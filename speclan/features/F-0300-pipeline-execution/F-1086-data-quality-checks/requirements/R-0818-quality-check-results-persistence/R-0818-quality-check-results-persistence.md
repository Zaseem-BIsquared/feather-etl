---
id: R-0818
type: requirement
title: Quality Check Results Persistence
status: review
owner: speclan
created: "2026-04-10T05:14:22.805Z"
updated: "2026-04-10T05:14:22.805Z"
---
# Quality Check Results Persistence

Every data quality check result is automatically persisted to a dedicated results table in the state store, creating a comprehensive historical record of data quality across all pipeline runs. This enables operators to query past results, identify recurring quality issues, track improvements over time, and demonstrate data governance practices to stakeholders and auditors.

Each persisted result captures the essential dimensions of the check: which table was checked, what type of check was performed, which column was evaluated (if applicable), whether the check passed, failed, or produced a warning, and descriptive details about the finding. Results accumulate over time, building a rich dataset that operators can query and analyze just like any other data in the system.

Persistence is automatic and unconditional — every check result from every pipeline run is recorded regardless of whether it passed or failed. This ensures complete traceability and allows operators to confirm that checks were executed, not just to find failures.

## Acceptance Criteria

- [ ] Every quality check result is automatically persisted to a dedicated results table in the state store
- [ ] Each persisted result records the check type (e.g., not_null, unique, duplicate, row_count)
- [ ] Each persisted result records the column evaluated, where applicable
- [ ] Each persisted result records the outcome: pass, fail, or warn
- [ ] Each persisted result records descriptive details about the finding
- [ ] Results from all pipeline runs accumulate over time for historical analysis
- [ ] Both passing and failing check results are persisted
