---
id: F-0405
type: feature
title: Data Loading
status: draft
owner: speclan
created: "2026-04-10T05:07:05.819Z"
updated: "2026-04-10T05:09:12.575Z"
goals: []
---
# Data Loading

## Overview

Data Loading is the stage of the pipeline lifecycle responsible for persisting extracted data into the local analytical database. After data has been extracted from source systems, operators need it reliably written to the destination so that transformations, queries, and reporting can operate on current data. Data Loading provides three distinct loading strategies — full replacement, incremental partition overwrite, and append-only — so that operators can match the loading behavior to the nature of each dataset.

Each loading operation is atomic: either all rows for a table are committed successfully, or the destination remains unchanged. This guarantees that downstream consumers never see partial or corrupted data, even if a pipeline run is interrupted mid-load. Every loaded row is automatically stamped with metadata identifying when it was loaded and which pipeline run produced it, giving operators full traceability from any row back to the run that created it.

On first use, the destination database is automatically provisioned with a standard set of data layers (bronze, silver, gold, and quarantine), giving operators an organized analytical environment without manual setup. The database file is secured with restricted permissions to protect sensitive data.

## Related Specifications

- **[Data Extraction](../F-0377-data-extraction/F-0377-data-extraction.md)**: Data Loading receives its input from Data Extraction. The extracted tabular data is the direct input to the loading process. The extraction strategy (full or incremental) typically determines which loading strategy is appropriate for a given table.
- **[Configuration System](../../F-0615-configuration-system/F-0615-configuration-system.md)**: Data Loading depends on the Configuration System for loading parameters — including which loading strategy to use for each table, the target schema and table names, the timestamp column used for partition boundaries in incremental loads, and the destination database file path.
- **[State Management & Observability](../../F-0992-state-management-observability/F-0992-state-management-observability.md)**: Loading outcomes — including row counts, timing, and error details — are recorded in the state store. The ETL run identifier stamped on every loaded row originates from the state management system, enabling end-to-end traceability across pipeline runs.
- **[Pipeline Execution](../F-0300-pipeline-execution.md)**: Data Loading is orchestrated as part of the extract → load → transform cycle managed by the Pipeline Execution feature. The pipeline engine invokes the loader after extraction completes for each table.
- **[Email Alerting](../../F-1100-email-alerting/F-1100-email-alerting.md)**: When a loading operation fails for a table, the alerting system can notify operators via email. Data Loading is an upstream producer of failure events that Email Alerting consumes, enabling operators to respond quickly to load failures without monitoring pipeline logs.

## User Capabilities

### Full Replacement Loading

Operators can configure tables to be fully replaced on each pipeline run. When a load executes with the full replacement strategy, the existing table is completely swapped out with the new data in a single atomic operation. This is ideal for small reference tables, lookup data, or any dataset where the complete contents should reflect the latest extraction. The previous version of the table is not retained — after a successful load, only the new data exists.

### Incremental Partition Loading

Operators can configure tables for incremental loading, where only the affected time partitions are refreshed. The system determines which partitions to update based on the timestamps in the incoming data, removes stale rows in those partitions, and inserts the new rows — all within a single atomic operation. This strategy is designed for large transactional tables where only recent data changes between runs, minimizing the volume of data written while keeping the destination current.

### Append-Only Loading

Operators can configure tables for append-only loading, where new rows are inserted without modifying or removing any existing data. This strategy is designed for audit trails, compliance logs, and any dataset where full history must be preserved. No data is ever deleted or overwritten — each pipeline run adds its batch of rows to the growing table. If the target table does not yet exist, it is automatically created on the first load.

### Automatic ETL Metadata Stamping

Every row loaded into the destination is automatically enriched with metadata columns identifying the load timestamp and the pipeline run that produced it. Operators do not need to configure or manage these columns — they are added transparently by the loading process. This enables operators to trace any row back to the specific pipeline run that loaded it, filter data by load time, and identify stale or duplicate records.

### Automatic Destination Provisioning

When the destination database is first accessed, the system automatically creates the standard analytical schema layers — bronze (raw ingested data), silver (cleaned and conformed data), gold (business-ready aggregates), and a quarantine area for rows that fail quality checks. Operators do not need to manually create schemas or run setup scripts. The database file is also secured with restricted access permissions to protect sensitive data from unauthorized access.

## Scope

This feature encompasses all aspects of writing extracted data to the local analytical database, including strategy selection, atomic commit behavior, metadata enrichment, destination provisioning, and file security. It does not cover data extraction (upstream), data quality checks (separate feature), or SQL transformations (downstream).

## Anchor

`src/feather_etl/destinations/duckdb.py`
