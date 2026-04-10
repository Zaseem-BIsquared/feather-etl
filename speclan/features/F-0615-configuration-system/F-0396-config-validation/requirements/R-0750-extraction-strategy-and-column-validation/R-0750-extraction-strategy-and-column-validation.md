---
id: R-0750
type: requirement
title: Extraction Strategy and Column Validation
status: review
owner: speclan
created: "2026-04-10T05:36:37.089Z"
updated: "2026-04-10T05:36:37.089Z"
---
# Extraction Strategy and Column Validation

Operators are informed when their table extraction strategies are invalid, when required supporting columns are missing, when deduplication settings conflict, or when numeric parameters are out of range. This prevents runtime failures and data integrity issues caused by incompatible strategy-column combinations.

The validation process checks each table's extraction strategy against the list of valid strategies (full, incremental, and append). Tables configured for incremental or append extraction are further checked to ensure they specify a `timestamp_column`, which is required for those strategies to determine what data is new. The system also enforces that the `dedup` flag and explicit `dedup_columns` list are not both specified on the same table, since these are mutually exclusive approaches to deduplication. Finally, the `overlap_window_minutes` parameter, if present, must be a non-negative number.

Each violation produces a specific error message identifying the table and the exact problem, so operators can fix all strategy and column issues in one editing pass.

## Acceptance Criteria

- [ ] Operator receives an error when a table specifies an extraction strategy other than full, incremental, or append
- [ ] Operator receives an error when an incremental table does not specify a timestamp column
- [ ] Operator receives an error when an append table does not specify a timestamp column
- [ ] Operator receives an error when a table specifies both the dedup flag and explicit dedup columns
- [ ] Operator receives an error when overlap_window_minutes is a negative number
- [ ] Error messages identify the specific table and the exact rule violation
- [ ] All strategy and column errors are reported together in a single validation run
