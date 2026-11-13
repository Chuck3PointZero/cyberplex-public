---
type: oaa/Skill
kind: skill
name: delivery-report
description: "Produces the prioritized delivery report: what shipped, what is late or blocked, and which work lacks acceptance criteria."
allowed-tools:
  - ../../tools/issue-reader/TOOL.md
  - ../../tools/github-read/TOOL.md
  - ../../tools/oaa-ontology/TOOL.md
authority:
  escalates:
    - data-source-unavailable
    - evidence-insufficient
---

# Skill: Delivery Report

Produces the prioritized delivery report: what shipped, what is late or blocked, and which work lacks acceptance criteria.
