---
id: R-0411
type: requirement
title: Append-Only Loading
status: review
owner: speclan
created: "2026-04-10T05:07:37.650Z"
updated: "2026-04-10T05:07:37.650Z"
---
# Append-Only Loading

Operators can load data into the destination database using an append-only strategy that inserts new rows without modifying or removing any existing data. This preserves the complete history of all records ever loaded, making it suitable for audit trails, compliance logs, and any dataset where regulatory or business requirements mandate full data retention.

When an append-only load executes, the incoming rows are inserted into the target table. No existing rows are deleted, updated, or overwritten under any circumstances. Each pipeline run adds its batch of records to the growing table, building a complete chronological record over time. The operation is atomic — either all rows from the batch are inserted, or none are.

If the target table does not yet exist when the first append-only load runs, the system automatically creates it based on the schema of the incoming data. Operators do not need to manually define table structures or run setup scripts before the first pipeline run. Subsequent runs append to the existing table.

## Acceptance Criteria

- [ ] Operator can configure a table to use the append-only loading strategy
- [ ] Append-only loads insert new rows without deleting, updating, or overwriting any existing rows
- [ ] Each pipeline run adds its batch of rows to the existing data in the target table
- [ ] The append operation executes as a single atomic transaction — either all rows are inserted or none are
- [ ] If the target table does not exist, it is automatically created on the first append-only load
- [ ] The auto-created table schema matches the structure of the incoming data
- [ ] Full history of all previously loaded rows is preserved across all pipeline runs
