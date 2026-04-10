---
id: R-0614
type: requirement
title: Primary Key Duplicate Detection
status: review
owner: speclan
created: "2026-04-10T05:14:02.480Z"
updated: "2026-04-10T05:14:02.480Z"
---
# Primary Key Duplicate Detection

When a table has a primary key configured, the system automatically checks for duplicate values in the primary key column(s) after each load — without requiring the operator to explicitly configure a separate quality check. This provides a built-in safety net for key-based data integrity that activates whenever primary key metadata is present in the table configuration.

Primary key duplicates are a particularly serious data quality issue because they indicate that the fundamental identity constraint of the dataset has been violated. This can cause incorrect joins, lost updates in incremental loads, and unpredictable behavior in downstream transformations and reports. By detecting these automatically, the system ensures that operators are alerted to key integrity problems even if they have not explicitly set up quality checks for the table.

This automatic check runs alongside any explicitly configured quality checks. If an operator has also configured a separate uniqueness check on the same column(s), both checks execute independently. The primary key duplicate check requires no additional configuration beyond having a primary key defined for the table.

## Acceptance Criteria

- [ ] The system automatically checks for duplicate primary key values when a table has a primary key configured
- [ ] No explicit quality check configuration is required — the check activates based on primary key metadata alone
- [ ] A check result of "fail" is produced when duplicate primary key values are found
- [ ] A check result of "pass" is produced when all primary key values are unique
- [ ] The check result includes details about the primary key column(s) checked and duplicates found
- [ ] The automatic primary key check runs alongside any explicitly configured quality checks without conflict
