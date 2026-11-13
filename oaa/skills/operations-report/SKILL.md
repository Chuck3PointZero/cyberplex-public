---
type: oaa/Skill
kind: skill
name: operations-report
description: "Writes the daily operations report and posts it to the CTO on the team channel: uptime, incidents, sign-ups by state, days waiting. The CTO includes it in the daily report."
allowed-tools:
  - ../../tools/oaa-ontology/TOOL.md
  - ../../tools/team-channel/TOOL.md
authority:
  escalates:
    - evidence-insufficient
---

# Skill: Operations Report

Writes the daily operations report and posts it to the CTO on the team channel: uptime, incidents, sign-ups by state, days waiting. The CTO includes it in the daily report.
