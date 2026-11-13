---
type: oaa/Tool
kind: tool
name: issue-reader
description: "Reads GitHub Issues on the Cyberplex repository and adds comments; cannot create, change, close, or delete any issue."
connector: mcp
auth: bearer
env: GITHUB_ISSUES_TOKEN
provenance:
  source: api.githubcopilot.com/mcp (GitHub's hosted MCP server, issues toolset)
  status: third-party
  proxy: server/proxy/proxy.py
concept-map: github-issues
authority:
  manages:
    - Initiative
    - WorkItem
  never:
    - create-or-change-work-items
    - delete-issues
    - close-issues
    - access-repository-outside-site-allowlist
---
