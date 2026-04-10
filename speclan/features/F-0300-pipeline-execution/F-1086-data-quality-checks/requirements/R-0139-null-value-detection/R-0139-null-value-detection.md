---
id: R-0139
type: requirement
title: Null Value Detection
status: review
owner: speclan
created: "2026-04-10T05:13:40.086Z"
updated: "2026-04-10T05:13:40.086Z"
---
# Null Value Detection

Operators can configure per-column null value checks to ensure that critical data fields are fully populated after each load. This capability helps catch upstream data issues — such as missing mandatory fields, broken source mappings, or incomplete extractions — before they propagate into downstream analytics and reporting where they can cause silent calculation errors or misleading results.

When a not-null check is configured for one or more columns on a table, the system examines every row in the loaded data for null values in those columns after each pipeline run. If any nulls are found, the check fails and reports which columns contain null values and how many null entries were detected. Operators can configure not-null checks for any number of columns on a single table, and each column is evaluated independently — a null found in one column does not prevent other columns from being checked.

The not-null check validates data as it exists in the local destination table after loading, ensuring the check reflects the actual state of data available to downstream consumers rather than the raw source.

## Acceptance Criteria

- [ ] Operator can configure one or more columns for null value detection on a per-table basis in YAML configuration
- [ ] The system checks every row in the specified columns for null values after each load
- [ ] A check result of "fail" is produced when any null values are found in a checked column
- [ ] A check result of "pass" is produced when no null values are found in a checked column
- [ ] Each column configured for null checking is evaluated independently
- [ ] The check result includes details identifying which column was checked and the number of null values found
- [ ] No custom code is required — configuration alone defines the check
