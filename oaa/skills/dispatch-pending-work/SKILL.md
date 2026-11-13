---
type: oaa/Skill
kind: skill
name: dispatch-pending-work
description: "Each tick, finds agents with pending work on the team channel, in the approval register, in GitHub issues, in the operations mail queue, in the website access-request queue, or in the shared spaces, and wakes them; never does the work itself."
allowed-tools:
  - ../../tools/team-channel/TOOL.md
  - ../../tools/issue-reader/TOOL.md
  - ../../tools/access-requests/TOOL.md
  - ../../tools/collab-space/TOOL.md
---

# Skill: Dispatch Pending Work

Each tick, finds agents with pending work on the team channel, in the approval register, in GitHub issues, in the operations mail queue, in the website access-request queue, or in the shared spaces, and wakes them; never does the work itself.
