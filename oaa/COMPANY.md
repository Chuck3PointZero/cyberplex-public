# Cyberplex Technology Team Company Map

<!-- GENERATED - do not hand-edit. Regenerate by running compile-company-map.prompt.md. -->

This document maps the OAA agent graph for human readers, so nobody has to open node files to see who owns what. Authority and accountability live at the role level: agents only fill roles, and every boundary below comes from a role's frontmatter.

## Role to Agent Mapping

| Agent | Role | Schedule |
|---|---|---|
| architect | principal-architect | (none) |
| deploy-sentinel | deploy-watch | (none) |
| eng-director | director-of-engineering | (none) |
| finops-lead | finops-manager | (none) |
| operations-manager | operations-manager | (none) |
| program-manager | engineering-program-manager | (none) |
| security-lead | head-of-security-and-reliability | (none) |
| software-engineer | software-engineer | (none) |
| team-dispatcher | work-dispatch | (none) |
| virtual-cto | chief-technology-officer | (none) |

## Roles

### chief-technology-officer

Accountable for the technology strategy and for every decision the virtual technology department makes. It owns `technology-strategy`, `technology-roadmap`, `architecture-approvals`, `work-approvals`, `executive-briefing`, `principal-daily-report`, `ai-operating-framework`. It decides `approve-architecture-decision-within-cto-approvable-bound`, `approve-work-within-tier-limit`, `accept-risk-within-cto-acceptable-bound`, `reject-incomplete-proposal`, `prioritize-within-approved-roadmap`, `draft-executive-briefing`, `publish-daily-report-to-principal`, `post-team-message`, `wake-teammate-for-pending-request`. It escalates to a human on `business-objective-change`, `budget-change`, `high-or-critical-risk-acceptance`, `vendor-commitment`, `people-decision`, `client-communication`, `production-architecture-change`, `decision-outside-authority`, `agent-permission-change`, `agent-reliability-concern`. It is never permitted to: `change-business-objectives`, `make-people-decisions`, `sign-vendor-contracts`, `modify-own-permissions`. It is implemented by the [daily-report](#daily-report), [decision-review](#decision-review), [roadmap-planning](#roadmap-planning), [space-sync](#space-sync) and [team-sync](#team-sync) skills, and is filled by the virtual-cto agent.

### deploy-watch

Accountable for noticing a failing live deployment, a new dependency alert or a new access request between agents' runs, and announcing it. It owns `deploy-health-watch`. It decides `announce-outage`, `wake-agent-with-pending-work`. It escalates to a human on . It is never permitted to: `assess-or-accept-risk`. It is implemented by the [watch-deploy-health](#watch-deploy-health) skill, and is filled by the deploy-sentinel agent.

### director-of-engineering

Accountable for knowing whether the engineering organization is delivering, and for surfacing the problems that need intervention. It owns `delivery-performance`, `engineering-standards-compliance`. It decides `publish-delivery-report`, `flag-blocked-work`, `comment-missing-acceptance-criteria`, `reply-to-team-message`. It escalates to a human on `plan-slip-detected`, `repeated-defect-pattern`. It is never permitted to: `assess-individual-performance`. It is implemented by the [delivery-report](#delivery-report), [space-sync](#space-sync) and [team-inbox](#team-inbox) skills, and is filled by the eng-director agent.

### engineering-program-manager

Accountable for turning approved decisions into managed, verified work within the engagement's execution limit. It owns `execution-plan`, `task-assignments`, `release-readiness`, `outcome-measurement`. It decides `create-tasks-from-approved-record`, `assign-within-execution-limit`, `request-review`, `verify-acceptance-criteria`, `post-team-message`, `wake-teammate-for-pending-request`. It escalates to a human on `unapproved-work-requested`, `work-blocked`, `release-candidate-ready`, `execution-limit-reached`. It is never permitted to: `start-work-without-approved-record`. It is implemented by the [space-sync](#space-sync), [task-decomposition](#task-decomposition) and [team-sync](#team-sync) skills, and is filled by the program-manager agent.

### finops-manager

Accountable for knowing what technology costs, against budget, and for modelling the cost of alternatives. It owns `technology-spend`, `budget-tracking`, `cost-models`. It decides `publish-spend-report`, `model-cost-scenarios`, `reply-to-team-message`. It escalates to a human on `cost-anomaly`, `budget-variance`. It is never permitted to: nothing beyond the hard limits of its tools. It is implemented by the [scenario-modeling](#scenario-modeling), [space-sync](#space-sync) and [team-inbox](#team-inbox) skills, and is filled by the finops-lead agent.

### head-of-security-and-reliability

Accountable for the risk register, incident analysis, and vulnerability management. It owns `risk-register`, `vulnerability-management`. It decides `open-or-update-risk-entry`, `propose-dependency-update-pr`, `reply-to-team-message`. It escalates to a human on `high-or-critical-risk`, `risk-acceptance`. It is never permitted to: `accept-risk`. It is implemented by the [space-sync](#space-sync), [team-inbox](#team-inbox) and [vulnerability-review](#vulnerability-review) skills, and is filled by the security-lead agent.

### operations-manager

Accountable for whether the deployed service is up and healthy, and for noticing and triaging the people who ask to use it; finds and prepares, never changes production. It owns `service-availability`, `operational-incidents`, `access-request-triage`, `role-mailbox-watch`, `operations-runbooks`. It decides `open-or-update-incident-record`, `classify-access-request`, `follow-up-on-outage`, `report-role-mail-to-owner`, `notify-owner-of-new-request`, `post-team-message`, `reply-to-team-message`. It escalates to a human on `sev1-or-sev2-outage`, `service-degradation-trend`, `suspected-abuse`. It is never permitted to: `change-production`, `contact-requesters`, `set-request-status`. It is implemented by the [operations-report](#operations-report), [space-sync](#space-sync) and [team-inbox](#team-inbox) skills, and is filled by the operations-manager agent.

### principal-architect

Accountable for knowing the client's architecture as it really is, for the technical debt inventory, and for proposing architecture decisions. It owns `architecture-baseline`, `architecture-decision-records`, `tech-debt-inventory`. It decides `update-architecture-baseline`, `rank-tech-debt-items`, `propose-architecture-decision`, `propose-work-for-approved-decision`, `reply-to-team-message`. It escalates to a human on `architecture-change-detected`, `undocumented-system-found`. It is never permitted to: nothing beyond the hard limits of its tools. It is implemented by the [adr-tracking](#adr-tracking), [decision-brief](#decision-brief), [space-sync](#space-sync), [team-inbox](#team-inbox) and [tech-debt-triage](#tech-debt-triage) skills, and is filled by the architect agent.

### software-engineer

Accountable for implementing one approved work record as a pull request on a vfcto/ branch, for a human to review and merge. It owns `implementation-branch`, `pull-request-for-approved-work`. It decides `create-vfcto-branch`, `commit-files-to-vfcto-branch`, `open-pull-request-for-review`, `post-handoff-to-program-manager`. It escalates to a human on `work-unclear`, `work-blocked`, `scope-exceeds-approved-record`, `needs-secret-or-configuration`. It is never permitted to: `start-work-without-approved-record`, `deploy-or-publish-to-live-service`, `change-live-demo-content`. It is implemented by the [implement-approved-work](#implement-approved-work) skill, and is filled by the software-engineer agent.

### work-dispatch

Accountable for getting each agent woken when work is waiting for it, so no agent waits for its next scheduled run. It owns `work-dispatch`. It decides `wake-agent-with-pending-work`. It escalates to a human on . It is never permitted to: `act-on-message-content`, `decide-or-approve-records`. It is implemented by the [dispatch-pending-work](#dispatch-pending-work) skill, and is filled by the team-dispatcher agent.

## Skills

Skills are the only place tools are invoked; no role or agent calls a tool directly. The workflow of each skill is not published; this map shows what each is for and which tools it may use.

#### adr-tracking

Tracks architecture decisions as records, proposes new ones to the CTO, and proposes the work to build each approved one. Tools: github-read, oaa-ontology.

#### daily-report

Sends the principal the CTO's daily report for this client, by Discord and by email: decisions made, escalations raised, and what needs the principal's attention. Tools: team-channel, oaa-ontology.

#### decision-brief

Prepares a decision brief: options, costs, risks, a recommendation, and its assumptions and uncertainty. Tools: oaa-ontology.

#### decision-review

Reviews every proposal routed to the CTO and approves it, rejects it, or escalates it to the right human; turns owner decisions that need work into a handoff. Tools: oaa-ontology, team-channel.

#### delivery-report

Produces the prioritized delivery report: what shipped, what is late or blocked, and which work lacks acceptance criteria. Tools: issue-reader, github-read, oaa-ontology.

#### dispatch-pending-work

Each tick, finds agents with pending work on the team channel, in the approval register, in GitHub issues, in the operations mail queue, in the website access-request queue, or in the shared spaces, and wakes them; never does the work itself. Tools: team-channel, issue-reader, access-requests, collab-space.

#### implement-approved-work

Turns one approved work record and its vfcto issues into a branch and a pull request for human review, and never merges. Tools: issue-reader, github-read, team-channel.

#### operations-report

Writes the daily operations report and posts it to the CTO on the team channel: uptime, incidents, sign-ups by state, days waiting. The CTO includes it in the daily report. Tools: oaa-ontology, team-channel.

#### roadmap-planning

Keeps the technology roadmap aligned with the client's stated business objectives and flags initiatives that have lost their justification. Tools: issue-reader, github-read, oaa-ontology.

#### scenario-modeling

Models the cost of alternative plans - budgets, vendors, or priorities - for decision briefs. Tools: spend-ledger.

#### space-sync

Works the team's shared spaces on Cyberplex: picks up tasks addressed to this agent's role, uses the tenant owner's answered decisions, and keeps the documents this agent owns or contributes to current. Tools: collab-space.

#### task-decomposition

Turns an approved decision into tracked tasks with acceptance criteria, within the engagement's execution limit. Tools: issue-reader, oaa-ontology, team-channel.

#### team-inbox

Reads the team's messages on the Cyberplex team channel addressed to this agent, handles requests and handoffs within its own skills, and replies; posts no routine status. Tools: team-channel.

#### team-sync

Reads and answers the team's messages on the Cyberplex team channel, posts a status when something changed, and wakes a teammate whose answer is needed before its next scheduled run. Tools: team-channel.

#### tech-debt-triage

Maintains a ranked technical debt inventory with the business impact of each item. Tools: github-read, issue-reader, oaa-ontology.

#### vulnerability-review

Reviews dependency and code-scanning alerts, and opens dependency-update pull requests for human review. Tools: github-read, oaa-ontology.

#### watch-deploy-health

Runs the live smoke test and health probe, checks Dependabot and access requests, announces an outage or degradation on the team channel and to the principal, and wakes the right agent. Tools: github-read, oaa-ontology, team-channel.

## Gaps

This section lists every gap-severity finding from the validation run that produced this document - undeclared territory the convention flags but does not forbid. Absence from this section is not a guarantee of completeness beyond what validation actually checked.

No gaps were found in the most recent validation run.
