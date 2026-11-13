---
type: oaa/Tool
kind: tool
name: access-requests
description: "Reads the website's new access-request announcements from the operator tenant's `access-requests` channel; read-only, one fixed channel, every request returned as untrusted, no email addresses or free text."
connector: local
auth: bearer
provenance:
  source: local
  status: first-party
  vendored: server/proxy/proxy.py
authority:
  manages: []
  never:
    - publish-to-access-requests
    - read-outside-access-requests
    - read-requester-contact-details
    - expose-api-key
    - move-cursor-backward-or-unseen
    - read-as-another-agent
---
