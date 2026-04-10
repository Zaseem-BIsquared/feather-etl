---
id: G-063
type: goal
title: Data Integrity & Quality Assurance
status: review
owner: TBD
created: '2026-04-10T05:56:55.833Z'
updated: '2026-04-10T05:57:53.636Z'
contributors:
  - F-1086
  - F-1406
---
# Data Integrity & Quality Assurance

## Overview

Guarantee that data flowing through feather-etl pipelines is structurally sound, semantically correct, and free of unexpected schema changes — catching problems at the pipeline level before they propagate to downstream dashboards and reports consumed by SMB clients.

Indian SMB ERPs are notoriously inconsistent. A SAP B1 instance might change column types after a vendor patch, a custom ERP might silently add nullable columns, and CSV exports might shift delimiters between runs. Without proactive quality checks and schema monitoring, these issues surface as broken dashboards or incorrect numbers — eroding client confidence in the data platform.

This goal ensures feather-etl acts as a quality gate. Data quality checks validate row-level and aggregate-level expectations (nulls, ranges, uniqueness, referential integrity), while schema drift detection catches structural changes before they cause silent data corruption. Together, these capabilities transform feather-etl from a mere data mover into a trustworthy data platform.

## Business Value

- **Primary Value**: Clients trust the numbers — data quality issues are caught at ingestion, not discovered in board meetings
- **Secondary Benefits**: Faster root-cause analysis when source systems change; reduced manual data validation effort
- **Stakeholder Impact**: Client finance and operations teams can rely on dashboards; the delivery team catches issues proactively rather than reactively

## Scope

This goal encompasses:
- Configurable data quality checks (null checks, range validation, uniqueness, custom SQL assertions)
- Schema drift detection across pipeline runs
- Alerting integration when quality checks fail or schemas change (cross-cuts with Operational Visibility)

### Boundaries

- **In Scope**: Data quality validation rules, schema drift detection, quality check configuration, failure reporting
- **Out of Scope**: Data transformation logic (separate goal), pipeline retry on quality failure (separate goal), monitoring infrastructure (separate goal)

## Success Indicators

- Every production pipeline includes at least one data quality check per critical table
- Schema drift is detected and surfaced within the same pipeline run that encounters it
- Zero incidents where bad data reaches client dashboards without a prior quality alert
- Quality checks are configurable via YAML without writing custom code
