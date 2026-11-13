---
type: oaa/Skill
kind: skill
name: daily-report
description: "Sends the principal the CTO's daily report for this client, by Discord and by email: decisions made, escalations raised, and what needs the principal's attention."
allowed-tools:
  - ../../tools/team-channel/TOOL.md
  - ../../tools/oaa-ontology/TOOL.md
authority:
  escalates:
    - data-source-unavailable
---

# Skill: Daily Report

Sends the principal the CTO's daily report for this client, by Discord and by email: decisions made, escalations raised, and what needs the principal's attention.


