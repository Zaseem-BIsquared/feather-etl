---
id: R-0208
type: requirement
title: Automatic Retry Tracking on Table Failure
status: review
owner: spec-agent
created: "2026-04-10T05:42:06.956Z"
updated: "2026-04-10T05:42:06.956Z"
---
# Automatic Retry Tracking on Table Failure

When a table fails during extraction, the system automatically records the failure and increments a per-table failure counter. This counter persists across pipeline runs, enabling the system to track how many consecutive times a table has failed and to apply progressively longer backoff periods.

Operators do not need to manually intervene when a table encounters an error. The pipeline acknowledges the failure, updates the table's retry state, and moves on to process the remaining tables in the run. The failure counter provides a running history of consecutive failures that drives all downstream backoff behavior.

The failure counter is specific to each table and is only incremented when an extraction attempt actually occurs and fails — tables that are skipped due to an active backoff window do not have their counter incremented again.

## Acceptance Criteria

- [ ] When a table extraction fails, its consecutive failure count is incremented by one
- [ ] The failure count persists across separate pipeline runs
- [ ] The pipeline continues processing remaining tables after recording a failure
- [ ] Each table maintains its own independent failure counter
- [ ] Tables skipped due to active backoff do not have their failure counter incremented
- [ ] The failure count is visible in the table's watermark state for operational inspection
