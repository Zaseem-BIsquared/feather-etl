---
id: R-0302
type: requirement
title: Automatic Schema Baseline Capture
status: review
owner: speclan
created: "2026-04-10T05:17:47.991Z"
updated: "2026-04-10T05:17:47.991Z"
---
# Automatic Schema Baseline Capture

The system automatically captures and stores the source schema as a baseline snapshot when a table is extracted for the first time. This eliminates any manual schema registration step and ensures that drift detection is immediately active for every table in the pipeline without additional operator configuration.

On the initial extraction of a table, the system records the complete column inventory — including column names and their data types — as the baseline. Since there is no prior schema to compare against on the first run, no drift is reported. The stored baseline then serves as the reference point for all subsequent extractions of that table.

The baseline is stored persistently so that it survives across pipeline runs and system restarts. If a table has never been extracted before, the system treats the first extraction as a bootstrapping event and focuses on capturing rather than comparing. Operators can observe that a baseline was established by reviewing the run history.

## Acceptance Criteria

- [ ] First extraction of a new table stores the complete source schema as a baseline
- [ ] The baseline includes all column names and their associated data types
- [ ] No schema drift is reported on the first extraction of a table
- [ ] The stored baseline persists across pipeline runs
- [ ] Subsequent extractions of the same table use the stored baseline for comparison
- [ ] Baseline capture occurs automatically without any per-table operator configuration
- [ ] The run history indicates when a new baseline was established for a table
