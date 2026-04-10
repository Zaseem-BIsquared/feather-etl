---
id: F-0300
type: feature
title: Pipeline Execution
status: review
owner: speclan
created: "2026-04-10T04:54:33.283Z"
updated: "2026-04-10T04:54:41.017Z"
goals: []
---
# Pipeline Execution

## Overview

Pipeline Execution is the core operational capability of the ETL system. It enables operators to execute the full data pipeline — extracting data from configured source systems, loading it into the local analytical database, running data quality checks, detecting schema changes, and applying transformations — all through a single command.

The operator initiates a pipeline run using the `feather run` command, and the system orchestrates the entire extract → load → transform cycle automatically. This capability is the primary way data is moved from source systems into the analytical environment and kept up to date.

## User Capabilities

### Full Pipeline Runs

Operators can execute the complete pipeline for all configured tables with a single command. The system processes each table through the full lifecycle — extraction, loading, quality validation, schema drift detection, and transformation — without requiring manual intervention between stages.

### Targeted Table Execution

Operators can run the pipeline for a single specific table when they need to refresh one dataset without processing everything. This supports quick iteration, debugging, and on-demand data refreshes for high-priority tables.

### Schedule-Based Execution

Operators can run the pipeline for groups of tables organized by schedule tier (e.g., hourly, daily, weekly). This allows the pipeline to be integrated with external schedulers so that different tables refresh at appropriate intervals based on their data freshness requirements.

### Independent Table Processing

Each table is processed independently during a pipeline run. If one table encounters an error — whether during extraction, loading, or transformation — it does not prevent other tables from completing successfully. Operators receive clear reporting on which tables succeeded and which failed, enabling targeted remediation.

### Automatic Transform Rebuilding

After source data is extracted and loaded, the system automatically rebuilds downstream transformations (silver and gold layers). The system adapts its transformation strategy based on the current environment mode — using lightweight approaches in development and test environments for speed, and durable approaches in production for reliability.

### Run Metadata and Auditability

Every pipeline run records comprehensive metadata — including timing, row counts, success/failure status, and error details — to a persistent state database. Operators can review historical runs to monitor pipeline health, diagnose issues, and verify that data was processed correctly.

## Scope

This feature encompasses the end-to-end orchestration of pipeline runs. Individual capabilities within the pipeline lifecycle — such as data extraction from specific source types, load strategies, data quality checks, schema drift detection, and SQL transformations — are expected to be specified as child features with their own detailed requirements.

## Anchor

`src/feather_etl/pipeline.py`
