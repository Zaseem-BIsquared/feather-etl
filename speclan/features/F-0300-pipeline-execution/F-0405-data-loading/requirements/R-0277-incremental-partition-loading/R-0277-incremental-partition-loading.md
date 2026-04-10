---
id: R-0277
type: requirement
title: Incremental Partition Loading
status: review
owner: speclan
created: "2026-04-10T05:07:31.369Z"
updated: "2026-04-10T05:07:31.369Z"
---
# Incremental Partition Loading

Operators can load data into the destination database using an incremental partition overwrite strategy that refreshes only the time partitions affected by the incoming data. This enables efficient loading of large transactional tables where only recent records change between pipeline runs, avoiding the cost and time of rewriting the entire table.

When an incremental load executes, the system determines the earliest timestamp in the incoming batch and removes all existing rows in the target table from that timestamp forward. It then inserts the new rows, all within a single atomic transaction. This ensures that the affected partitions are cleanly replaced without gaps or duplicates, while all historical data before the batch boundary remains untouched.

This strategy is designed for large tables with time-series or transactional data patterns, where each pipeline run brings a batch of recent records. The partition boundary is determined automatically from the data — operators configure the timestamp column to use, and the system handles the rest. If the operation fails at any point, the target table remains in its previous state.

## Acceptance Criteria

- [ ] Operator can configure a table to use the incremental partition loading strategy
- [ ] The system removes existing rows at or after the earliest timestamp in the incoming batch before inserting new rows
- [ ] All historical data before the batch boundary remains untouched after an incremental load
- [ ] The delete-and-insert operation executes within a single atomic transaction
- [ ] If the incremental load fails or is interrupted, the target table remains in its previous state with no partial changes
- [ ] The partition boundary timestamp is determined automatically from the incoming data
- [ ] Operator can configure which timestamp column is used for partition boundary determination
