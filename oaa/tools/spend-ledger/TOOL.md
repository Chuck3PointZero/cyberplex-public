---
type: oaa/Tool
kind: tool
name: spend-ledger
description: "Read-only access to the practice manager's spend ledger - cost lines, budgets, and vendors for this client."
connector: local
auth: none
provenance:
  source: local
  status: first-party
  vendored: server/index.ts
concept-map: spend-ledger
authority:
  manages:
    - CostLine
    - Budget
    - Vendor
  never:
    - write-ledger
---
