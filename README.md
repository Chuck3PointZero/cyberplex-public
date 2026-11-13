# Shared spaces for a team of agents on Cyberplex

A small tool that lets a team of AI agents share work through [Cyberplex](https://cyberplex.cpe.net) collaboration projects: one shared document per project, tasks addressed to a role, and decisions that only the human tenant owner can make.

It is a **client** of the Cyberplex service, not part of it. You need a Cyberplex tenant with collaboration enabled.

## About OAA

This repository is written in OAA, the **Organizational Agent Architecture** ([github.com/Chuck3PointZero/OAA](https://github.com/Chuck3PointZero/OAA)): a way to structure a team of agents the way a company is structured. Agents fill roles, roles require skills, skills use tools, and each layer's limits compose downward. OAA is a skill (`org-agent-architecture`) that you install separately. This repository does not contain it.

- **Version.** The tree was compiled with OAA 0.8.0 (tag `v0.8.0`).
- **Install, in Claude Code.** Pin to that tag:

  ```bash
  /plugin marketplace add Chuck3PointZero/OAA@v0.8.0
  /plugin install organizational-agents@oaa
  ```

  OAA's own README suggests `@stable`. At the time of writing the `stable` tag still points at 0.7.0, which does not have the compile and validate utility this tree uses. OAA's README also lists installs for other agents.
- **Do you need it?** Only to validate or compile the tree. The two tools run without it.

## What is here

The agents, roles, skills and tools are an [OAA](https://github.com/Chuck3PointZero/OAA) tree under `oaa/`, one folder per node, laid out like the OAA companies they come from (see About OAA above).

| Path | What it is |
|---|---|
| `oaa/agents/` | The ten agents of a real team that runs on Cyberplex collaboration: the technology practice that looks after Cyberplex itself. Each `AGENT.md` is the **frontmatter only**: name, description and the role it fills. |
| `oaa/roles/` | The ten roles those agents fill. Each `ROLE.md` is the frontmatter only: what the role owns, may decide, must escalate and must never do (its `authority`), plus the skills it lists. |
| `oaa/skills/space-sync/` | The one skill published in full: the instructions an agent follows to use the tool in a run. |
| `oaa/tools/collab-space/` | The tool, published in full: an MCP server (`server/proxy/proxy.py`, Python standard library only), its declaration (`TOOL.md`) and its settings (`server/spaces.json`). |
| `oaa/tools/collab-space/setup_spaces.py` | Helper for the tenant owner: check the settings, print what to create, confirm the key and project ids work, retire a space. |
| `oaa/tools/team-channel/` | The messaging tool, published in full: an MCP server for posting and reading team messages on channels and sub-channels, with each agent's channels in `server/channels.json`. |
| `oaa/tools/*/` (the others) | Frontmatter only, for the other tools this team uses with collaboration. |
| `docs/deck/` | The deck: `shared-spaces-on-cyberplex.pdf` (25 slides), and its slide sources. It covers the idea, the demonstration, the workspace page, and the limits. |
| `tests/run_tests.py`, `tests/test_channels.py` | Static and live tests for the shared spaces, and live tests for the channels, against your own tenant. |

The instructions that follow the frontmatter in the real agent, role and tool files are not published, and neither is OAA itself, which is a skill you install separately. The tree is a picture of the team's structure, not a runnable company. The `collab-space` tool and the `space-sync` skill are complete. The server is a plain MCP server and works with any MCP client, without OAA.

## Working with the tree

OAA is a skill (`org-agent-architecture`), installed separately. This repository does not contain it. With the skill installed, point your agent at the `oaa/` folder and ask it to validate or compile the tree, for example "validate the OAA company in `oaa/`". The skill's own prompts do the work.

Validation checks that every `requires` path resolves to a node. The role files list skills this repository does not publish, so until those lines are removed from each `ROLE.md` and `role.json`, validation reports them as unresolved. With only `space-sync` listed, the tree validates.

## The model

A **space** is one Cyberplex collaboration project. Its notebook is one shared document.

| Part | Who | Can |
|---|---|---|
| Tenant owner | a person, in the Cyberplex workspace page | create spaces, write accepted and verified entries, decide requests, send tasks |
| Owner | exactly one agent per space | rewrite the document's agent-editable parts, save checkpoints |
| Contributor | a few agents | add one suggestion or question at a time, post tasks, claim and report tasks |
| Reader | other agents | read |

A statement moves from **suggestion** (a contributor) to **fact** (the owner agent) to **accepted** or **verified** (the tenant owner). No agent can change, remove or forge an accepted or verified entry.

Tasks are addressed to a role, not to an agent: the task names a required skill, and the agent that holds that skill claims it on its next run.

### What enforces what

Be clear about this before you rely on it.

- **Enforced by Cyberplex:** which projects a token can reach; that only a person creates projects, decides requests and writes accepted or verified entries; one worker per task; one use per approval.
- **Enforced by this tool, not by Cyberplex:** the split between owner and contributor. Cyberplex has a single notebook update operation. The tool is the only holder of the tenant key, and it gives each agent only the functions its part allows. A second program holding the same key is not bound by that.

## Set up

1. Copy `.env.example` to `.env` and put your tenant API key in it.
2. Edit `oaa/tools/collab-space/server/spaces.json`: your agents, their skills, your spaces, and who has which part. The file ships with the agents and spaces of a real team (see `oaa/agents/`): ten agents, seven working spaces and one test space, `collab-test`. Replace them with your own.
3. Check it, and print what to create:

   ```bash
   python oaa/tools/collab-space/setup_spaces.py --validate
   python oaa/tools/collab-space/setup_spaces.py --print
   ```

4. Create each project in the Cyberplex workspace page. Only the tenant owner can. The project id is in the address bar after `project=`.
5. Put the ids in `spaces.local.json` at the repository root:

   ```json
   {"projects": {"collab-test": "<project id>"}}
   ```

6. Confirm the key and ids work:

   ```bash
   python oaa/tools/collab-space/setup_spaces.py --check
   ```

`.env`, `spaces.local.json` and `.state/` are git-ignored. Do not commit them. To keep them out of the repository altogether, set `COLLAB_ENV_FILE`, `COLLAB_SPACES_LOCAL` and `COLLAB_STATE_DIR` to files elsewhere.

## Run the tool

Start `oaa/tools/collab-space/server/proxy/proxy.py` as an MCP server over stdio, with these in its environment:

| Variable | Meaning |
|---|---|
| `OAA_AGENT` | The calling agent's name, as listed in `spaces.json`. Set by your runner, never by the agent. |
| `CYBERPLEX_COLLAB_API_KEY` | The tenant key. |
| `CYBERPLEX_COLLAB_URL` | Optional. Default `https://cyberplex.cpe.net`. |
| `COLLAB_SPACES_LOCAL`, `COLLAB_STATE_DIR` | Optional. Where the project ids and the tool's per-agent state live. |

`oaa/tools/collab-space/server/mcp.json` is a ready launch entry. `TOOL.md` lists every function and every rule the tool enforces.

## Messages on channels

`team-channel` is the messaging half. A channel is a durable, ordered log: every reader gets every message, and each reader keeps its own read position, so it is a group queue where everyone gets a copy. For "exactly one agent takes this", use a task in a space instead.

Cyberplex has no channel tree. A **sub-channel** is a naming rule: `team` is the main channel, and `team-security`, `team-ops` and `team-delivery` share its prefix, so one token can be scoped to the whole family with `team-*`. Which agent is on which channel is one file, `oaa/tools/team-channel/server/channels.json`. Every function takes an optional `channel`; without it a call uses the agent's main channel. A channel that is not on the agent's list is refused by the tool, and the agent's token is not valid for it.

It needs its own key in `.env`, `CYBERPLEX_TEAM_API_KEY`, which is normally the same tenant key as `CYBERPLEX_COLLAB_API_KEY`. Read positions are saved in `oaa/agents/<agent>/memory/`, which is git-ignored, or under `TEAM_MEMORY_DIR`.

Use a channel for a message every listener should see and nobody must act on. Use a task when exactly one role must act and the result must be recorded, a document entry when it should still be true next week, and a decision request when the tenant owner must approve.

## Things to know

- **Nothing notifies anyone.** An agent calls `pending_work` at the start of a run. A dispatcher script can call `waiting_by_agent` to learn which agent to wake.
- **A document allows 180 edits in its life,** and holds 50 entries. Write once per run. `setup_spaces.py --retire` points a space at a successor project.
- **A claimed task must be finished in the same run.** The tool renews the lease while the run lasts; when the run ends the claim lapses.
- **An approval is not an action.** `decision_use` records one authorization. Carrying the action out is the agent's job.

## Tests

```bash
python tests/run_tests.py t0
python tests/run_tests.py t2
python tests/test_channels.py
```

`t0` needs nothing but Python. `t2` runs against your own tenant and the `collab-test` space, writes a few test records there, and waits for the tenant owner to approve one test request in the workspace page (`--no-wait` skips that).

## Licence

MIT. See `LICENSE`.
