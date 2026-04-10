---
id: F-0131
type: feature
title: Run History & Status
status: draft
owner: team
created: "2026-04-10T05:39:24.286Z"
updated: "2026-04-10T05:41:03.593Z"
goals: []
---
# Run History & Status

## Overview

Run History & Status provides operators and data engineers with complete visibility into every pipeline execution. After each run, the system automatically records comprehensive operational details — including timing, row counts, outcomes, error messages, watermark progression, and schema changes — into persistent storage. Users access this information through two purpose-built CLI commands (`feather history` and `feather status`) as well as direct SQL queries for advanced analysis.

This feature addresses the operational need to answer questions like "What happened during last night's sync?", "Which tables are failing?", "How many rows were loaded yesterday?", and "Are my data quality checks passing?" — without requiring external monitoring infrastructure.

## Related Specifications

- **[Pipeline Execution](../../../features/F-0300-pipeline-execution/F-0300-pipeline-execution.md)**: Pipeline Execution is the primary producer of the run metadata that this feature persists and surfaces. Every pipeline run — including timing, row counts, success/failure status, and error details — generates the operational data that Run History & Status records and makes queryable.
- **[CLI Interface](../../../features/F-1440-cli-interface/F-1440-cli-interface.md)**: The `feather history` and `feather status` commands defined in the CLI Interface are the primary user-facing access points for run history data. The CLI delegates to this feature for data retrieval and supports `--json` output mode for machine-readable consumption of run history.
- **[Data Quality Checks](../../../features/F-0300-pipeline-execution/F-1086-data-quality-checks/F-1086-data-quality-checks.md)**: Data quality check outcomes are recorded as part of each run's operational record. Run History & Status persists these results to a dedicated table, enabling operators to query quality trends and failures across runs via SQL or CLI commands.
- **[Schema Drift Detection](../../../features/F-0300-pipeline-execution/F-1406-schema-drift-detection/F-1406-schema-drift-detection.md)**: Schema drift details detected during extraction are persisted as structured data within the run history. This gives operators a historical record of schema evolution across all pipeline runs, supporting audit trails and root-cause analysis.
- **[Email Alerting](../../../features/F-1100-email-alerting/F-1100-email-alerting.md)**: Automated alerting based on run history is explicitly out of scope for this feature and is handled by Email Alerting. Run History & Status provides the historical record, while Email Alerting provides proactive notification of issues as they occur.

## Key Capabilities

- **Comprehensive run logging**: Every pipeline execution is recorded with full context including timing, row metrics, error details, watermark values, and schema change detection
- **Recent run browsing**: Users can review recent pipeline activity, optionally filtered by table name and limited to a specific number of results
- **At-a-glance table status**: Users can see the last run outcome for every table across all time, providing a quick health dashboard
- **Data quality result tracking**: All data quality check outcomes are recorded per run, enabling users to query for failures and trends
- **Machine-readable output**: Both history and status commands support JSON output for integration with scripts, dashboards, and alerting tools

## Scope

### In Scope
- Persistent storage of run execution metadata (timing, counts, status, errors)
- Persistent storage of watermark progression per run
- Persistent storage of detected schema changes per run
- CLI command for browsing recent run history with filtering
- CLI command for viewing last-run status across all tables
- JSON output mode for both commands
- Persistent storage of data quality check results per run
- Direct SQL queryability of data quality results

### Out of Scope
- Real-time run monitoring or streaming logs
- Web-based dashboards or GUI interfaces
- Automated alerting based on run history (covered by Email Alerting)
- Run history retention policies or automatic cleanup
