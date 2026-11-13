---
type: oaa/Agent
kind: agent
name: team-dispatcher
description: "wakes agents that have work waiting on the team channel, in the register, or in GitHub issues."
executor: predicate
fills:
  - ../../roles/work-dispatch
enabled: true
---
