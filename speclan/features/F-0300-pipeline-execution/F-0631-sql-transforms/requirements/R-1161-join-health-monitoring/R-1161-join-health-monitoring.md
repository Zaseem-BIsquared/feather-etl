---
id: R-1161
type: requirement
title: Join Health Monitoring
status: review
owner: speclan
created: "2026-04-10T05:10:54.810Z"
updated: "2026-04-10T05:10:54.810Z"
---
# Join Health Monitoring

Operators can annotate gold transforms with a fact table reference, enabling the system to automatically monitor join health by comparing the row count of the gold transform output against the row count of the designated source fact table. This detects two common data quality issues: join inflation (where faulty joins multiply rows beyond the expected count) and join loss (where rows are unexpectedly dropped during joins).

After transforms are executed, the system checks each annotated gold transform by counting the rows in the resulting dataset and comparing against the fact table's row count. A significant discrepancy indicates a potential join defect. This monitoring runs automatically as part of the transform process, giving operators early warning of data quality issues before bad data propagates to dashboards and downstream consumers.

Operators choose which gold transforms to monitor by adding the fact table annotation — only annotated transforms are checked. Transforms without fact table annotations skip this health check entirely, allowing operators to focus monitoring on the transforms where join correctness is most critical.

## Acceptance Criteria

- [ ] Operator can annotate a gold transform SQL file with a fact table reference for join health monitoring
- [ ] The system compares the row count of the gold transform output against the referenced fact table after execution
- [ ] Join inflation (gold output has more rows than the fact table) is detected and reported
- [ ] Join loss (gold output has fewer rows than the fact table) is detected and reported
- [ ] Only gold transforms with a fact table annotation are subject to join health checking
- [ ] Gold transforms without a fact table annotation skip join health monitoring without errors
- [ ] Join health check results are surfaced to operators with enough detail to identify the affected transform
