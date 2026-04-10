---
id: R-0135
type: requirement
title: Severity-Based Alert Categorization
status: review
owner: speclan
created: "2026-04-10T05:00:11.380Z"
updated: "2026-04-10T05:00:11.380Z"
---
# Severity-Based Alert Categorization

Operators receive email alerts that are categorized by severity level — critical, warning, or informational — enabling them to immediately assess urgency and prioritize their response. This classification system ensures that pipeline failures and data integrity issues demand attention, while routine notifications remain visible without causing alarm.

Critical alerts are sent for events that represent data loss, pipeline interruption, or data integrity risks: pipeline stage failures (such as failed extractions or loads), data that could not be loaded correctly and was set aside for review, and schema changes that alter the meaning of existing columns (such as a column's data type changing). Warning alerts are sent when data quality checks fail, indicating that data was loaded successfully but may not meet expected standards. Informational alerts notify operators of structural changes in source data — such as new columns appearing or existing columns being removed — that do not affect current processing but may require attention in downstream transformations. When a schema change involves a data type modification, the severity is elevated from informational to critical, reflecting the higher risk to data integrity.

## Acceptance Criteria

- [ ] Pipeline failures (extraction errors, load errors) generate critical-severity alerts
- [ ] Records quarantined due to type-casting issues generate critical-severity alerts
- [ ] Data quality check failures generate warning-severity alerts
- [ ] New or removed columns in source data generate informational-severity alerts
- [ ] Column data type changes generate critical-severity alerts, not informational
- [ ] Each alert email clearly displays its severity level in a consistent, recognizable format
- [ ] Severity categorization is consistent and deterministic for the same event type across runs
