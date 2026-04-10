---
id: R-1010
type: requirement
title: Non-Blocking Quality Alerts
status: review
owner: speclan
created: "2026-04-10T05:14:32.858Z"
updated: "2026-04-10T05:14:32.858Z"
---
# Non-Blocking Quality Alerts

Data quality check failures produce advisory warnings that inform operators of issues but never block the pipeline or prevent data from being loaded. When quality issues are detected and email alerting is configured, the system sends warning-level email notifications so operators can investigate at their convenience. This design ensures that data availability is never sacrificed for quality gatekeeping — the pipeline always completes, and operators retain full control over how and when to address quality findings.

The non-blocking approach reflects an operational philosophy where data consumers benefit more from having timely access to imperfect data with known quality annotations than from having no data at all due to a blocked pipeline. Quality check results serve as metadata that enriches the operator's understanding of the data, rather than as gates that restrict access to it.

When one or more quality checks fail or warn during a pipeline run and email alerting is configured, the system includes quality check findings in the pipeline notification email at a warning severity level, clearly distinguished from critical pipeline errors. If email alerting is not configured, results are still persisted to the state store and visible through direct query.

## Acceptance Criteria

- [ ] Quality check failures never halt, block, or prevent completion of the pipeline run
- [ ] Data is fully loaded and available in the destination table regardless of quality check outcomes
- [ ] Quality check failures trigger warning-level email alerts when email alerting is configured
- [ ] Email alerts clearly identify which checks failed and for which tables
- [ ] Quality check warnings are distinct from pipeline error notifications in severity level
- [ ] If email alerting is not configured, quality check results are still persisted and queryable
- [ ] The pipeline reports overall success even when quality checks produce failures or warnings
