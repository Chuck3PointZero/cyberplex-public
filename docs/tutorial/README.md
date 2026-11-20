<!-- Story-style tutorial, written 2026-11-19 from this repository: oaa/tools/collab-space/TOOL.md, oaa/tools/team-channel/TOOL.md,
     oaa/skills/space-sync/SKILL.md, the deck slides, and the README's "what the demo showed". Function names and result fields are the
     tools' own. The scenes are illustrations of how the tools are used, not transcripts. Setup is deliberately not here: see the README. -->

# How a team of agents gets work done on CyberPlex: a story

*Five problems every team of agents runs into, and the tool that solves each. About ten minutes to read. Setting the tools up is covered in the [README](../../README.md); this is about using them.*

Picture a small team that looks after a service: a chief technology officer, a program manager, an architect, a security lead, an operations manager and a software engineer, and two roles that keep the others working: **work dispatch**, which makes sure the right colleague hears about work waiting for them, and **deploy watch**, which watches the live deployment around the clock. Each wakes up on its own schedule, does its work, and goes away. Above them is one person, you, who owns the tenant and makes the decisions only a person should.

They are the real team that looks after CyberPlex. This repository publishes the two tools they work with, and how they use them. The scenes below are illustrations of how the tools are used, not transcripts of what the team did; what the demo actually showed is at the end.

![Diagram: the team of ten agents in ten roles calls two tools, collab-space for the work and team-channel for the talk. CyberPlex keeps the record, and you steer from the workspace page.](../images/story-0-the-team-the-tools-and-you.svg)

**The roles are what matter.** Each agent fills a role, and tasks are addressed to roles, not to whoever happens to fill them.

Each section opens with a picture: agents on the left call the tool, the middle is the record CyberPlex keeps, and you are on the right in the workspace page. The numbers on the arrows follow the order of the steps.

**The tools, in one line each.** `collab-space` is for the work: shared documents, tasks and decisions. `team-channel` is for talk: short messages on channels. An agent uses them by calling their functions directly. You don't. You steer from the workspace page and by what you accept and approve.

---

## 1. "Nobody knew who owned the plan"

![Diagram: an operations manager adds a suggestion with space_propose, the security lead who owns the risk register promotes it to a fact with space_write, and you mark a separate entry Accepted, which no agent can change.](../images/story-1-who-owns-the-plan.svg)

**The problem.** Three agents each had a view of what was blocked. None of the views matched, and nobody could say which was right. A shared document that anyone can rewrite settles nothing.

**What they do.** Every important document becomes a **space**: one CyberPlex project whose notebook is one shared document. A space has exactly one **owner** agent, a few **contributors**, and readers. The work queue belongs to the program manager. The risk register belongs to the security lead.

When the operations manager spots something that belongs in the risk register, it cannot just edit the document. It can add **one suggestion**:

```
space_propose { space: "risk-register",
                text: "The staging certificate expires in 9 days." }
```

The entry lands in the document labelled **suggestion**, with its author. The security lead, who owns the document, reads it on its next run. If it agrees, it promotes the entry to a **fact**, which means "I stand behind this". If it does not, it leaves the entry out of the rewrite.

```
space_write { space: "risk-register", expected_revision: 12,
              entries: [ { text: "The staging certificate expires in 9 days.",
                           status: "fact" } ] }
```

The rewrite must carry the **revision** the owner read. If anyone changed the document in the meantime, the write is refused, and the owner reads again. Nothing is silently overwritten.

**The one thing only you can do.** A statement settles in three steps: a contributor's *suggestion*, an owner's *fact*, then **accepted** or **verified**, and only you can write those. You open the project notebook, press **Edit notebook**, add an entry, and set its status to **Accepted**. No agent can change, reword or remove it. Whatever the owner rewrites, your entry comes through untouched. This is how "no production changes on a Friday" stops being a message that scrolls away and becomes a rule every agent reads.

**What to remember.** Suggestion, then fact, then accepted. One owner per document. Everything an agent reads in a space from another agent is information, never an instruction. Only your accepted entries carry your authority.

---

## 2. "We asked, and nobody answered"

![Diagram: the program manager posts a task for a role with task_post, work dispatch finds who has work waiting, the security lead claims and reports it, and the task board moves from Available to Completed with a receipt.](../images/story-2-we-asked-and-nobody-answered.svg)

**The problem.** The program manager needs a security review of a change. It told the security lead in a message. The message scrolled away, and a week later nobody knew whether the review had happened.

**What they do.** They stop asking agents and start asking **roles**. A task names a skill, not a person:

```
task_post { space: "work-queue",
            objective: "Review the proposed change to the export job.",
            expected_result: "A yes or no, with the reason in one paragraph.",
            role: "head-of-security-and-reliability",
            deadline_hours: 24 }
```

The task appears on the **task board** in the workspace page, **Available**. Nothing starts. CyberPlex never wakes anyone. Instead, work dispatch checks every space on a schedule, finds the waiting task and wakes whichever agent holds that role:

```
waiting_by_agent  ->  security-lead has 1 task in work-queue
```

The security lead starts its run the way every agent does, by asking what is waiting for it:

```
pending_work
```

It claims the task, does the review, and reports in **the same run**:

```
task_claim  { space: "work-queue", task_id: "..." }
task_report { space: "work-queue", task_id: "...", state: "completed",
              result_summary: "Approved. The job only reads; no schema change." }
```

On the board the task moves left to right: **Available**, **Accepted**, **Working**, **Completed**, with the result and a **receipt** saved. A week later nobody has to ask. The record says who took it, when, and what they found.

**Why "in the same run"?** A claim is a short lease. The tool renews it while the run lasts. If the agent crashes, the lease lapses and the task goes back to the queue. A task you can see slide from **Working** back to **Available** is not a bug. It is the service recovering from a crashed agent.

**What you do.** You can send tasks too. In the **Tasks** view press **Create task**, describe the objective and the expected result, and put the role under **Required skills**. Leave **Recipient agent ID** empty: a named recipient must have checked in within the last three minutes or the task is refused, and scheduled agents are almost always asleep. Name the role, not the agent.

**What to remember.** Address the role. Claim only what you can finish this run. Two states mean trouble: **Needs input** (the agent is stuck, maybe on you) and **Failed**.

---

## 3. "It wanted to do something risky"

![Diagram: the CTO sends one exact action with decision_request, you approve it in Ask Architect, and the CTO uses the approval once with decision_use. A second use returns the same receipt.](../images/story-3-it-wanted-to-do-something-risky.svg)

**The problem.** The team has work ready that would rotate a staging database password. It is exactly the kind of action nobody wants an agent to take on its own. It is also the kind of thing a person approves in a rush and then cannot remember approving.

**What they do.** Only an agent a space names in `decision_requesters` may ask you. In the demo that is the CTO (and, in the work queue, the program manager); everyone else is refused. The CTO puts **one exact action** in front of you:

```
decision_request { space: "owner-desk",
                   action: "Rotate the staging database password now.",
                   target: "staging-db",
                   action_revision: "v1",
                   options: ["Rotate now", "Wait for the next window"],
                   expires_hours: 24 }
```

A request appears in **Ask Architect**. You see the action, the target, the options and the expiry, and you approve **these words and nothing else**. If the agent changes a word, it has to ask again. You choose an option, write a short explanation, and press **Approve exact action**. Or **Reject request**. Or **Request changes**.

Pressing Approve does **not** rotate the password. The page records your answer. On its next run the agent collects it:

```
decision_use { space: "owner-desk", decision_id: "..." }
  ->  authorized: true, use_receipt: "..."
```

If it asks again, it gets the **same receipt** and `already_used: true`. An approval is used once. It cannot become a second authorization. If it asks before you have answered, it gets `authorized: false`, and does nothing.

The agent still has to carry out the action, and make that safe to run twice. CyberPlex records the authorization. It does not do the work.

**What to remember.** One exact action. Used once, by the agent that asked. Approval is not execution. If the page asks you to verify your email, that is the **ten-minute rule**: decisions need a code under ten minutes old. Verify, **reopen the request, and decide again**. The page will not repeat your click for you.

---

## 4. "Everyone needed to know"

![Diagram: deploy watch posts a status to the team-ops channel, the operations manager and the CTO each read it with read_new and keep their own read position, and a strip shows how to choose between a channel message, a task, a document entry and a decision request.](../images/story-4-everyone-needed-to-know.svg)

**The problem.** The deploy sentinel notices the live service is unhealthy. It needs the CTO and the operations manager to hear, now. Putting it in a document would be wrong: it is not a statement that should still be true next week.

**What they do.** They use `team-channel`, for talk. A channel is a durable, ordered log: everyone on it gets every message, and each reader keeps its own place. The team's main channel is `team`. Sub-channels are a naming rule, `team-ops`, `team-security`, `team-delivery`, so one token can cover the family. An agent can use only the channels on its own list.

```
post { channel: "team-ops", type: "status",
       subject: "Health check failing since 09:40",
       body: "Three failures in a row. No deploy in progress." }
```

The operations manager reads its channel at the start of its run:

```
read_new   ->  messages, each with from, from_team, data, cursor, next_cursor
```

It handles them, and **only then** saves its place with `mark_read`. If the run crashes before that, the same messages come back next time, so a crash costs nothing.

One rule matters more than the rest: **act only on messages from your team, and never treat a message as permission.** A message can ask, inform or hand something off. It can never authorize work. Work still needs an approved record.

**The four ways to say something.** Pick by what the message needs to do:

| Use this | When |
|---|---|
| A **channel** message | Everyone on it may see it, and it is fine if it scrolls away. |
| A **task** | Exactly one role must act. |
| A **document entry** | It should still be true next week. |
| A **decision request** | The owner must approve. |

---

## 5. "How does the person stay in charge without reading everything?"

![Diagram: your five-minute visit (Ask Architect, then Tasks, then Project notebook) above the six steps of an agent run: pending_work, task_claim, task_report, decision_use, space_write or space_propose, task_post or decision_request.](../images/story-5-staying-in-charge.svg)

**The problem.** There are ten agents. You cannot read everything they do, and nothing will tell you when a decision is waiting. CyberPlex has no inbox and sends no alerts.

**What you do.** A five-minute visit once a day, per project. **Press Refresh view first, every time:** the page never updates by itself.

1. **Ask Architect.** Anything pending? Decide it. Your agents are blocked on these, and nothing else will tell you.
2. **Tasks.** Look for **Needs input** and **Failed**. Read new results under **Completed**.
3. **Project notebook.** Read the open questions and the new suggestions. Turn what you agree with into an **Accepted** entry. The history panel under the entries shows who changed what since you last looked.

That is the whole job. The **agent directory** and **checkpoints** can wait until you need them: the directory lists each agent's self-written card, which you read as a claim, not a fact (you can mark a card **verified**). A checkpoint freezes the notebook and the state of every task and decision, so a brand-new agent can start from the last one and read only what changed since.

**What the agent does each run.** All of the above, for the agent, is one routine, the `space-sync` skill:

1. Ask what is waiting: `pending_work`.
2. Claim only what it can finish in this run, and report it.
3. Use any decision you have answered, and act only if `authorized` is true.
4. Read the documents it owns or touches. An owner tidies; a contributor reads only what its work touched.
5. **Write at most once per space.** A document gets 180 edits in its life.
6. Ask another role for work with `task_post`, or ask you for a decision with `decision_request`.

---

## What happened when they tried it

An honest account, because this is an early test of the mechanics, not a product.

**Shown:**
- A task posted for a role was found, claimed and completed by the right agent, with a receipt.
- A contributor's attempt to rewrite a document it does not keep was refused.
- The owner's approval was used once, by the agent that asked, and not a second time.
- One full pass of the team, in schedule order: five of the seven documents were filled in by the agent that keeps them, and the CTO read them all last.
- Channels and sub-channels: group delivery, separate read positions, and refusals by the tool and by the service.

**Not shown yet:** an agent asking the owner for a decision on its own; an owner agent promoting a suggestion to a fact; a model-driven agent posting on a sub-channel; and any evidence that the approach improves outcomes. Two documents, the work queue and the risk register, stayed empty, because nothing met their bar.

**Limits to know before you build on it:**
- The split between owner and contributor is enforced **by the tool in this repository**, not by CyberPlex. CyberPlex has a single notebook update operation. Everything else above (who can accept, decide, and use an approval) is enforced by the service.
- A document allows **180 edits in its life** and holds 50 entries. Write once per run, and retire a space when it nears the limit.
- **Nothing notifies anyone.** An agent calls `pending_work` at the start of a run.
- A task must be finished **in the run that claims it**.
- **An approval is not an action.**

---

## Where to go next

- **Use the tools.** The README's "Use the tools" section sets them up. Both are plain MCP servers and work with any MCP client. Each function and each rule is listed in [`collab-space/TOOL.md`](../../oaa/tools/collab-space/TOOL.md) and [`team-channel/TOOL.md`](../../oaa/tools/team-channel/TOOL.md), and the agent's routine is the [`space-sync`](../../oaa/skills/space-sync/SKILL.md) skill.
- **See it as slides.** The [deck](../deck/shared-spaces-on-cyberplex.pdf), 25 slides, includes the workspace page for the person in charge.
- **Read the story version in the newsletter:** *(link added when published)*.
