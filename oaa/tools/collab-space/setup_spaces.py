#!/usr/bin/env python3
"""
Owner helper for the collab-space tool. Not an agent tool.

    python oaa/tools/collab-space/setup_spaces.py --validate   check server/spaces.json (no network)
    python oaa/tools/collab-space/setup_spaces.py --print      what to create in the Cyberplex workspace page
    python oaa/tools/collab-space/setup_spaces.py --check      confirm the key and each project id work (reads only)
    python oaa/tools/collab-space/setup_spaces.py --retire <space> <new project id>
                                                           point a space at its successor project; the old id is kept
                                                           under "retired" in spaces.local.json. Create the successor
                                                           in the workspace page first, and have the owner agent save
                                                           a final checkpoint in the old one.

Agents cannot create a space: Cyberplex reserves that for the verified tenant owner. Create each space in
the workspace page (https://cyberplex.cpe.net/workspace/) with the title and objective printed by --print.
The project id is in the page's address bar after "project=". Put it in spaces.local.json at the repository root:

    {"projects": {"collab-test": "<project id>"}}

The key goes in .env at the repository root as CYBERPLEX_COLLAB_API_KEY. Both files are git-ignored.
To keep them outside the repository, set COLLAB_ENV_FILE, COLLAB_SPACES_LOCAL and COLLAB_STATE_DIR to files elsewhere.
Nothing here prints the key.
"""

import json
import os
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve()
REPO = HERE.parents[3]
SPACES_FILE = HERE.parent / "server" / "spaces.json"
PROXY = HERE.parent / "server" / "proxy" / "proxy.py"
NAME = re.compile(r"^[a-z0-9-]{1,40}$")
AGENT = re.compile(r"^[a-z0-9_-]{1,64}$")


def validate(settings):
    """Return a list of problems with a spaces.json. An empty list means it is sound."""
    problems = []
    agents, spaces = settings.get("agents"), settings.get("spaces")
    if not isinstance(agents, dict) or not agents:
        return ["agents: missing or empty"]
    if not isinstance(spaces, dict) or not spaces:
        return ["spaces: missing or empty"]
    if len(spaces) > 50:
        problems.append("spaces: Cyberplex allows 50 projects per tenant")
    for name, agent in agents.items():
        if not AGENT.match(name):
            problems.append(f"agent {name}: name must be lower-case letters, digits, - or _")
        skills = agent.get("skills")
        if not isinstance(skills, list) or not skills or len(skills) > 20 or not all(isinstance(s, str) and 0 < len(s) <= 80 for s in skills):
            problems.append(f"agent {name}: needs 1 to 20 skills of at most 80 characters")
        if len(str(agent.get("description", ""))) > 4000:
            problems.append(f"agent {name}: description over 4000 characters")
    for agent in settings.get("dispatchers", []):
        if agent not in agents:
            problems.append(f"dispatchers: {agent} is not listed under agents")
    for name, space in spaces.items():
        where = f"space {name}"
        if not NAME.match(name):
            problems.append(f"{where}: name must be lower-case letters, digits or -")
        if not 1 <= len(str(space.get("title", "")).strip()) <= 120:
            problems.append(f"{where}: title must be 1 to 120 characters")
        if not 1 <= len(str(space.get("objective", "")).strip()) <= 4000:
            problems.append(f"{where}: objective must be 1 to 4000 characters")
        if not 1 <= len(str(space.get("guide", "")).strip()) <= 1000:
            problems.append(f"{where}: needs a guide of 1 to 1000 characters saying what belongs in the document")
        owner = space.get("owner")
        if not isinstance(owner, str) or owner not in agents:
            problems.append(f"{where}: needs exactly one owner, an agent listed under agents")
        contributors = space.get("contributors", [])
        if not isinstance(contributors, list):
            problems.append(f"{where}: contributors must be a list")
            contributors = []
        if owner in contributors:
            problems.append(f"{where}: the owner is also listed as a contributor")
        if len(set(contributors)) != len(contributors):
            problems.append(f"{where}: a contributor is listed twice")
        readers = space.get("readers", [])
        named = contributors + ([] if readers == "*" else list(readers) if isinstance(readers, list) else [])
        if readers != "*" and not isinstance(readers, list):
            problems.append(f"{where}: readers must be a list or \"*\"")
        for agent in named + list(space.get("decision_requesters", [])):
            if agent not in agents:
                problems.append(f"{where}: {agent} is not listed under agents")
        for agent in space.get("decision_requesters", []):
            if agent != owner and agent not in contributors and readers != "*" and agent not in (readers or []):
                problems.append(f"{where}: {agent} may ask for decisions but has no part in the space")
        if not space.get("decision_requesters"):
            problems.append(f"{where}: nobody may ask the owner for a decision (decision_requesters is empty)")
    return problems


def load_env():
    env_file = Path(os.environ.get("COLLAB_ENV_FILE") or REPO / ".env")   # point COLLAB_ENV_FILE elsewhere to keep the key outside the repository
    if env_file.is_file():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                name, value = line.split("=", 1)
                os.environ.setdefault(name.strip(), value.strip().strip('"').strip("'"))


def call_tool(agent, function, arguments):
    """One call to the real MCP server, as an agent. Returns (ok, parsed-or-text)."""
    request = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": function, "arguments": arguments}})
    done = subprocess.run([sys.executable, str(PROXY)], input=request + "\n", capture_output=True, text=True, encoding="utf-8",
                          env={**os.environ, "OAA_AGENT": agent}, timeout=120)
    answer = json.loads(done.stdout.strip().splitlines()[-1])["result"]
    text = answer["content"][0]["text"]
    try:
        return not answer["isError"], json.loads(text)
    except ValueError:
        return not answer["isError"], text


def main():
    settings = json.loads(SPACES_FILE.read_text(encoding="utf-8"))
    mode = sys.argv[1] if len(sys.argv) > 1 else "--validate"
    problems = validate(settings)
    if problems:
        print("spaces.json has problems:")
        for problem in problems:
            print("  - " + problem)
        return 1
    if mode == "--validate":
        print(f"spaces.json is sound: {len(settings['spaces'])} spaces, {len(settings['agents'])} agents.")
        return 0
    if mode == "--print":
        print("Create each of these in the workspace page of your tenant, then put each project id (in the address bar,\n"
              "after project=) in spaces.local.json.\n")
        for name, space in settings["spaces"].items():
            others = ", ".join(space.get("contributors", [])) or "none"
            print(f"[{name}]\n  Title:     {space['title']}\n  Objective: {space['objective']}\n  (owner agent: {space['owner']}; contributors: {others})\n")
        return 0
    if mode == "--check":
        load_env()
        if not os.environ.get("CYBERPLEX_COLLAB_API_KEY", "").strip():
            print("BLOCKED: CYBERPLEX_COLLAB_API_KEY is not set (put it in .env at the repository root).")
            return 2
        local = REPO / "spaces.local.json"
        local = Path(os.environ.get("COLLAB_SPACES_LOCAL") or local)
        projects = json.loads(local.read_text(encoding="utf-8")).get("projects", {}) if local.is_file() else {}
        if not projects:
            print(f"BLOCKED: no project ids in {local.name}. Run --print, create a space, and record its id.")
            return 2
        failed = 0
        for name in settings["spaces"]:
            if name not in projects:
                print(f"  not set up   {name}")
                continue
            ok, answer = call_tool(settings["spaces"][name]["owner"], "space_read", {"space": name})
            if ok:
                print(f"  ok           {name}: revision {answer['revision']}, title {answer['title']!r}")
            else:
                failed += 1
                print(f"  FAILED       {name}: {answer}")
        return 1 if failed else 0
    if mode == "--retire":
        if len(sys.argv) != 4 or sys.argv[2] not in settings["spaces"] or not re.match(r"^[A-Za-z0-9_-]{1,100}$", sys.argv[3]):
            print("usage: --retire <space name from spaces.json> <new project id>")
            return 1
        name, new_id = sys.argv[2], sys.argv[3]
        local = Path(os.environ.get("COLLAB_SPACES_LOCAL") or REPO / "spaces.local.json")
        data = json.loads(local.read_text(encoding="utf-8")) if local.is_file() else {}
        old = data.setdefault("projects", {}).get(name)
        if old == new_id:
            print(f"{name} already points at {new_id}.")
            return 0
        if old:
            data.setdefault("retired", {}).setdefault(name, []).append(old)
        data["projects"][name] = new_id
        local.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        print(f"{name}: now {new_id}." + (f" Retired: {old} (still readable in the workspace page)." if old else ""))
        return 0
    print(__doc__)
    return 1


if __name__ == "__main__":
    sys.exit(main())
