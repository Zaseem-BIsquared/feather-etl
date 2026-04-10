---
id: R-0335
type: requirement
title: Linear Backoff Scheduling
status: review
owner: spec-agent
created: "2026-04-10T05:42:14.267Z"
updated: "2026-04-10T05:42:14.267Z"
---
# Linear Backoff Scheduling

After a table fails, the system computes a backoff period that determines the earliest time the table may be retried. The backoff duration increases linearly with each consecutive failure — 15 minutes per failure — up to a maximum cap of 120 minutes. This graduated approach gives transient issues time to resolve while ensuring that persistently failing tables do not remain in backoff indefinitely.

The backoff schedule is deterministic and predictable. Operators can easily calculate when a table will next be eligible for retry based on its failure count: multiply the count by 15 minutes, capped at 120 minutes. The "retry after" timestamp is set relative to the time of the most recent failure.

The backoff progression follows this pattern: 15 minutes after the first failure, 30 minutes after the second, 45 minutes after the third, and so on. Starting from the eighth consecutive failure, the backoff period remains fixed at 120 minutes regardless of additional failures.

## Acceptance Criteria

- [ ] Backoff duration equals the consecutive failure count multiplied by 15 minutes
- [ ] Backoff duration is capped at a maximum of 120 minutes
- [ ] The cap takes effect starting at the eighth consecutive failure
- [ ] The "retry after" timestamp is computed relative to the time of the most recent failure
- [ ] Backoff progression is linear: 15min, 30min, 45min, 60min, 75min, 90min, 105min, 120min
- [ ] The computed "retry after" timestamp is persisted for use in subsequent pipeline runs
