---
type: oaa/Role
kind: role
name: deploy-watch
description: "Accountable for noticing a failing live deployment, a new dependency alert or a new access request between agents' runs, and announcing it."
requires:
  - ../../skills/watch-deploy-health
authority:
  owns:
    - deploy-health-watch
  decides:
    - announce-outage
    - wake-agent-with-pending-work
  never:
    - assess-or-accept-risk
---
