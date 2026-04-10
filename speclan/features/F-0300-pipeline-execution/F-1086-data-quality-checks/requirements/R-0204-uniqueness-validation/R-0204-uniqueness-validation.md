---
id: R-0204
type: requirement
title: Uniqueness Validation
status: review
owner: speclan
created: "2026-04-10T05:13:47.597Z"
updated: "2026-04-10T05:13:47.597Z"
---
# Uniqueness Validation

Operators can configure uniqueness checks on specific columns to verify that values expected to be distinct — such as identifiers, codes, or natural keys — contain no duplicates after each load. This capability detects data integrity problems like accidental duplicate ingestion, source system issues producing repeated identifiers, or extraction logic that inadvertently pulls overlapping record sets.

When a uniqueness check is configured for a column, the system examines the loaded data in the destination table and identifies any values that appear more than once in that column. If duplicate values are found, the check fails and reports the column name along with details about the duplicates detected. Operators can configure uniqueness checks on multiple columns for a single table, and each column is evaluated independently.

This check is distinct from duplicate row detection — uniqueness validation focuses on a single column's values rather than entire row equality. It is particularly valuable for columns that serve as business identifiers or natural keys where duplicates would indicate a data integrity issue.

## Acceptance Criteria

- [ ] Operator can configure one or more columns for uniqueness validation on a per-table basis in YAML configuration
- [ ] The system identifies duplicate values within each specified column after each load
- [ ] A check result of "fail" is produced when any duplicate values exist in a checked column
- [ ] A check result of "pass" is produced when all values in a checked column are unique
- [ ] Each column configured for uniqueness checking is evaluated independently
- [ ] The check result includes details identifying which column was checked and information about the duplicates found
- [ ] No custom code is required — configuration alone defines the check
