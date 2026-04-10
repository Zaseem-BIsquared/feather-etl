---
id: F-1086
type: feature
title: Data Quality Checks
status: review
owner: speclan
created: "2026-04-10T05:13:23.790Z"
updated: "2026-04-10T05:16:05.093Z"
goals: []
---
# Data Quality Checks

## Overview

Data Quality Checks provide operators with automated, declarative data validation that runs as part of every pipeline execution. After data is loaded into the local analytical database, the system automatically evaluates a suite of quality checks against the freshly loaded data, giving operators immediate visibility into data integrity issues without requiring any custom code.

Operators configure their quality checks in the pipeline's YAML configuration on a per-table basis. The system supports several categories of validation — detecting null values, verifying uniqueness constraints, identifying duplicate rows, and monitoring row counts — each designed to catch common data quality problems that could affect downstream analytics and reporting. Results are always persisted for historical review and trend analysis.

Critically, data quality checks are advisory — they never block the pipeline or prevent data from being loaded. When issues are detected, the system records the findings and can notify operators via email, but the data remains available. This design philosophy prioritizes data availability over gatekeeping, allowing operators to investigate and remediate quality issues at their convenience without creating pipeline bottlenecks.

## Related Specifications

- **[Configuration System](../../F-0615-configuration-system/F-0615-configuration-system.md)**: Data Quality Checks depend on the Configuration System for all check definitions. Operators define which checks apply to each table — including null checks, uniqueness checks, and duplicate detection — through the `quality_checks` section of the table's YAML configuration. The configuration also provides primary key definitions used for automatic duplicate detection.
- **[Data Loading](../F-0405-data-loading/F-0405-data-loading.md)**: Quality checks execute after data loading completes. They validate the data as it exists in the local destination table, not the raw source data. This ensures checks reflect the actual state of data available to downstream consumers.
- **[State Management & Observability](../../F-0992-state-management-observability/F-0992-state-management-observability.md)**: All quality check results are persisted to a dedicated results table in the state store. This provides operators with a historical record of data quality across pipeline runs, enabling trend analysis and proactive issue identification.
- **[Email Alerting](../../F-1100-email-alerting/F-1100-email-alerting.md)**: When quality checks detect issues, the alerting system can send warning notifications to operators. Quality check failures produce warning-level alerts (not errors), reflecting their advisory nature.
- **[SQL Transforms](../F-0631-sql-transforms/F-0631-sql-transforms.md)**: Data Quality Checks and SQL Transforms are complementary data validation mechanisms within the pipeline. Quality checks validate source data integrity at the row and column level immediately after loading, while SQL Transforms provides join health monitoring that detects row count anomalies at the transform level. Together, they give operators coverage across the full data lifecycle — from raw ingestion through analytical datasets.

## User Capabilities

### Declarative Quality Configuration

Operators define data quality checks entirely through YAML configuration — no custom code or scripting is required. Each table can have its own set of checks tailored to its data characteristics, and operators can add, modify, or remove checks by editing configuration files. This makes quality validation accessible to operators without programming expertise.

### Automatic Post-Load Validation

Quality checks run automatically after each successful data load as an integrated part of the pipeline lifecycle. Operators do not need to remember to trigger validation separately or build external monitoring processes — the pipeline handles it as part of every run.

### Multi-Dimensional Quality Assessment

Operators can validate data across several quality dimensions simultaneously: checking for null values in critical columns, verifying that columns expected to be unique contain no duplicates, detecting exact duplicate rows across the dataset, and leveraging primary key definitions to catch key-based duplicates automatically. This comprehensive approach catches a wide range of common data quality issues.

### Always-On Row Count Monitoring

Every table load is automatically monitored for row count, regardless of what other quality checks are configured. Operators receive an immediate warning if a load produces zero rows, which often indicates an upstream issue such as a failed extraction, empty source, or misconfigured filter — without requiring the operator to explicitly configure this safeguard.

### Persistent Quality History

Every quality check result — including the check type, affected column, pass/fail/warn outcome, and descriptive details — is recorded in a dedicated results table. Operators can query this history to identify recurring quality issues, track improvements over time, and demonstrate data governance compliance.

### Non-Blocking Advisory Alerts

Quality check failures never halt the pipeline or prevent data from being loaded. Instead, they generate warning-level notifications that inform operators of issues requiring attention. This ensures that data remains available to downstream consumers even when quality issues exist, and operators can investigate and remediate at their convenience.

## Scope

This feature encompasses the declarative configuration, automatic execution, result persistence, and alerting integration of post-load data quality checks. It covers all supported check types (null detection, uniqueness validation, duplicate detection, primary key duplicate detection, and row count monitoring) and the non-blocking advisory model.

Child features are not anticipated — individual check types are specified as requirements within this leaf feature.

## Anchor

`src/feather_etl/dq.py`
