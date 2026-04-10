---
id: R-0792
type: requirement
title: Backoff Skip Behavior
status: review
owner: spec-agent
created: "2026-04-10T05:42:22.776Z"
updated: "2026-04-10T05:42:22.776Z"
---
# Backoff Skip Behavior

When the pipeline runs and encounters a table that is still within its backoff window (the current time is earlier than the table's "retry after" timestamp), the table is skipped entirely. The system reports the table with a "skipped" status and includes an error message that references the original failure, giving operators clear visibility into why the table was not processed.

This skip behavior is the primary mechanism that protects source systems from being hammered by repeated failing requests. Instead of attempting extraction and failing again — potentially causing load on the source or triggering rate limits — the pipeline recognizes the table is in cooldown and bypasses it efficiently.

The skip is non-destructive: the table's existing failure count and backoff timestamp remain unchanged. The table will be retried automatically once its backoff window expires on a future pipeline run.

## Acceptance Criteria

- [ ] Tables with a "retry after" timestamp in the future are not extracted during the current run
- [ ] Skipped tables are reported with a "skipped" status in the run results
- [ ] The skip status message references the original failure that caused the backoff
- [ ] Skipping a table does not modify its failure count or backoff timestamp
- [ ] Skipped tables do not generate any requests against the source system
- [ ] The remaining tables in the pipeline continue to process normally when one table is skipped
