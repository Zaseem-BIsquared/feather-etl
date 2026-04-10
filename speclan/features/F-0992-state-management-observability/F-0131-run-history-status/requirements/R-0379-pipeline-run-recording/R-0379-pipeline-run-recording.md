---
id: R-0379
type: requirement
title: Pipeline Run Recording
status: review
owner: team
created: "2026-04-10T05:39:36.985Z"
updated: "2026-04-10T05:39:36.985Z"
---
# Pipeline Run Recording

Every pipeline execution is automatically recorded with complete operational context, giving operators a reliable audit trail of all pipeline activity. This ensures that no run goes untracked and that users can always determine what happened, when, and with what outcome.

Each recorded run captures a unique run identifier, the target table name, start and end timestamps, total duration, and a final status indicating success, failure, or skipped. Row-level metrics are also recorded, including counts of rows extracted, loaded, and skipped. When a run fails, the associated error message is preserved. Watermark values are tracked both before and after each run, allowing users to understand exactly what data range was processed. Any schema changes detected during the run are also noted in the record.

Run step details are recorded separately for each discrete phase of a pipeline execution, enabling users to pinpoint where in the pipeline a failure or slowdown occurred.

## Acceptance Criteria

- [ ] Each pipeline run produces a persistent record with a unique run identifier
- [ ] The run record includes the target table name and start/end timestamps
- [ ] The run record includes computed duration of the execution
- [ ] The run record captures final status as success, failure, or skipped
- [ ] Row counts for extracted, loaded, and skipped rows are recorded
- [ ] Error messages are preserved when a run fails
- [ ] Watermark values before and after the run are recorded
- [ ] Schema changes detected during the run are recorded
- [ ] Individual run steps are recorded with their own timing and status details
