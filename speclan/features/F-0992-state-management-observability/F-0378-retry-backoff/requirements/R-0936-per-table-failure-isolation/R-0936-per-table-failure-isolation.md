---
id: R-0936
type: requirement
title: Per-Table Failure Isolation
status: review
owner: spec-agent
created: "2026-04-10T05:42:37.938Z"
updated: "2026-04-10T05:42:37.938Z"
---
# Per-Table Failure Isolation

Each table's retry and backoff state is completely independent from every other table in the pipeline. A failure in one table has no effect on the extraction schedule, backoff state, or processing of any other table. This isolation guarantee ensures that the blast radius of any single table's problems is strictly contained.

Operators can rely on the fact that a problematic table — even one that fails repeatedly and reaches the maximum backoff cap — will never cause delays, skips, or failures in other tables. The pipeline processes each table on its own merits: healthy tables continue on schedule, while failing tables independently enter and exit their backoff periods.

This isolation applies to all aspects of retry state: failure counts, backoff timestamps, skip decisions, and recovery resets are all scoped to individual tables. There is no shared retry budget, no global failure threshold, and no cross-table dependency in backoff calculations.

## Acceptance Criteria

- [ ] A table entering backoff does not affect the extraction schedule of any other table
- [ ] A table's failure count is independent and not shared with other tables
- [ ] Multiple tables can be in different stages of backoff simultaneously
- [ ] A table recovering from backoff does not influence the state of other tables in backoff
- [ ] The pipeline processes all non-backoff tables normally even when some tables are in backoff
- [ ] There is no global failure threshold that affects tables collectively
