---
type: oaa/Tool
kind: tool
name: github-read
description: "Read-only access to the client's GitHub repositories, pull requests, workflow runs, and security alerts."
connector: mcp
auth: bearer
env: GITHUB_READ_TOKEN
provenance:
  source: api.githubcopilot.com/mcp (GitHub's hosted MCP server)
  status: third-party
  proxy: server/proxy/proxy.py
concept-map: github
authority:
  manages:
    - Repository
    - Vulnerability
    - Deployment
  never:
    - read-secrets
    - access-repository-outside-site-allowlist
---
