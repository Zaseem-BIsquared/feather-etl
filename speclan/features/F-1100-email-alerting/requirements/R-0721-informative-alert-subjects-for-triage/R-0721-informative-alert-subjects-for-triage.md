---
id: R-0721
type: requirement
title: Informative Alert Subjects for Triage
status: review
owner: speclan
created: "2026-04-10T05:00:25.311Z"
updated: "2026-04-10T05:00:25.311Z"
---
# Informative Alert Subjects for Triage

Every alert email includes a structured subject line that provides enough context for operators to assess and prioritize the alert without opening the email body. This enables rapid triage from inbox views, mobile notifications, and email filtering rules.

The subject line includes four key pieces of information: the severity level (clearly marked as CRITICAL, WARNING, or INFO), the tool or system name (identifying which pipeline deployment generated the alert), a concise description of the event that occurred, and the name of the affected table. This consistent structure allows operators to create email filters, set up mobile notification rules, and visually scan their inbox to find the most urgent items first. For example, an operator managing multiple pipeline deployments can immediately distinguish a critical failure on a revenue table from an informational schema change on a staging table.

## Acceptance Criteria

- [ ] Alert email subject lines include the severity level in a bracketed tag format (e.g., `[CRITICAL]`, `[WARNING]`, `[INFO]`)
- [ ] Alert email subject lines include the tool or pipeline name
- [ ] Alert email subject lines include a human-readable description of the event
- [ ] Alert email subject lines include the name of the affected table
- [ ] Subject lines follow a consistent ordering of these elements across all alert types
- [ ] Subject lines are suitable for use in email filtering rules (consistent, predictable format)
