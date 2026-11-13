#!/usr/bin/env python3
"""
Live test of the team channel and its sub-channels on your own tenant. No model is involved.

    python tests/test_channels.py        (from the repository root; needs .env, see README)

It shows that a channel is a group queue (every reader gets every message, each at its own read position),
that sub-channels are separate queues, and that an agent can only use the channels on its own list.
It publishes three short messages. Each agent is a real team-channel proxy process, started as the runner
starts it. Nothing here prints a key or a token.
"""

import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PROXY = REPO / "oaa" / "tools" / "team-channel" / "server" / "proxy" / "proxy.py"
MEMORY = REPO / ".test-work" / "team-memory"
RESULTS, TRANSCRIPT = [], []


def load_env():
    env_file = Path(os.environ.get("COLLAB_ENV_FILE") or REPO / ".env")   # set COLLAB_ENV_FILE to keep the key outside the repository
    if env_file.is_file():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                name, value = line.split("=", 1)
                os.environ.setdefault(name.strip(), value.strip().strip('"').strip("'"))
    os.environ["TEAM_MEMORY_DIR"] = str(MEMORY)


def call(agent, function, **arguments):
    request = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": function, "arguments": arguments}})
    done = subprocess.run([sys.executable, "-B", str(PROXY)], input=request + "\n", capture_output=True, text=True, encoding="utf-8",
                          cwd=REPO, env={**os.environ, "OAA_AGENT": agent}, timeout=90)
    TRANSCRIPT.extend([done.stdout, done.stderr])
    answer = json.loads(done.stdout.strip().splitlines()[-1])["result"]
    text = answer["content"][0]["text"]
    try:
        return not answer["isError"], json.loads(text)
    except ValueError:
        return not answer["isError"], text


def check(case, ok, detail=""):
    RESULTS.append({"id": case, "result": "pass" if ok else "FAIL", "detail": str(detail)[:300]})
    print(f"{'PASS' if ok else 'FAIL'}  {case}  {str(detail)[:160]}")


def http(method, url, bearer, body=None):
    request = urllib.request.Request(url, data=json.dumps(body).encode() if body is not None else None, method=method,
                                     headers={"authorization": "Bearer " + bearer, "content-type": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return response.status, json.loads(response.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        return e.code, {}


def subjects(page):
    return [m.get("data", {}).get("subject") for m in page.get("messages", [])] if isinstance(page, dict) else []


def main():
    load_env()
    key = os.environ.get("CYBERPLEX_TEAM_API_KEY", "").strip()
    if not key:
        print("BLOCKED: CYBERPLEX_TEAM_API_KEY is not set (put it in .env, see README)")
        return 2
    base = (os.environ.get("CYBERPLEX_TEAM_URL") or "https://cyberplex.cpe.net").rstrip("/")
    tag = time.strftime("%H%M%S", time.gmtime())
    main_subject, sub_subject, ops_subject = f"channel test {tag} main", f"channel test {tag} security", f"channel test {tag} ops"

    # Bring every reader up to date first, so the test sees only its own messages.
    for agent, channels in (("security-lead", ("team", "team-security")), ("program-manager", ("team", "team-delivery")), ("operations-manager", ("team", "team-ops", "team-security"))):
        for channel in channels:
            ok, page = call(agent, "read_new", channel=channel, limit=100)
            if ok and page.get("next_cursor"):
                call(agent, "mark_read", channel=channel, cursor=page["next_cursor"])

    ok, sent = call("virtual-cto", "post", type="info", subject=main_subject, body="To everyone on the main channel.")
    check("C01", ok and sent.get("channel") == "team", "the CTO posts on the main channel" if ok else sent)
    ok1, sec = call("security-lead", "read_new")
    ok2, pm = call("program-manager", "read_new")
    check("C02", ok1 and ok2 and main_subject in subjects(sec) and main_subject in subjects(pm),
          "group queue: two readers each received the same message")
    call("security-lead", "mark_read", cursor=sec["next_cursor"])
    _, sec_again = call("security-lead", "read_new")
    _, pm_again = call("program-manager", "read_new")
    check("C03", main_subject not in subjects(sec_again) and main_subject in subjects(pm_again),
          "own read positions: marked read for one reader, still unread for the other")
    call("program-manager", "mark_read", cursor=pm_again["next_cursor"])

    ok, sent = call("virtual-cto", "post", channel="team-security", type="info", subject=sub_subject, body="Only for the security sub-channel.")
    check("C04", ok and sent.get("channel") == "team-security", "the CTO posts on the team-security sub-channel" if ok else sent)
    _, sec_sub = call("security-lead", "read_new", channel="team-security")
    _, ops_sub = call("operations-manager", "read_new", channel="team-security")
    _, sec_main = call("security-lead", "read_new")
    check("C05", sub_subject in subjects(sec_sub) and sub_subject in subjects(ops_sub) and sub_subject not in subjects(sec_main),
          "sub-channel: both of its readers got the message, and it did not appear on the main channel")
    ok, refused = call("program-manager", "read_new", channel="team-security")
    ok_post, refused_post = call("program-manager", "post", channel="team-security", type="info", subject="should not arrive", body="x")
    check("C06", not ok and not ok_post and "use-channel-outside-allowlist" in str(refused) and "use-channel-outside-allowlist" in str(refused_post), refused)

    ok, sent = call("operations-manager", "post", channel="team-ops", type="status", subject=ops_subject, body="Only for the operations sub-channel.")
    _, cto_ops = call("virtual-cto", "read_new", channel="team-ops")
    _, sec_listing = call("security-lead", "read_new", channel="team-security")
    check("C07", ok and ops_subject in subjects(cto_ops) and ops_subject not in subjects(sec_listing),
          "a second sub-channel is a separate queue; the CTO, who is on every channel, reads it")

    # The service itself enforces the scope: a token for the delivery channels cannot read the security channel.
    status, issued = http("POST", base + "/v1/agent-token", key, {"agentId": "program-manager", "ops": ["history"], "channels": ["team", "team-delivery"], "ttlSec": 120})
    status2, _ = http("GET", base + "/v1/channels/team-security/messages?limit=1", issued.get("token", ""))
    status3, _ = http("GET", base + "/v1/channels/team/messages?limit=1", issued.get("token", ""))
    check("C08", status == 200 and status2 == 403 and status3 == 200, f"scoped token: team-security answered {status2}, team answered {status3}")
    # A prefix scope covers the whole family of sub-channels and nothing else.
    status, issued = http("POST", base + "/v1/agent-token", key, {"agentId": "virtual-cto", "ops": ["history"], "channels": ["team-*"], "ttlSec": 120})
    codes = {name: http("GET", f"{base}/v1/channels/{name}/messages?limit=1", issued.get("token", ""))[0] for name in ("team-security", "team-ops", "team-delivery", "team", "other")}
    check("C09", status == 200 and codes == {"team-security": 200, "team-ops": 200, "team-delivery": 200, "team": 403, "other": 403}, f"prefix token team-*: {codes}")

    ok, here = call("virtual-cto", "who_is_here", channel="team-security")
    names = {p.get("agentId") for p in here.get("presence", [])} if ok else set()
    check("C10", {"virtual-cto", "security-lead", "operations-manager"} <= names and "program-manager" not in names, sorted(names))

    text = "".join(TRANSCRIPT)
    leaked = [n for n, found in (("the tenant key", key in text), ("a token", bool(re.search(r"eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}", text)))) if found]
    check("C11", not leaked, f"{len(TRANSCRIPT)} answers and log lines scanned; found: {leaked or 'nothing'}")

    failed = sum(1 for r in RESULTS if r["result"] == "FAIL")
    out = REPO / "tests" / "results"
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"channels-{time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())}.json"
    path.write_text(json.dumps({"cases": RESULTS}, indent=2), encoding="utf-8")
    print(f"\nchannels: {len(RESULTS) - failed} passed, {failed} failed. Results: {path.relative_to(REPO)}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
