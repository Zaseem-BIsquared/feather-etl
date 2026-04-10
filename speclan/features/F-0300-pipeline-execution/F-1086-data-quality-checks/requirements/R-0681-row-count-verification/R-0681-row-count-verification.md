---
id: R-0681
type: requirement
title: Row Count Verification
status: review
owner: speclan
created: "2026-04-10T05:14:15.292Z"
updated: "2026-04-10T05:14:15.292Z"
---
# Row Count Verification

The system automatically verifies the row count of every loaded table after each pipeline run, regardless of whether the operator has configured any explicit quality checks for that table. This always-on safeguard ensures that operators are immediately alerted when a load produces zero rows — a condition that typically indicates an upstream problem such as a failed extraction, an empty source table, a misconfigured filter, or a connectivity issue.

Row count verification requires no configuration and cannot be disabled. It runs for every table on every pipeline execution as a baseline data quality guarantee. When the loaded table contains zero rows, the system produces a warning-level result rather than a failure, reflecting that an empty result may occasionally be legitimate but warrants operator attention. When the table contains one or more rows, the check passes and records the actual row count for operational visibility.

This check serves as a first line of defense that catches the most obvious data pipeline failures — the complete absence of data — even for tables where operators have not yet invested in configuring more detailed quality checks.

## Acceptance Criteria

- [ ] The system automatically checks the row count of every loaded table after each pipeline run
- [ ] No explicit configuration is required — the row count check runs for all tables unconditionally
- [ ] A check result of "warn" is produced when the loaded table contains zero rows
- [ ] A check result of "pass" is produced when the loaded table contains one or more rows
- [ ] The check result includes the actual row count loaded
- [ ] The row count check runs even when no other quality checks are configured for the table
