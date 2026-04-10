---
id: R-2047
type: requirement
title: Non-Blocking Pipeline Continuation
status: review
owner: speclan
created: "2026-04-10T05:18:31.176Z"
updated: "2026-04-10T05:18:31.176Z"
---
# Non-Blocking Pipeline Continuation

Schema drift detection is purely an observability mechanism — it never blocks the pipeline, halts data processing, or prevents data from being loaded into the destination. Regardless of the type or severity of drift detected, the pipeline always continues to completion. This design ensures that data availability is never interrupted by upstream schema changes.

Operators benefit from this non-blocking approach because their downstream consumers, reports, and dashboards continue to receive fresh data even when the source schema is evolving. Drift notifications provide awareness and enable proactive response, but the pipeline does not wait for operator acknowledgment or approval before proceeding.

Even when critical drift is detected — such as data type changes that result in some rows being quarantined — the pipeline continues processing all remaining data and tables. The quarantine mechanism ensures that problematic rows are safely set aside without affecting the rest of the load, and operators can address quarantined data on their own timeline.

## Acceptance Criteria

- [ ] The pipeline continues to completion regardless of any schema drift detected
- [ ] Added column drift does not pause or halt the pipeline
- [ ] Removed column drift does not pause or halt the pipeline
- [ ] Type-changed column drift does not pause or halt the pipeline
- [ ] Quarantined rows from type conversion failures do not block the loading of other rows
- [ ] Drift detection operates as an observability layer that produces reports without gating data flow
