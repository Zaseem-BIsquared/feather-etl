---
id: R-0133
type: requirement
title: Full Replacement Loading
status: review
owner: speclan
created: "2026-04-10T05:07:22.660Z"
updated: "2026-04-10T05:07:22.660Z"
---
# Full Replacement Loading

Operators can load data into the destination database using a full replacement strategy that atomically swaps the entire contents of a target table with new data. This ensures that reference tables, lookup data, and other small datasets always reflect the most recent extraction without risk of partial updates or data corruption.

When a full replacement load executes, the system creates a new version of the target table with the incoming data, then atomically replaces the existing table with the new version. If the operation is interrupted at any point before the final swap, the original table remains intact and unchanged. After a successful load, only the newly loaded data exists in the target table — no rows from previous runs are retained.

This strategy is appropriate for tables where the complete dataset is small enough to be replaced on every run and where historical versions within the destination are not required. Operators select this strategy through pipeline configuration on a per-table basis.

## Acceptance Criteria

- [ ] Operator can configure a table to use the full replacement loading strategy
- [ ] A full replacement load atomically replaces all existing rows in the target table with the new data
- [ ] If the load operation fails or is interrupted, the original table data remains intact and unchanged
- [ ] No rows from previous pipeline runs remain in the target table after a successful full replacement load
- [ ] The full replacement strategy is selectable independently for each table in the pipeline configuration
- [ ] The loading operation completes as a single atomic transaction — downstream consumers never see a partially loaded table
