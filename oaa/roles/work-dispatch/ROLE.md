---
type: oaa/Role
kind: role
name: work-dispatch
description: "Accountable for getting each agent woken when work is waiting for it, so no agent waits for its next scheduled run."
requires:
  - ../../skills/dispatch-pending-work
authority:
  owns:
    - work-dispatch
  decides:
    - wake-agent-with-pending-work
  never:
    - act-on-message-content
    - decide-or-approve-records
---
