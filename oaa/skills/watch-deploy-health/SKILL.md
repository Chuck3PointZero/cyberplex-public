---
type: oaa/Skill
kind: skill
name: watch-deploy-health
description: "Runs the live smoke test and health probe, checks Dependabot and access requests, announces an outage or degradation on the team channel and to the principal, and wakes the right agent."
allowed-tools:
  - ../../tools/github-read/TOOL.md
  - ../../tools/oaa-ontology/TOOL.md
  - ../../tools/team-channel/TOOL.md
authority:
  escalates:
    - data-source-unavailable
---

# Skill: Watch Deploy Health

Runs the live smoke test and health probe, checks Dependabot and access requests, announces an outage or degradation on the team channel and to the principal, and wakes the right agent.
