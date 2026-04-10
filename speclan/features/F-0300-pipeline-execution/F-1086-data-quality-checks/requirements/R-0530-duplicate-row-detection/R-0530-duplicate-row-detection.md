---
id: R-0530
type: requirement
title: Duplicate Row Detection
status: review
owner: speclan
created: "2026-04-10T05:13:54.651Z"
updated: "2026-04-10T05:13:54.651Z"
---
# Duplicate Row Detection

Operators can configure duplicate row detection to identify exact duplicate rows in a loaded table. This capability catches problems where the same record has been ingested multiple times — due to extraction overlap, source system issues, or load retry scenarios — which can inflate aggregations, distort metrics, and cause incorrect analytical results.

When a duplicate check is configured for a table, the system examines all rows in the destination table after loading and identifies any rows that are exact duplicates across all columns. If duplicate rows are found, the check fails and reports the number of duplicate rows detected. This provides operators with a dataset-wide integrity assessment that complements column-level uniqueness checks.

This check evaluates entire rows for equality — it will only detect rows where every column value matches. For detecting duplicates based on specific key columns, operators should use the primary key duplicate detection capability or column-level uniqueness checks instead.

## Acceptance Criteria

- [ ] Operator can configure duplicate row detection on a per-table basis in YAML configuration
- [ ] The system identifies exact duplicate rows (matching across all columns) in the loaded table after each load
- [ ] A check result of "fail" is produced when any exact duplicate rows are found
- [ ] A check result of "pass" is produced when no exact duplicate rows exist
- [ ] The check result includes details about the number of duplicate rows detected
- [ ] No custom code is required — configuration alone defines the check
