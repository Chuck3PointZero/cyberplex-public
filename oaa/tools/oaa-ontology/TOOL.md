---
type: oaa/Tool
kind: tool
name: oaa-ontology
description: "The site's shared memory - the OAA ontology compiler and SQLite entity store that skills write to and query derived concepts from."
connector: mcp
provenance:
  source: github.com/Chuck3PointZero/OAA (ontology server)
  status: first-party
  proxy: server/proxy/proxy.py
authority:
  never:
    - use-store-outside-site
    - rewrite-ontology-artifacts
---
