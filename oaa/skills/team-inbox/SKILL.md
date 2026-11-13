---
type: oaa/Skill
kind: skill
name: team-inbox
description: "Reads the team's messages on the Cyberplex team channel addressed to this agent, handles requests and handoffs within its own skills, and replies; posts no routine status."
allowed-tools:
  - ../../tools/team-channel/TOOL.md
authority:
  escalates:
    - data-source-unavailable
---

# Skill: Team Inbox

Reads the team's messages on the Cyberplex team channel addressed to this agent, handles requests and handoffs within its own skills, and replies; posts no routine status.
