---
type: oaa/Agent
kind: agent
name: deploy-sentinel
description: "runs the live smoke test and checks Dependabot; wakes the security lead only on a failure or a new alert."
executor: predicate
fills:
  - ../../roles/deploy-watch
enabled: true
---
