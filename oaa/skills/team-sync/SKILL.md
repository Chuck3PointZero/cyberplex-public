---
type: oaa/Skill
kind: skill
name: team-sync
description: "Reads and answers the team's messages on the Cyberplex team channel, posts a status when something changed, and wakes a teammate whose answer is needed before its next scheduled run."
allowed-tools:
  - ../../tools/team-channel/TOOL.md
authority:
  escalates:
    - data-source-unavailable
    - evidence-insufficient
---

# Skill: Team Sync

Reads and answers the team's messages on the Cyberplex team channel, posts a status when something changed, and wakes a teammate whose answer is needed before its next scheduled run.
