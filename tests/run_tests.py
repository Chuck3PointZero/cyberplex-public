#!/usr/bin/env python3
"""
Tests for the collab-space tool, using the team in oaa/tools/collab-space/server/spaces.json.

    python tests/run_tests.py t0             static checks, no network
    python tests/run_tests.py t2             live, against your own tenant: needs .env and spaces.local.json (see README)
    python tests/run_tests.py t2 --no-wait   do not wait for the tenant owner's approval; report those cases as blocked

The live level uses the collab-test space and writes a few records in it: suggestions, tasks and decision requests.

A case passes only when its stated result is observed. A case that could not run is reported as blocked.
Results are written to tests/results/<level>-<time>.json. Nothing here prints a key or a token.
"""

import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
TOOL_DIR = REPO / "oaa" / "tools" / "collab-space"
PROXY = TOOL_DIR / "server" / "proxy" / "proxy.py"
SPACES_FILE = TOOL_DIR / "server" / "spaces.json"
sys.path.insert(0, str(TOOL_DIR))
import setup_spaces  # noqa: E402

SPACE = "collab-test"
SECURITY_ROLE = "head-of-security-and-reliability"
TOKEN = re.compile(r"eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}")


class Results:
    def __init__(self, level):
        self.level, self.cases, self.transcript = level, [], []

    def check(self, case, ok, detail=""):
        self.cases.append({"id": case, "result": "pass" if ok else "FAIL", "detail": str(detail)[:400]})
        print(f"{'PASS' if ok else 'FAIL'}  {case}  {str(detail)[:150]}")
        return ok

    def blocked(self, case, reason):
        self.cases.append({"id": case, "result": "blocked", "detail": reason})
        print(f"BLOCKED  {case}  {reason}")

    def finish(self):
        counts = {r: sum(1 for c in self.cases if c["result"] == r) for r in ("pass", "FAIL", "blocked")}
        out = REPO / "tests" / "results"
        out.mkdir(parents=True, exist_ok=True)
        path = out / f"{self.level}-{time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())}.json"
        path.write_text(json.dumps({"level": self.level, "counts": counts, "cases": self.cases}, indent=2), encoding="utf-8")
        print(f"\n{self.level}: {counts['pass']} passed, {counts['FAIL']} failed, {counts['blocked']} blocked. Results: {path.relative_to(REPO)}")
        return 1 if counts["FAIL"] else (2 if counts["blocked"] else 0)


class Agent:
    """One run of one agent: a real proxy.py process, spoken to over MCP, started the way the runner starts it."""

    def __init__(self, name, env, results):
        self.name, self.results, self.n = name, results, 0
        full = {**os.environ, **env, "OAA_AGENT": name}
        self.process = subprocess.Popen([sys.executable, str(PROXY)], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                        stderr=subprocess.PIPE, text=True, encoding="utf-8", env=full)
        threading.Thread(target=self._drain, daemon=True).start()

    def _drain(self):
        for line in self.process.stderr:
            self.results.transcript.append(line)

    def call(self, function, **arguments):
        self.n += 1
        self.process.stdin.write(json.dumps({"jsonrpc": "2.0", "id": self.n, "method": "tools/call",
                                             "params": {"name": function, "arguments": arguments}}) + "\n")
        self.process.stdin.flush()
        line = self.process.stdout.readline()
        self.results.transcript.append(line)
        answer = json.loads(line)["result"]
        text = answer["content"][0]["text"]
        try:
            return not answer["isError"], json.loads(text)
        except ValueError:
            return not answer["isError"], text

    def close(self):
        try:
            self.process.stdin.close()
            self.process.wait(timeout=10)
        except Exception:
            self.process.kill()


def post(url, body, headers):
    request = urllib.request.Request(url, data=json.dumps(body).encode(), method="POST",
                                     headers={"content-type": "application/json", **headers})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return response.status, json.loads(response.read().decode() or "{}"), response.headers
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode() or "{}"), e.headers
        except ValueError:
            return e.code, {}, e.headers
    except (ConnectionError, urllib.error.URLError) as e:
        return 0, {"error": {"code": "connection", "message": str(e)[:80]}}, {}


def mint(origin, api_key, agent, ops, projects):
    return post(origin + "/v1/agent-token", {"agentId": agent, "ops": ["history"], "channels": [], "ttlSec": 300,
                                             "collaboration": {"ops": ops, "projects": projects}}, {"authorization": "Bearer " + api_key})


# -- T0 ---------------------------------------------------------------------------

def t0():
    r = Results("t0")
    settings = json.loads(SPACES_FILE.read_text(encoding="utf-8"))
    r.check("S01", setup_spaces.validate(settings) == [], "spaces.json validates")

    def broken(change):
        copy = json.loads(json.dumps(settings))
        change(copy["spaces"][SPACE])
        return setup_spaces.validate(copy)
    caught = [broken(lambda s: s.pop("owner")), broken(lambda s: s["contributors"].append("nobody-agent")),
              broken(lambda s: s["contributors"].append(s["owner"])), broken(lambda s: s.update(decision_requesters=[]))]
    r.check("S02", all(caught), f"{sum(1 for c in caught if c)} of 4 broken files caught")

    sys.path.insert(0, str(PROXY.parent))
    import proxy
    person_only = {"project.create", "agent.verify", "decision.decide"}
    ours = set(proxy.OWNER_OPS + proxy.DECISION_OPS)
    detail, ok = "no person-only operation in any part", not (ours & person_only)
    r.check("S03", ok, detail)

    tool_md = (TOOL_DIR / "TOOL.md").read_text(encoding="utf-8")
    front, _, body = tool_md.partition("\n---\n")
    nevers = re.findall(r"^    - ([a-z-]+)$", front, re.M)
    enforcement = body.split("## Enforcement")[1].split("## Notes")[0]
    missing = [f["name"] for f in proxy.TOOLS if f"`{f['name']}`" not in body] + [n for n in nevers if f"| {n} |" not in enforcement]
    r.check("S04", not missing and len(nevers) >= 8, f"{len(proxy.TOOLS)} functions declared, {len(nevers)} never rules enforced; missing: {missing}")

    def one(env):
        agent = Agent(env.pop("OAA_AGENT_OVERRIDE", "virtual-cto"), env, r)
        answer = agent.call("spaces_list")
        agent.close()
        return answer
    ok, text = one({"CYBERPLEX_COLLAB_API_KEY": ""})
    r.check("S05", not ok and "data-source-unavailable" in str(text), text)
    ok, text = one({"CYBERPLEX_COLLAB_API_KEY": "k", "OAA_AGENT_OVERRIDE": ""})
    r.check("S06", not ok and "act-as-another-agent" in str(text), text)
    ok, text = one({"CYBERPLEX_COLLAB_API_KEY": "k", "CYBERPLEX_COLLAB_URL": "http://example.test"})
    r.check("S07", not ok and "expose-key-or-token" in str(text), text)
    ok, text = one({"CYBERPLEX_COLLAB_API_KEY": "k", "CYBERPLEX_COLLAB_URL": "", "COLLAB_SPACES_LOCAL": str(REPO / "no-such-file.json")})
    r.check("S08", ok and "expose-key-or-token" not in str(text), "an empty address (as a runner passes an unset variable) falls back to the default https address")
    scratch = REPO / ".test-work"
    scratch.mkdir(exist_ok=True)
    local = scratch / "retire-test.json"
    local.write_text(json.dumps({"projects": {SPACE: "old-project-id"}}), encoding="utf-8")
    done = subprocess.run([sys.executable, "-B", str(TOOL_DIR / "setup_spaces.py"), "--retire", SPACE, "new-project-id"],
                          capture_output=True, text=True, env={**os.environ, "COLLAB_SPACES_LOCAL": str(local)})
    after = json.loads(local.read_text(encoding="utf-8"))
    r.check("R01", done.returncode == 0 and after["projects"][SPACE] == "new-project-id" and after.get("retired", {}).get(SPACE) == ["old-project-id"], after)
    shutil.rmtree(scratch, ignore_errors=True)
    settings = json.loads(SPACES_FILE.read_text(encoding="utf-8"))
    r.check("G00", all(s.get("guide") for s in settings["spaces"].values()) and settings.get("dispatchers") == ["team-dispatcher"],
            "every space says what belongs in its document; one dispatcher is named")
    return r.finish()


# -- Shared cases (T1 and T2) --------------------------------------------------------

def leak_check(r, secrets):
    text = "".join(r.transcript)
    found = [name for name, value in secrets.items() if value and value in text]
    if TOKEN.search(text):
        found.append("a token")
    if '"fence"' in text:
        found.append("a fence")
    r.check("E01", not found, f"{len(r.transcript)} answers and log lines scanned; found: {found or 'nothing'}")


def stamp():
    return time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime())


# -- T2 ---------------------------------------------------------------------------

def t2(wait):
    r = Results("t2")
    setup_spaces.load_env()
    api_key = os.environ.get("CYBERPLEX_COLLAB_API_KEY", "").strip()
    local = Path(os.environ.get("COLLAB_SPACES_LOCAL") or REPO / "spaces.local.json")
    projects = json.loads(local.read_text(encoding="utf-8")).get("projects", {}) if local.is_file() else {}
    if not api_key:
        r.blocked("T2", "CYBERPLEX_COLLAB_API_KEY is not set: put your tenant key in .env (see README)")
        return r.finish()
    if SPACE not in projects:
        r.blocked("T2", f"no project id for {SPACE} in {local.name}: create the project in the workspace page and record its id (see README)")
        return r.finish()
    agents = []

    def run(name):
        agent = Agent(name, {}, r)
        agents.append(agent)
        return agent
    try:
        cto, pm, sec, arch = run("virtual-cto"), run("program-manager"), run("security-lead"), run("architect")
        ok, listing = cto.call("spaces_list")
        r.check("P01", ok and any(s["space"] == SPACE and s["your_part"] == "owner" and s.get("revision") for s in listing["spaces"]), listing if not ok else "owner of collab-test")
        if not ok or not any(s["space"] == SPACE and s.get("revision") for s in listing["spaces"]):
            r.blocked("T2", "the live space could not be read; stopping before any write")
            return r.finish()
        reads = [a.call("space_read", space=SPACE) for a in (cto, pm, arch)]
        r.check("L01", all(ok for ok, _ in reads), f"revision {reads[0][1].get('revision')}")
        text = f"Live test {stamp()} UTC: a contributor's suggestion."
        ok, _ = pm.call("space_propose", space=SPACE, text=text)
        _, doc = cto.call("space_read", space=SPACE)
        mine = [e for e in doc["entries"] if e["text"] == text]
        r.check("L02", ok and len(mine) == 1 and mine[0]["by"] == "program-manager" and mine[0]["status"] == "suggestion", mine)
        ok, answer = arch.call("space_propose", space=SPACE, text="A reader should not be able to add this.")
        r.check("L05", not ok and "act-beyond-your-part" in str(answer), answer)
        owners_words = [e for e in doc["entries"] if e["status"] in ("accepted", "verified") and e["by_kind"] == "human"]
        if not owners_words:
            r.blocked("L11", "the live document has no accepted entry: add one in the workspace page (Edit notebook, Add notebook entry, status Accepted) and run again")
        else:
            ok, rewritten = cto.call("space_write", space=SPACE, expected_revision=doc["revision"],
                                     entries=[{"text": e["text"], "status": e["status"]} for e in doc["entries"] if e["status"] in ("suggestion", "fact")][-5:])
            kept = [e for e in rewritten.get("entries", []) if e["status"] in ("accepted", "verified")] if ok else []
            r.check("L11", ok and [e["text"] for e in kept] == [e["text"] for e in owners_words], f"{len(kept)} owner entr(ies) kept through an agent rewrite" if ok else rewritten)
            _, doc = cto.call("space_read", space=SPACE)
        ok, answer = pm.call("space_write", space=SPACE, expected_revision=doc["revision"], objective="Rewritten by a contributor.")
        r.check("L07", not ok and "act-beyond-your-part" in str(answer), answer)
        ok, posted = pm.call("task_post", space=SPACE, objective=f"Live test {stamp()} UTC: confirm you can read this task.",
                             expected_result="One line saying so.", role=SECURITY_ROLE, deadline_hours=2)
        r.check("K01", ok and posted["state"] == "Available", posted)
        ok, claimed = sec.call("task_claim", space=SPACE, task_id=posted["task_id"]) if ok else (False, posted)
        r.check("K04", ok and claimed["assigned_to"] == "security-lead", claimed if not ok else "claimed")
        ok, done = sec.call("task_report", space=SPACE, task_id=posted["task_id"], state="completed", result_summary="Read and confirmed.") if ok else (False, claimed)
        r.check("K05", ok and done["state"] == "Completed" and bool(done.get("receipt")), done if not ok else "completed with a receipt")
        ask = dict(space=SPACE, action=f"Live test {stamp()} UTC: record that the tenant owner approved this test request. Nothing else happens.",
                   target="collab-test", action_revision="live-test-v1", options=["Approve the test", "Decline"], expires_hours=1)
        ok, answer = pm.call("decision_request", **ask)
        r.check("N01", not ok and "ask-the-owner-out-of-turn" in str(answer), answer)
        ok, asked = cto.call("decision_request", **ask)
        ok2, early = cto.call("decision_use", space=SPACE, decision_id=asked["decision_id"]) if ok else (False, asked)
        r.check("N02", ok and ok2 and early["authorized"] is False, early)
        if not ok:
            r.blocked("N03", "no request was made"); r.blocked("N04", "no request was made")
        elif not wait:
            r.blocked("N03", "--no-wait: the tenant owner's approval was not waited for"); r.blocked("N04", "same")
        else:
            print(f"\nWAITING for the tenant owner: open the workspace page, the collab-test project, Ask Architect,\n"
                  f"and choose 'Approve the test' on decision {asked['decision_id']}. Waiting up to 10 minutes.\n")
            state = "Pending"
            for _ in range(60):
                time.sleep(10)
                _, view = cto.call("decision_get", space=SPACE, decision_id=asked["decision_id"])
                state = view.get("state", "Pending") if isinstance(view, dict) else "Pending"
                if state != "Pending":
                    break
            if state == "Pending":
                r.blocked("N03", "the tenant owner did not decide within 10 minutes"); r.blocked("N04", "same")
            else:
                later = run("virtual-cto")
                ok3, used = later.call("decision_use", space=SPACE, decision_id=asked["decision_id"])
                r.check("N03", ok3 and used.get("authorized") is True and bool(used.get("use_receipt")), used if not ok3 else f"state {used['state']}")
                ok4, again = later.call("decision_use", space=SPACE, decision_id=asked["decision_id"])
                r.check("N04", ok3 and ok4 and again.get("use_receipt") == used.get("use_receipt"), "same receipt" if ok4 else again)
        # ---- Cases added to close the gaps (2026-11-12): reads, service-level refusals, and withdrawals ----
        pid, origin = projects[SPACE], os.environ.get("CYBERPLEX_COLLAB_URL", "").strip() or "https://cyberplex.cpe.net"
        status, issued, _ = mint(origin, api_key, "architect", ["project.get"], [pid])
        status2, refused, _ = post(origin + "/v1/collaboration/project.update", {"projectId": pid, "expectedRevision": doc["revision"], "title": "x", "objective": "x"},
                                   {"authorization": "Bearer " + issued.get("token", "")})
        r.check("L06", status == 200 and status2 == 403, f"token minted {status}; update answered {status2} {refused.get('error', {}).get('code')}")
        status, _, _ = mint(origin, api_key, "virtual-cto", ["project.get", "decision.decide"], [pid])
        r.check("L13", status >= 400, f"a token asking for decision.decide: {status}")
        ok, history = arch.call("space_history", space=SPACE, limit=50)
        r.check("L14", ok and "program-manager" in json.dumps(history), "history names the editors" if ok else history)
        ok, found = arch.call("directory_search", space=SPACE)
        r.check("D01", ok and any(a["agent"] == "security-lead" for a in found.get("agents", [])), [a["agent"] for a in found.get("agents", [])] if ok else found)
        ok, unwanted = pm.call("task_post", space=SPACE, objective=f"Live test {stamp()} UTC: a task that is withdrawn at once.", expected_result="Nothing.", role=SECURITY_ROLE, deadline_hours=1)
        ok2, gone = pm.call("task_cancel", space=SPACE, task_id=unwanted["task_id"], reason="Live test.") if ok else (False, unwanted)
        r.check("K09", ok and ok2 and gone["state"] == "Canceled", gone.get("state") if ok2 else gone)
        ok, waiting = sec.call("pending_work")
        r.check("K08", ok and not waiting.get("problems"), f"{len(waiting.get('waiting', []))} item(s) waiting for security-lead" if ok else waiting)
        ok, listing = arch.call("decision_list", space=SPACE)
        r.check("N08", ok and any(d["decision_id"] == asked.get("decision_id") for d in listing.get("decisions", [])), f"{len(listing.get('decisions', []))} request(s) listed" if ok else listing)
        ok, extra = cto.call("decision_request", space=SPACE, action=f"Live test {stamp()} UTC: a request that is withdrawn at once.", target="collab-test",
                             action_revision="live-test-v1", options=["Approve", "Decline"], expires_hours=1)
        ok2, withdrawn = cto.call("decision_cancel", space=SPACE, decision_id=extra["decision_id"]) if ok else (False, extra)
        r.check("N10", ok and ok2 and withdrawn["state"] == "Canceled", withdrawn.get("state") if ok2 else withdrawn)
        ok, packet = arch.call("space_handoff", space=SPACE)
        if ok and not packet.get("checkpoint_id"):
            cto.call("space_checkpoint", space=SPACE, label="Live test baseline")
            ok, packet = arch.call("space_handoff", space=SPACE)
        r.check("H01", ok and bool(packet.get("checkpoint_id")), f"checkpoint {packet.get('label')!r}, {len(packet.get('changes_since', []))} change(s) since" if ok else packet)

        leak_check(r, {"the tenant key": api_key})
    finally:
        for agent in agents:
            agent.close()
    return r.finish()


if __name__ == "__main__":
    level = sys.argv[1] if len(sys.argv) > 1 else ""
    if level == "t0":
        sys.exit(t0())
    if level == "t2":
        sys.exit(t2("--no-wait" not in sys.argv))
    print(__doc__)
    sys.exit(1)
