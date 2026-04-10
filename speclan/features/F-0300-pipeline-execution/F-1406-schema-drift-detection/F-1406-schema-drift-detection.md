---
id: F-1406
type: feature
title: Schema Drift Detection
status: review
owner: speclan
created: "2026-04-10T05:17:27.980Z"
updated: "2026-04-10T05:20:14.189Z"
goals: []
---
# Schema Drift Detection

## Overview

Schema Drift Detection provides operators with automatic, continuous monitoring of source schema changes across pipeline runs. Every time data is extracted, the system compares the current source schema against a previously stored baseline and identifies any differences — new columns, removed columns, or columns whose data types have changed. This gives operators immediate awareness of upstream schema evolution without requiring manual inspection or external monitoring tools.

On the very first extraction of a table, the system captures and stores the source schema as the baseline. Subsequent runs compare the live schema against this baseline, classifying any differences by type and severity so that operators can quickly assess the impact. Importantly, schema drift detection is purely observational — it never blocks the pipeline or prevents data from flowing. Drift is recorded and reported, and the pipeline continues processing so that data availability is never interrupted by schema changes.

This capability is essential for production data pipelines that consume data from source systems outside the operator's control. Database administrators, application developers, or third-party vendors may alter source schemas at any time. Without drift detection, these changes could silently corrupt data, introduce NULL columns, or cause type-conversion failures that go unnoticed until downstream reports break. Schema Drift Detection turns these invisible risks into visible, classified, and actionable notifications.

## Related Specifications

- **[Data Extraction](../F-0377-data-extraction/F-0377-data-extraction.md)**: Schema Drift Detection operates during the extraction phase of the pipeline. It inspects the schema of data as it arrives from the source system, comparing it to the stored baseline before the data moves to loading. Extraction provides the live schema that drift detection evaluates.
- **[Data Loading](../F-0405-data-loading/F-0405-data-loading.md)**: Schema drift directly affects how data is loaded. When new columns are detected, the destination table is automatically expanded to accommodate them, with historical rows receiving NULL values. When columns are removed from the source, the destination retains them and loads NULL for the missing data. Type changes trigger conversion attempts, with failures routed to quarantine.
- **[SQL Transforms](../F-0631-sql-transforms/F-0631-sql-transforms.md)**: Schema drift can impact downstream SQL transforms that reference specific column names or depend on particular data types. When columns are added, removed, or change type at the source, transforms that reference affected columns may need operator attention. Drift detection provides early warning of schema changes that could cause transform failures, complementing the join health monitoring provided by SQL Transforms.
- **[Data Quality Checks](../F-1086-data-quality-checks/F-1086-data-quality-checks.md)**: Schema Drift Detection and Data Quality Checks are complementary observability mechanisms. Drift detection monitors structural changes to the data schema, while quality checks validate the content and integrity of the data itself. Together, they provide comprehensive coverage of both structural and content-level data issues.
- **[State Management & Observability](../../F-0992-state-management-observability/F-0992-state-management-observability.md)**: Drift detection results — including the full details of every detected change — are persisted in the run state as structured data. This provides operators with a historical record of schema evolution across all pipeline runs, enabling trend analysis and audit trails.
- **[Email Alerting](../../F-1100-email-alerting/F-1100-email-alerting.md)**: When schema drift is detected, the alerting system sends notifications to operators. The severity of the alert corresponds to the type of drift: informational alerts for added or removed columns, and critical alerts for data type changes that may cause conversion failures.
- **[Configuration System](../../F-0615-configuration-system/F-0615-configuration-system.md)**: The Configuration System defines which tables are monitored by the pipeline. Schema Drift Detection operates on every configured table automatically — no additional per-table drift configuration is required.

## User Capabilities

### Automatic Baseline Capture

When a table is extracted for the first time, the system automatically captures and stores the source schema as a baseline snapshot. Operators do not need to manually register schemas or configure baseline definitions — the system bootstraps itself on first contact with each source table. No drift is reported on the initial run since there is no prior schema to compare against.

### Continuous Schema Comparison

On every subsequent extraction, the system automatically compares the current source schema against the stored baseline. Operators receive immediate visibility into any schema changes without needing to run separate monitoring tools, write comparison scripts, or manually inspect source systems.

### Three-Category Drift Classification

The system classifies every detected schema change into one of three clear categories so operators can immediately understand the nature and impact of each change:

- **Added columns**: A new column exists in the source that was not present in the baseline. The destination table is automatically expanded to include the new column, and historical rows receive NULL values for the new column.
- **Removed columns**: A column present in the baseline no longer exists in the source. The destination table retains the column, and incoming rows receive NULL for the missing column. No data is lost.
- **Type-changed columns**: A column's data type in the source differs from the baseline. The system attempts to convert values to the expected type, but rows that fail conversion are quarantined rather than loaded with corrupt data.

### Severity-Graded Awareness

Each category of drift carries a severity level that helps operators prioritize their response. Added and removed columns are classified as informational — they are handled automatically and typically require no immediate action. Data type changes are classified as critical — they carry a risk of conversion failures and potential data quarantine, warranting prompt operator attention.

### Persistent Drift History

All drift details are recorded as structured data in the pipeline's run history. Operators can review the complete history of schema changes across any table and any run, supporting audit requirements, change tracking, and root-cause analysis when downstream data issues arise.

### Proactive Drift Notifications

When drift is detected, the system triggers email notifications to alert operators. This ensures that schema changes are surfaced promptly even when operators are not actively monitoring pipeline runs, enabling timely investigation and coordination with upstream data owners.

## Scope

This feature encompasses the automatic capture and storage of schema baselines, the comparison of live source schemas against baselines, the classification of detected differences into added/removed/type-changed categories, severity assignment, structured persistence of drift details, and integration with the alerting system for notifications.

This feature does not cover the loading-side mechanics of schema adaptation (ALTER TABLE operations, NULL backfilling, type casting, or quarantine routing) — those behaviors belong to [Data Loading](../F-0405-data-loading/F-0405-data-loading.md). It also does not cover the email delivery mechanism itself — that belongs to [Email Alerting](../../F-1100-email-alerting/F-1100-email-alerting.md).

## Anchor

`src/feather_etl/schema_drift.py`
