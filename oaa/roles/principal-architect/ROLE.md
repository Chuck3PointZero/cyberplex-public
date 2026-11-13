---
type: oaa/Role
kind: role
name: principal-architect
description: "Accountable for knowing the client's architecture as it really is, for the technical debt inventory, and for proposing architecture decisions."
requires:
#  - ../../skills/baseline-assessment
#  - ../../skills/repo-analysis
  - ../../skills/tech-debt-triage
  - ../../skills/adr-tracking
#  - ../../skills/migration-readiness
  - ../../skills/decision-brief
  - ../../skills/team-inbox
  - ../../skills/space-sync
authority:
  owns:
    - architecture-baseline
    - architecture-decision-records
    - tech-debt-inventory
  decides:
    - update-architecture-baseline
    - rank-tech-debt-items
    - propose-architecture-decision
    - propose-work-for-approved-decision
    - reply-to-team-message
  escalates:
    - architecture-change-detected
    - undocumented-system-found
---
