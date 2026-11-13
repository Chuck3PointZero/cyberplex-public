#!/usr/bin/env python3
"""
collab-space MCP server
=======================

Makes oaa/tools/collab-space/TOOL.md's `authority.never` block real instead of decorative.

Agents share business documents, tasks and owner decisions in Cyberplex collaboration projects
("shared spaces"). This is a small MCP server (stdio, JSON-RPC) that calls the Cyberplex REST API itself:

    runner gateway  <--stdio-->  this server  --https-->  Cyberplex /v1/agent-token, /v1/collaboration/<operation>

- The tenant API key stays in this process. It is used only to mint a short-lived agent token for OAA_AGENT,
  one per space, carrying only the operations that agent's part in the space allows and that one project id.
- Cyberplex has no owner/contributor split for a notebook. This server enforces it from server/spaces.json.
- No function takes a project id, an agent id for the caller, a URL, a header or a tenant from the agent.
- Task fences never leave this process; leases and heartbeats are renewed here while the run is alive.

If you change a rule here, change TOOL.md's `never` list too. The server is the enforcement; TOOL.md is the
declaration; they must agree.

Dependency-free: Python 3 standard library only.
"""

import hashlib
import json
import os
import re
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

TOOL = "collab-space"
CREDENTIAL_ENV = "CYBERPLEX_COLLAB_API_KEY"
HERE = Path(__file__).resolve()
TOOL_DIR = HERE.parents[2]   # proxy -> server -> collab-space
REPO_DIR = HERE.parents[5]   # ... -> tools -> oaa -> repository root

BASE_URL = (os.environ.get("CYBERPLEX_COLLAB_URL") or "https://cyberplex.cpe.net").rstrip("/")  # an empty value means the default
AGENT = os.environ.get("OAA_AGENT", "").strip().lower()
SPACES_FILE = Path(os.environ.get("COLLAB_SPACES_FILE") or TOOL_DIR / "server" / "spaces.json")
LOCAL_FILE = Path(os.environ.get("COLLAB_SPACES_LOCAL") or REPO_DIR / "spaces.local.json")
STATE_DIR = Path(os.environ.get("COLLAB_STATE_DIR") or REPO_DIR / ".state")
TOKEN_TTL_SEC = 900
HTTP_TIMEOUT_SEC = 30
RENEW_EVERY_SEC = float(os.environ.get("COLLAB_RENEW_EVERY_SEC", "40"))
HEARTBEAT_EVERY_SEC = 90
RETIRE_AT_REVISION = 150          # of the 180 ordinary edits a notebook gets in its life
MAX_ENTRIES, MAX_QUESTIONS, MAX_CONSTRAINTS = 50, 30, 30
AGENT_ID = re.compile(r"^[a-z0-9_-]{1,64}$")
PROJECT_ID = re.compile(r"^[A-Za-z0-9_-]{1,100}$")
SPACE_NAME = re.compile(r"^[a-z0-9-]{1,40}$")
AGENT_STATUSES = ("suggestion", "fact")          # never: write-accepted-or-verified
HUMAN_STATUSES = ("accepted", "verified")

# never: decide-a-request -> project.create, agent.verify and decision.decide are in no list below.
READ_OPS = ["project.get", "project.history", "project.checkpoints", "project.handoff", "agent.get", "agent.list",
            "task.get", "task.list", "decision.get", "decision.list"]
CONTRIBUTOR_OPS = READ_OPS + ["project.update", "agent.upsert", "agent.heartbeat", "task.create", "task.claim",
                              "task.renew", "task.update", "task.cancel"]
OWNER_OPS = CONTRIBUTOR_OPS + ["project.checkpoint"]
DECISION_OPS = ["decision.create", "decision.consume", "decision.cancel"]
RANK = {"reader": 1, "contributor": 2, "owner": 3}


class Refused(Exception):
    """A rule of this tool blocked the call."""


class ServiceError(Exception):
    def __init__(self, status, code, message=""):
        super().__init__(f"{code} ({status})" + (f": {message}" if message else ""))
        self.status, self.code = status, code


def log(text):
    sys.stderr.write(f"[{TOOL}] {text}\n")
    sys.stderr.flush()


# -- Settings -----------------------------------------------------------------

def load_settings():
    with open(SPACES_FILE, encoding="utf-8") as f:
        settings = json.load(f)
    projects = {}
    if LOCAL_FILE.is_file():
        with open(LOCAL_FILE, encoding="utf-8") as f:
            projects = (json.load(f) or {}).get("projects", {})
    return settings, projects


def part_in(space):
    """This agent's part in a space: owner, contributor, reader, or None."""
    if space.get("owner") == AGENT:
        return "owner"
    if AGENT in space.get("contributors", []):
        return "contributor"
    readers = space.get("readers", [])
    if readers == "*" or AGENT in readers:
        return "reader" if AGENT in SETTINGS.get("agents", {}) else None
    return None


def my_skills():
    return list(SETTINGS.get("agents", {}).get(AGENT, {}).get("skills") or [AGENT])


def space_for(name, need="reader"):
    """Resolve a space name to (space, project id, part), or refuse. Agents never pass a project id."""
    if not isinstance(name, str) or not SPACE_NAME.match(name) or name not in SETTINGS["spaces"]:
        raise Refused(f"reach-a-space-without-a-part: no space named {name!r}; call spaces_list")
    space = SETTINGS["spaces"][name]
    part = part_in(space)
    if part is None:
        raise Refused(f"reach-a-space-without-a-part: {AGENT} has no part in {name}")
    if RANK[part] < RANK[need]:
        raise Refused(f"act-beyond-your-part: {name} needs the {need} part; {AGENT} is a {part}")
    project = PROJECTS.get(name, "")
    if not PROJECT_ID.match(project or ""):
        raise ValueError(f"space {name} is not set up yet: the owner has not created it (no project id in "
                         f"{LOCAL_FILE.name}). Report data-source-unavailable.")
    return space, project, part


# -- HTTP ---------------------------------------------------------------------

_tokens, _lock = {}, threading.RLock()


def _post(path, body, bearer):
    request = urllib.request.Request(BASE_URL + path, data=json.dumps(body).encode("utf-8"), method="POST",
                                     headers={"content-type": "application/json", "authorization": "Bearer " + bearer})
    try:
        with urllib.request.urlopen(request, timeout=HTTP_TIMEOUT_SEC) as response:
            return json.loads(response.read().decode("utf-8") or "{}")
    except urllib.error.HTTPError as e:
        try:
            error = (json.loads(e.read().decode("utf-8")) or {}).get("error") or {}
        except Exception:
            error = {}
        # never: expose-key-or-token -> only the service's code and message travel on; never the request.
        raise ServiceError(e.code, str(error.get("code") or "http_error"), str(error.get("message") or "")[:300]) from None
    except urllib.error.URLError as e:
        raise ServiceError(0, "unreachable", str(e.reason)[:200]) from None


def ops_for(space_name, part):
    ops = {"reader": READ_OPS, "contributor": CONTRIBUTOR_OPS, "owner": OWNER_OPS}[part][:]
    if AGENT in SETTINGS["spaces"][space_name].get("decision_requesters", []):
        ops += DECISION_OPS
    return ops


def token_for(space_name, project, part, fresh=False):
    with _lock:
        cached = _tokens.get(space_name)
        if cached and not fresh and cached[1] > time.time() + 60:
            return cached[0]
        issued = _post("/v1/agent-token", {
            "agentId": AGENT, "ops": ["history"], "channels": [], "ttlSec": TOKEN_TTL_SEC,
            "collaboration": {"ops": ops_for(space_name, part), "projects": [project]}},
            os.environ.get(CREDENTIAL_ENV, "").strip())
        _tokens[space_name] = (issued["token"], time.time() + TOKEN_TTL_SEC)
        return issued["token"]


def op(space_name, project, part, operation, body=None):
    """One collaboration operation as this agent in this space. Mints again once after a 401."""
    payload = {"projectId": project, **(body or {})}
    try:
        return _post(f"/v1/collaboration/{operation}", payload, token_for(space_name, project, part))
    except ServiceError as e:
        if e.status != 401:
            raise
        return _post(f"/v1/collaboration/{operation}", payload, token_for(space_name, project, part, fresh=True))


def key(*parts):
    """A stable idempotency key: the same call repeated returns the original record."""
    return "k" + hashlib.sha256("\x1f".join(str(p) for p in (AGENT,) + parts).encode("utf-8")).hexdigest()[:48]


# -- Local state (per agent): decision bindings and posted tasks ---------------

def _state_file():
    return STATE_DIR / f"{AGENT}.json"


def load_state():
    try:
        with open(_state_file(), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {"decisions": {}, "tasks": {}}


def save_state(state):
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    temporary = _state_file().with_suffix(".tmp")
    with open(temporary, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)
    os.replace(temporary, _state_file())


# -- Arguments ----------------------------------------------------------------

def text_arg(arguments, name, limit, required=True):
    value = arguments.get(name)
    if value is None and not required:
        return None
    if not isinstance(value, str) or not value.strip() or len(value.strip()) > limit or "\x00" in value:
        raise ValueError(f"{name} must be text of 1 to {limit} characters")
    return value.strip()


def links_arg(arguments, name="sources"):
    links = arguments.get(name) or []
    if not isinstance(links, list) or len(links) > 20:
        raise ValueError(f"{name} must be a list of at most 20 links")
    clean = []
    for link in links:
        if not isinstance(link, dict) or not str(link.get("url", "")).startswith("https://"):
            raise ValueError(f"each item of {name} needs a label and an https url")
        item = {"label": text_arg(link, "label", 500), "url": text_arg(link, "url", 2048)}
        if link.get("digest"):
            item["digest"] = text_arg(link, "digest", 128)
        clean.append(item)
    return clean


def int_arg(arguments, name, low, high, default=None):
    value = arguments.get(name, default)
    if not isinstance(value, int) or isinstance(value, bool) or not low <= value <= high:
        raise ValueError(f"{name} must be a whole number from {low} to {high}")
    return value


def plain(entry):
    return {"text": entry["text"], "status": entry["status"], "sources": entry.get("sources", [])}


def document(space_name, record):
    data = record["data"]
    return {"space": space_name, "revision": record["revision"], "updated_at": record["updatedAt"],
            "title": data["title"], "objective": data["objective"], "constraints": data.get("constraints", []),
            "questions": data.get("questions", []),
            "entries": [{"n": i + 1, "text": e["text"], "status": e["status"], "sources": e.get("sources", []),
                         "by": (e.get("author") or {}).get("id"), "by_kind": (e.get("author") or {}).get("kind")}
                        for i, e in enumerate(data.get("entries", []))],
            "artifacts": data.get("artifacts", []), "edited_by": (data.get("editedBy") or {}).get("id")}


def update_body(data, revision, **changes):
    body = {"expectedRevision": revision, "title": data["title"], "objective": data["objective"],
            "constraints": data.get("constraints", []), "questions": data.get("questions", []),
            "entries": [plain(e) for e in data.get("entries", [])], "artifacts": data.get("artifacts", [])}
    body.update(changes)
    return body


# -- Spaces and documents ------------------------------------------------------

def spaces_list(arguments):
    out = []
    for name, space in SETTINGS["spaces"].items():
        part = part_in(space)
        if part is None:
            continue
        item = {"space": name, "title": space["title"], "your_part": part, "owner": space["owner"],
                "guide": space.get("guide", ""),
                "may_ask_owner_decision": AGENT in space.get("decision_requesters", []),
                "set_up": bool(PROJECT_ID.match(PROJECTS.get(name, "") or ""))}
        if item["set_up"]:
            try:
                record = op(name, PROJECTS[name], part, "project.get")
                item["revision"] = record["revision"]
                item["retire_soon"] = record["revision"] >= RETIRE_AT_REVISION
            except ServiceError as e:
                item["error"] = e.code
        out.append(item)
    return {"agent": AGENT, "skills": my_skills(), "spaces": out}


def space_read(arguments):
    name = arguments.get("space")
    _, project, part = space_for(name)
    return {**document(name, op(name, project, part, "project.get")), "guide": SETTINGS["spaces"][name].get("guide", "")}


def space_history(arguments):
    name = arguments.get("space")
    _, project, part = space_for(name)
    page = op(name, project, part, "project.history", {"after": int_arg(arguments, "after", 0, 10**12, 0),
                                                       "limit": int_arg(arguments, "limit", 1, 50, 20)})
    return {"space": name, **page}


def space_propose(arguments):
    """never: let-a-contributor-rewrite -> the update is the current document plus exactly one item."""
    name = arguments.get("space")
    _, project, part = space_for(name, "contributor")
    kind = arguments.get("kind", "suggestion")
    if kind not in ("suggestion", "question"):
        raise ValueError("kind must be 'suggestion' or 'question'")
    text = text_arg(arguments, "text", 4000 if kind == "suggestion" else 500)
    sources = links_arg(arguments)
    for _ in range(4):
        record = op(name, project, part, "project.get")
        data = record["data"]
        if kind == "suggestion":
            entries = [plain(e) for e in data.get("entries", [])]
            new = {"text": text, "status": "suggestion", "sources": sources}
            if new in entries:
                return {"space": name, "revision": record["revision"], "already_present": True}
            if len(entries) >= MAX_ENTRIES:
                raise ValueError(f"{name} already has {MAX_ENTRIES} entries; ask its owner ({SETTINGS['spaces'][name]['owner']}) to tidy it")
            body = update_body(data, record["revision"], entries=entries + [new])
        else:
            questions = list(data.get("questions", []))
            if text in questions:
                return {"space": name, "revision": record["revision"], "already_present": True}
            if len(questions) >= MAX_QUESTIONS:
                raise ValueError(f"{name} already has {MAX_QUESTIONS} open questions")
            body = update_body(data, record["revision"], questions=questions + [text])
        try:
            saved = op(name, project, part, "project.update", body)
            return {"space": name, "revision": saved["revision"], "added": kind}
        except ServiceError as e:
            if e.code != "conflict":
                raise
    raise ValueError("the document kept changing while adding your item; try again later")


def space_write(arguments):
    """Owner only. Human entries (accepted, verified) are carried over untouched, whatever the agent sends."""
    name = arguments.get("space")
    _, project, part = space_for(name, "owner")
    revision = int_arg(arguments, "expected_revision", 1, 200)
    record = op(name, project, part, "project.get")
    if record["revision"] != revision:
        raise ValueError(f"the document is at revision {record['revision']}, not {revision}; read it again and redo your edit")
    data, changes = record["data"], {}
    if "objective" in arguments:
        changes["objective"] = text_arg(arguments, "objective", 4000)
    for field, limit in (("constraints", MAX_CONSTRAINTS), ("questions", MAX_QUESTIONS)):
        if field in arguments:
            values = arguments[field]
            if not isinstance(values, list) or len(values) > limit:
                raise ValueError(f"{field} must be a list of at most {limit} lines")
            changes[field] = [text_arg({"v": v}, "v", 500) for v in values]
    if "entries" in arguments:
        sent = arguments["entries"]
        if not isinstance(sent, list):
            raise ValueError("entries must be a list")
        mine = []
        for entry in sent:
            if not isinstance(entry, dict):
                raise ValueError("each entry needs text and status")
            status = entry.get("status")
            if status in HUMAN_STATUSES:
                continue  # carried over from the current document below; an agent's copy is ignored
            if status not in AGENT_STATUSES:
                raise Refused("write-accepted-or-verified: an agent entry is 'suggestion' or 'fact'")
            mine.append({"text": text_arg(entry, "text", 4000), "status": status, "sources": links_arg(entry)})
        kept = [plain(e) for e in data.get("entries", []) if e["status"] in HUMAN_STATUSES]
        if len(kept) + len(mine) > MAX_ENTRIES:
            raise ValueError(f"a document holds at most {MAX_ENTRIES} entries ({len(kept)} are the owner's)")
        changes["entries"] = kept + mine
    if not changes:
        raise ValueError("nothing to change: send objective, constraints, questions or entries")
    try:
        saved = op(name, project, part, "project.update", update_body(data, revision, **changes))
    except ServiceError as e:
        if e.code == "conflict":
            raise ValueError("someone else edited the document first; read it again and redo your edit") from None
        raise
    return document(name, saved)


def space_checkpoint(arguments):
    name = arguments.get("space")
    _, project, part = space_for(name, "owner")
    label = text_arg(arguments, "label", 200)
    record = op(name, project, part, "project.get")
    saved = op(name, project, part, "project.checkpoint", {
        "expectedRevision": record["revision"], "label": label, "idempotencyKey": key("checkpoint", name, label, record["revision"])})
    return {"space": name, "checkpoint_id": saved["id"], "label": label, "document_revision": record["revision"]}


def space_handoff(arguments):
    name = arguments.get("space")
    _, project, part = space_for(name)
    checkpoint = arguments.get("checkpoint_id")
    if checkpoint is None:
        saved = op(name, project, part, "project.checkpoints", {"limit": 50}).get("items", [])
        if not saved:
            return {"space": name, "checkpoint": None, "note": "no checkpoint yet; use space_read"}
        checkpoint = max(saved, key=lambda c: c["createdAt"])["id"]
    elif not isinstance(checkpoint, str) or not PROJECT_ID.match(checkpoint):
        raise ValueError("checkpoint_id is not a valid id")
    changes, after, first = [], None, None
    for _ in range(5):
        page = op(name, project, part, "project.handoff", {"checkpointId": checkpoint, "limit": 50,
                                                           **({"after": after} if after is not None else {})})
        first = first or page
        changes += page.get("changes", [])
        after = page.get("next")
        if after is None:
            break
    data = first["checkpoint"]["data"]
    return {"space": name, "checkpoint_id": checkpoint, "label": data.get("label"),
            "document_at_checkpoint": data.get("notebook"), "tasks_at_checkpoint": data.get("tasks"),
            "decisions_at_checkpoint": data.get("decisions"), "changes_since": changes, "more_changes": after is not None}


def directory_search(arguments):
    name = arguments.get("space")
    _, project, part = space_for(name)
    search = arguments.get("search", "")
    if not isinstance(search, str) or len(search) > 100:
        raise ValueError("search must be text of at most 100 characters")
    page = op(name, project, part, "agent.list", {"search": search, "limit": 50})
    return {"space": name, "agents": [{"agent": c["id"], "description": c["data"].get("description"),
                                       "skills": c["data"].get("skills"), "availability": c["data"].get("availability"),
                                       "recent_heartbeat": c["data"].get("recentHeartbeat"),
                                       "verified_by_owner": bool(c["data"].get("attestation"))} for c in page.get("items", [])]}


# -- Tasks ----------------------------------------------------------------------

_claims = {}          # task id -> {"space", "project", "part", "fence"}; never returned to the agent
_heartbeats = {}      # space -> last heartbeat time
_renewer = None


def ensure_card(name, project, part):
    """Register this agent's card in the space (only when it differs) and send a heartbeat."""
    profile = SETTINGS.get("agents", {}).get(AGENT, {})
    want = {"description": profile.get("description") or f"{AGENT}, an agent of this team", "skills": my_skills(),
            "inputs": [], "outputs": [], "availability": "available", "evidence": []}
    try:
        card = op(name, project, part, "agent.get", {"id": AGENT})
        current = {k: card["data"].get(k) for k in want}
        if current != want:
            op(name, project, part, "agent.upsert", {"expectedRevision": card["revision"], **want})
    except ServiceError as e:
        if e.status != 404:
            raise
        op(name, project, part, "agent.upsert", {"expectedRevision": 0, **want})
    op(name, project, part, "agent.heartbeat")
    _heartbeats[name] = time.time()


def _renew_loop():
    while True:
        time.sleep(RENEW_EVERY_SEC)
        with _lock:
            held = dict(_claims)
        for task_id, claim in held.items():
            try:
                op(claim["space"], claim["project"], claim["part"], "task.renew", {"id": task_id, "fence": claim["fence"]})
                if time.time() - _heartbeats.get(claim["space"], 0) > HEARTBEAT_EVERY_SEC:
                    op(claim["space"], claim["project"], claim["part"], "agent.heartbeat")
                    _heartbeats[claim["space"]] = time.time()
            except ServiceError as e:
                log(f"lease on {task_id} not renewed: {e.code}")
                if e.code in ("stale_lease", "conflict", "not_found"):
                    with _lock:
                        _claims.pop(task_id, None)


def task_view(record):
    data = record["data"]
    return {"task_id": record["id"], "revision": record["revision"], "objective": data.get("objective"),
            "expected_result": data.get("expectedResult"), "state": data.get("effectiveState", data.get("state")),
            "claimable": data.get("claimable"), "required_skills": data.get("requiredSkills", []),
            "recipient": data.get("recipient"), "assigned_to": data.get("assignedTo"),
            "created_by": (data.get("createdBy") or {}).get("id"), "created_by_kind": (data.get("createdBy") or {}).get("kind"),
            "deadline": data.get("deadline"), "lease_until": data.get("leaseUntil"), "attempt": data.get("attempt"), "progress": data.get("progress"),
            "blocker": data.get("blocker"), "result": data.get("result"), "held_by_this_run": record["id"] in _claims}


def all_tasks(name, project, part, pages=4):
    items, after = [], None
    for _ in range(pages):
        page = op(name, project, part, "task.list", {"limit": 50, **({"after": after} if after else {})})
        items += page.get("items", [])
        after = page.get("next")
        if not after:
            break
    return items


def task_post(arguments):
    name = arguments.get("space")
    _, project, part = space_for(name, "contributor")
    objective, expected = text_arg(arguments, "objective", 4000), text_arg(arguments, "expected_result", 4000)
    role = text_arg(arguments, "role", 80)
    known = {s for a in SETTINGS.get("agents", {}).values() for s in a.get("skills", [])}
    if role not in known:
        raise ValueError(f"no agent holds the skill {role!r}; known skills: {', '.join(sorted(known))}")
    hours = int_arg(arguments, "deadline_hours", 1, 720, 72)
    state, post_key = load_state(), key("task", name, objective, expected, role, time.strftime("%Y-%m-%d", time.gmtime()))
    if post_key in state["tasks"]:
        try:
            return {**task_view(op(name, project, part, "task.get", {"id": state["tasks"][post_key]})), "already_posted_today": True}
        except ServiceError:
            pass
    record = op(name, project, part, "task.create", {
        "objective": objective, "expectedResult": expected, "requiredSkills": [role], "context": links_arg(arguments, "context"),
        "deadline": int(time.time() * 1000) + hours * 3600_000, "idempotencyKey": post_key})
    state["tasks"][post_key] = record["id"]
    save_state(state)
    return task_view(record)


def task_list(arguments):
    name = arguments.get("space")
    _, project, part = space_for(name)
    wanted = arguments.get("state")
    tasks = [task_view(t) for t in all_tasks(name, project, part)]
    if wanted:
        tasks = [t for t in tasks if str(t["state"]).lower() == str(wanted).lower()]
    if arguments.get("for_me"):
        skills = set(my_skills())
        tasks = [t for t in tasks if t["claimable"] and set(t["required_skills"]) <= skills and t["recipient"] in (None, AGENT)]
    return {"space": name, "tasks": tasks}


def task_get(arguments):
    name = arguments.get("space")
    _, project, part = space_for(name)
    return task_view(op(name, project, part, "task.get", {"id": text_arg(arguments, "task_id", 100)}))


def task_claim(arguments):
    global _renewer
    name = arguments.get("space")
    _, project, part = space_for(name, "contributor")
    task_id = text_arg(arguments, "task_id", 100)
    ensure_card(name, project, part)
    record = op(name, project, part, "task.get", {"id": task_id})
    claimed = op(name, project, part, "task.claim", {"id": task_id, "expectedRevision": record["revision"]})
    if not claimed.get("lease"):
        return {**task_view(claimed), "claimed": False, "note": "Not claimed: see the task's state (its deadline may have passed)."}
    with _lock:
        # never: expose-key-or-token -> the fence is a credential for this attempt; it stays here.
        _claims[task_id] = {"space": name, "project": project, "part": part, "fence": claimed["lease"]["fence"]}
        if _renewer is None:
            _renewer = threading.Thread(target=_renew_loop, daemon=True)
            _renewer.start()
    return {**task_view(claimed), "note": "The lease is renewed for you while this run lasts. Finish and report this "
                                          "task in this run; an unreported task goes back to available."}


REPORT_STATES = {"working": "Working", "needs-input": "Needs input", "completed": "Completed", "failed": "Failed"}


def task_report(arguments):
    name = arguments.get("space")
    _, project, part = space_for(name, "contributor")
    task_id = text_arg(arguments, "task_id", 100)
    claim = _claims.get(task_id)
    if not claim:
        raise ValueError("this run does not hold that task; claim it first (a claim does not carry over between runs)")
    state = REPORT_STATES.get(str(arguments.get("state", "")).lower())
    if not state:
        raise ValueError("state must be one of: " + ", ".join(REPORT_STATES))
    body = {"id": task_id, "fence": claim["fence"], "state": state, "evidence": links_arg(arguments, "evidence"),
            "message": text_arg(arguments, "message", 4000, required=False) or ""}
    for field in ("progress", "blocker"):
        if arguments.get(field) is not None:
            body[field] = text_arg(arguments, field, 4000)
    if state == "Completed":
        body["result"] = {"summary": text_arg(arguments, "result_summary", 4000), "artifacts": links_arg(arguments, "artifacts")}
        body["idempotencyKey"] = key("complete", task_id, claim["fence"])
    record = op(name, project, part, "task.get", {"id": task_id})
    saved = op(name, project, part, "task.update", {**body, "expectedRevision": record["revision"]})
    if state in ("Completed", "Failed"):
        with _lock:
            _claims.pop(task_id, None)
    return {**task_view(saved), "receipt": saved["data"].get("receipt")}


def task_cancel(arguments):
    """Withdraw a task you posted. Cyberplex allows this only to the task's creator (or the tenant owner)."""
    name = arguments.get("space")
    _, project, part = space_for(name, "contributor")
    task_id = text_arg(arguments, "task_id", 100)
    record = op(name, project, part, "task.get", {"id": task_id})
    saved = op(name, project, part, "task.cancel", {"id": task_id, "expectedRevision": record["revision"],
                                                    "reason": text_arg(arguments, "reason", 1000, required=False) or ""})
    with _lock:
        _claims.pop(task_id, None)
    return task_view(saved)


# -- Owner decisions ---------------------------------------------------------------

def decision_view(record):
    data, verdict = record["data"], record["data"].get("decision") or {}
    return {"decision_id": record["id"], "state": data.get("state"), "action": data.get("action"), "target": data.get("target"),
            "action_revision": data.get("actionRevision"), "options": data.get("options"), "expires_at": data.get("expiresAt"),
            "requested_by": data.get("requesterId"), "chosen_option": verdict.get("option"),
            "explanation": verdict.get("explanation"), "decided_by": verdict.get("actorId"), "used": bool(data.get("consumption"))}


def decision_request(arguments):
    name = arguments.get("space")
    space, project, part = space_for(name)
    if AGENT not in space.get("decision_requesters", []):
        raise Refused(f"ask-the-owner-out-of-turn: in {name} only {', '.join(space.get('decision_requesters', [])) or 'nobody'} "
                      f"may ask the owner for a decision; hand it to them")
    action, target = text_arg(arguments, "action", 4000), text_arg(arguments, "target", 500)
    action_revision = text_arg(arguments, "action_revision", 500)
    options = arguments.get("options")
    if not isinstance(options, list) or not 1 <= len(options) <= 10:
        raise ValueError("options must be a list of 1 to 10 choices")
    options = [text_arg({"v": o}, "v", 500) for o in options]
    hours = int_arg(arguments, "expires_hours", 1, 168, 72)
    request_key = key("decision", name, action, target, action_revision)
    state = load_state()
    known = next((d for d in state["decisions"].values() if d.get("key") == request_key), None)
    expires = known["expires_at"] if known else int(time.time() * 1000) + hours * 3600_000
    # never: tie-a-decision-to-a-task -> taskId and fence are never sent; a decision must outlive the run.
    record = op(name, project, part, "decision.create", {
        "action": action, "target": target, "actionRevision": action_revision, "evidence": links_arg(arguments, "evidence"),
        "options": options, "expiresAt": expires, "idempotencyKey": request_key})
    state["decisions"][record["id"]] = {"key": request_key, "space": name, "action": action, "target": target,
                                        "action_revision": action_revision, "digest": record["data"]["digest"],
                                        "options": options, "expires_at": expires}
    save_state(state)
    return {**decision_view(record), "note": "The owner decides in the workspace page. Use decision_use on a later run."}


def decision_list(arguments):
    name = arguments.get("space")
    _, project, part = space_for(name)
    page = op(name, project, part, "decision.list", {"limit": 50})
    return {"space": name, "decisions": [decision_view(d) for d in page.get("items", [])]}


def decision_get(arguments):
    name = arguments.get("space")
    _, project, part = space_for(name)
    return decision_view(op(name, project, part, "decision.get", {"id": text_arg(arguments, "decision_id", 100)}))


def decision_use(arguments):
    """never: use-an-approval-that-is-not-the-one-asked -> every bound field is compared before the one use."""
    name = arguments.get("space")
    space, project, part = space_for(name)
    decision_id = text_arg(arguments, "decision_id", 100)
    asked = load_state()["decisions"].get(decision_id)
    if not asked or asked.get("space") != name:
        raise Refused("use-an-approval-that-is-not-the-one-asked: this agent has no record of asking for that decision")
    record = op(name, project, part, "decision.get", {"id": decision_id})
    data, view = record["data"], decision_view(record)
    # "Consumed" is this agent's own earlier use: the same call again recovers the same receipt (a retry
    # after a lost answer), it never makes a second authorization.
    if data.get("state") not in ("Approved", "Consumed"):
        return {**view, "authorized": False, "note": "Not approved. Do not carry out the action."}
    verdict = data.get("decision") or {}
    live = data.get("state") == "Consumed" or data.get("expiresAt", 0) > time.time() * 1000
    same = (data.get("requesterId") == AGENT and data.get("action") == asked["action"] and data.get("target") == asked["target"]
            and data.get("actionRevision") == asked["action_revision"] and data.get("digest") == asked["digest"]
            and verdict.get("option") in asked["options"] and live)
    if not same:
        raise Refused("use-an-approval-that-is-not-the-one-asked: the stored decision differs from what was asked, or expired")
    used = op(name, project, part, "decision.consume", {
        "id": decision_id, "action": asked["action"], "target": asked["target"], "actionRevision": asked["action_revision"],
        "digest": asked["digest"], "option": verdict["option"], "idempotencyKey": key("consume", decision_id)})
    return {**decision_view(used), "authorized": True, "use_receipt": (used["data"].get("consumption") or {}).get("id"),
            "already_used": data.get("state") == "Consumed",
            "note": "This records one authorization for exactly this action. Carrying it out is still your job. "
                    "already_used=true means an earlier call used it: check whether the action was already carried out."}


def decision_cancel(arguments):
    """Withdraw a request you made. Cyberplex allows this only to the agent that asked (or the tenant owner)."""
    name = arguments.get("space")
    space, project, part = space_for(name)
    if AGENT not in space.get("decision_requesters", []):
        raise Refused(f"ask-the-owner-out-of-turn: {AGENT} makes no decision requests in {name}, so has none to withdraw")
    decision_id = text_arg(arguments, "decision_id", 100)
    record = op(name, project, part, "decision.get", {"id": decision_id})
    return decision_view(op(name, project, part, "decision.cancel", {"id": decision_id, "expectedRevision": record["revision"]}))


# -- Waiting work ----------------------------------------------------------------

def pending_work(arguments):
    skills, waiting, problems = set(my_skills()), [], []
    asked = load_state()["decisions"]
    for name, space in SETTINGS["spaces"].items():
        part = part_in(space)
        if part is None or not PROJECT_ID.match(PROJECTS.get(name, "") or ""):
            continue
        project = PROJECTS[name]
        try:
            if RANK[part] >= RANK["contributor"]:
                for task in all_tasks(name, project, part):
                    view = task_view(task)
                    if view["claimable"] and set(view["required_skills"]) <= skills and view["recipient"] in (None, AGENT):
                        waiting.append({"kind": "task", "space": name, "task_id": view["task_id"], "objective": view["objective"],
                                        "from": view["created_by"], "from_kind": view["created_by_kind"]})
            for decision_id, binding in asked.items():
                if binding.get("space") != name:
                    continue
                view = decision_view(op(name, project, part, "decision.get", {"id": decision_id}))
                if view["state"] in ("Approved", "Rejected", "Changes requested") and not view["used"]:
                    waiting.append({"kind": "decision", "space": name, "decision_id": decision_id, "state": view["state"],
                                    "action": view["action"]})
        except ServiceError as e:
            problems.append({"space": name, "error": e.code})
    return {"agent": AGENT, "waiting": waiting, "problems": problems}


def waiting_by_agent(arguments):
    """For a dispatcher script: which agents have work waiting. Read with the dispatcher's own reader tokens;
    it never acts as the agents it reports on, and it returns ids and reasons, never document text."""
    if AGENT not in SETTINGS.get("dispatchers", []):
        raise Refused("act-beyond-your-part: only a dispatcher listed in spaces.json may ask who has work waiting")
    waiting, problems = [], []
    for name, space in SETTINGS["spaces"].items():
        part = part_in(space)
        if part is None or not PROJECT_ID.match(PROJECTS.get(name, "") or ""):
            continue
        project, workers = PROJECTS[name], [space["owner"]] + list(space.get("contributors", []))
        try:
            for task in all_tasks(name, project, part):
                view = task_view(task)
                if not view["claimable"]:
                    continue
                needed = set(view["required_skills"])
                able = [a for a in workers if view["recipient"] in (None, a)
                        and needed <= set(SETTINGS["agents"].get(a, {}).get("skills") or [a])]
                if not needed and not view["recipient"]:
                    able = [space["owner"]]          # addressed to nobody: the document's owner looks at it
                for agent in able:
                    waiting.append({"agent": agent, "kind": "task", "space": name, "id": view["task_id"],
                                    "from_kind": view["created_by_kind"]})
            for record in op(name, project, part, "decision.list", {"limit": 50}).get("items", []):
                view = decision_view(record)
                if view["state"] in ("Approved", "Rejected", "Changes requested") and not view["used"] and view["requested_by"]:
                    waiting.append({"agent": view["requested_by"], "kind": "decision", "space": name, "id": view["decision_id"],
                                    "state": view["state"]})
        except ServiceError as e:
            problems.append({"space": name, "error": e.code})
    return {"waiting": waiting, "problems": problems}


# -- MCP -------------------------------------------------------------------------

SPACE = {"space": {"type": "string", "description": "a space name from spaces_list"}}
LINKS = {"type": "array", "items": {"type": "object", "properties": {"label": {"type": "string"}, "url": {"type": "string"}}}}


def tool(name, description, properties=None, required=None):
    return {"name": name, "description": description,
            "inputSchema": {"type": "object", "properties": properties or {}, "required": required or []}}


TOOLS = [
    tool("spaces_list", "The shared spaces you have a part in, your part in each (owner, contributor, reader), and whether each is near retirement."),
    tool("space_read", "The document of one space: objective, constraints, open questions and entries with their status and author.", SPACE, ["space"]),
    tool("space_history", "Who changed the document and when, oldest first.", {**SPACE, "after": {"type": "integer"}, "limit": {"type": "integer"}}, ["space"]),
    tool("space_propose", "Contributor: add ONE suggestion entry or ONE open question to a document. Changes nothing else. Costs one of the document's 180 lifetime edits.",
         {**SPACE, "kind": {"type": "string", "enum": ["suggestion", "question"]}, "text": {"type": "string"}, "sources": LINKS}, ["space", "text"]),
    tool("space_write", "Owner only: replace the objective, constraints, questions or your entries (status 'suggestion' or 'fact'). The tenant owner's accepted and verified entries are always kept. Write once per run.",
         {**SPACE, "expected_revision": {"type": "integer"}, "objective": {"type": "string"}, "constraints": {"type": "array", "items": {"type": "string"}},
          "questions": {"type": "array", "items": {"type": "string"}},
          "entries": {"type": "array", "items": {"type": "object", "properties": {"text": {"type": "string"}, "status": {"type": "string", "enum": list(AGENT_STATUSES)}, "sources": LINKS}}}},
         ["space", "expected_revision"]),
    tool("space_checkpoint", "Owner only: save a snapshot of the document with its tasks and decisions.", {**SPACE, "label": {"type": "string"}}, ["space", "label"]),
    tool("space_handoff", "The latest (or a named) checkpoint plus everything that changed since. Use it when you start cold.", {**SPACE, "checkpoint_id": {"type": "string"}}, ["space"]),
    tool("directory_search", "The agents registered in a space, with skills and availability.", {**SPACE, "search": {"type": "string"}}, ["space"]),
    tool("task_post", "Ask a role to do something: a task any agent holding that skill can claim. Address the role, not an agent.",
         {**SPACE, "objective": {"type": "string"}, "expected_result": {"type": "string"}, "role": {"type": "string", "description": "the required skill, e.g. security-lead"},
          "deadline_hours": {"type": "integer"}, "context": LINKS}, ["space", "objective", "expected_result", "role"]),
    tool("task_list", "Tasks in a space. for_me=true keeps only those you can claim now.", {**SPACE, "state": {"type": "string"}, "for_me": {"type": "boolean"}}, ["space"]),
    tool("task_get", "One task with its progress and result.", {**SPACE, "task_id": {"type": "string"}}, ["space", "task_id"]),
    tool("task_claim", "Take a task. You must finish and report it in this run.", {**SPACE, "task_id": {"type": "string"}}, ["space", "task_id"]),
    tool("task_report", "Report on a task this run holds: working, needs-input, completed (with result_summary) or failed.",
         {**SPACE, "task_id": {"type": "string"}, "state": {"type": "string", "enum": list(REPORT_STATES)}, "message": {"type": "string"},
          "progress": {"type": "string"}, "blocker": {"type": "string"}, "result_summary": {"type": "string"}, "artifacts": LINKS, "evidence": LINKS},
         ["space", "task_id", "state"]),
    tool("task_cancel", "Withdraw a task you posted. Only the agent that posted it can.",
         {**SPACE, "task_id": {"type": "string"}, "reason": {"type": "string"}}, ["space", "task_id"]),
    tool("decision_request", "Ask the tenant owner to decide one exact action. Only agents the space names may ask.",
         {**SPACE, "action": {"type": "string"}, "target": {"type": "string"}, "action_revision": {"type": "string"},
          "options": {"type": "array", "items": {"type": "string"}}, "expires_hours": {"type": "integer"}, "evidence": LINKS},
         ["space", "action", "target", "action_revision", "options"]),
    tool("decision_list", "Decision requests in a space and their state.", SPACE, ["space"]),
    tool("decision_get", "One decision request.", {**SPACE, "decision_id": {"type": "string"}}, ["space", "decision_id"]),
    tool("decision_use", "Use an approval you asked for, once. Checks it is exactly what you asked. authorized=false means do not act.",
         {**SPACE, "decision_id": {"type": "string"}}, ["space", "decision_id"]),
    tool("decision_cancel", "Withdraw a decision request you made, before or after the owner answers. It can no longer be used.",
         {**SPACE, "decision_id": {"type": "string"}}, ["space", "decision_id"]),
    tool("waiting_by_agent", "Dispatcher scripts only: which agents have a claimable task or an answered decision waiting, by space. Ids and reasons only."),
    tool("pending_work", "Across your spaces: tasks you can claim now, and decisions of yours the owner has answered."),
]

FUNCTIONS = {f.__name__: f for f in (spaces_list, space_read, space_history, space_propose, space_write, space_checkpoint,
                                     space_handoff, directory_search, task_post, task_list, task_get, task_claim, task_report,
                                     task_cancel, decision_request, decision_list, decision_get, decision_use, decision_cancel,
                                     pending_work, waiting_by_agent)}
SETTINGS, PROJECTS = {"spaces": {}, "agents": {}}, {}


def call(name, arguments):
    global SETTINGS, PROJECTS
    if name not in FUNCTIONS:
        raise Refused(f"function-not-on-allowlist:{name}")
    # never: act-as-another-agent -> the identity is the runner's OAA_AGENT, never an argument.
    if not AGENT_ID.match(AGENT):
        raise Refused("act-as-another-agent: OAA_AGENT is not set; the runner must launch this tool")
    host = urllib.parse.urlparse(BASE_URL).hostname or ""
    if not (BASE_URL.startswith("https://") or (BASE_URL.startswith("http://") and host in ("127.0.0.1", "localhost"))):
        raise Refused("expose-key-or-token: CYBERPLEX_COLLAB_URL must be an https address")
    SETTINGS, PROJECTS = load_settings()
    if AGENT not in SETTINGS.get("agents", {}):
        raise Refused(f"reach-a-space-without-a-part: {AGENT} is not listed in {SPACES_FILE.name}")
    return FUNCTIONS[name](arguments)


def result(request_id, payload, is_error=False):
    text = payload if isinstance(payload, str) else json.dumps(payload, indent=2, ensure_ascii=False)
    return {"jsonrpc": "2.0", "id": request_id, "result": {"isError": is_error, "content": [{"type": "text", "text": text}]}}


def handle(message):
    method, request_id = message.get("method"), message.get("id")
    if request_id is None:
        return None
    if method == "initialize":
        version = (message.get("params") or {}).get("protocolVersion", "2025-06-18")
        return {"jsonrpc": "2.0", "id": request_id, "result": {
            "protocolVersion": version, "capabilities": {"tools": {}}, "serverInfo": {"name": TOOL, "version": "0.1.0"}}}
    if method == "ping":
        return {"jsonrpc": "2.0", "id": request_id, "result": {}}
    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": request_id, "result": {"tools": TOOLS}}
    if method == "tools/call":
        params = message.get("params") or {}
        name, arguments = params.get("name", ""), params.get("arguments") or {}
        if not os.environ.get(CREDENTIAL_ENV, "").strip():
            return result(request_id, f"{TOOL} is unavailable: {CREDENTIAL_ENV} is not set. Report data-source-unavailable.", True)
        try:
            return result(request_id, call(name, arguments))
        except Refused as e:
            log(f"BLOCKED {name}: {e}")
            return result(request_id, f"BLOCKED by tools/{TOOL}: {e}. This is a hard ceiling from tools/{TOOL}/TOOL.md "
                                      f"authority.never; escalate instead of retrying.", True)
        except ServiceError as e:
            return result(request_id, f"Cyberplex refused: {e}", True)
        except Exception as e:
            return result(request_id, f"Error: {e}", True)
    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": -32601, "message": f"method not found: {method}"}}


def main():
    sys.stdin.reconfigure(encoding="utf-8")
    sys.stdout.reconfigure(encoding="utf-8")
    for raw_line in sys.stdin:
        line = raw_line.strip()
        if not line:
            continue
        try:
            message = json.loads(line)
        except json.JSONDecodeError:
            continue
        response = handle(message)
        if response is not None:
            sys.stdout.write(json.dumps(response, ensure_ascii=False) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
