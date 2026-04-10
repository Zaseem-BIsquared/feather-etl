---
id: F-0377
type: feature
title: Data Extraction
status: review
owner: speclan
created: "2026-04-10T05:04:41.634Z"
updated: "2026-04-10T05:06:06.317Z"
goals: []
---
# Data Extraction

## Overview

Data Extraction is the first stage of the pipeline lifecycle. It enables operators to pull data from any configured source system — whether file-based or database-backed — and receive a consistent, tabular result regardless of where the data originates. Operators configure their sources once, and the extraction engine handles the details of connecting, reading, and returning data in a uniform format.

This capability is the foundation for all downstream pipeline stages. Without extraction, no data enters the analytical environment. The extraction engine is designed to be stateless: it reads data based on the parameters it receives (table name, watermark, filters, batch size) and does not track run history or manage state on its own.

## Related Specifications

- **[Configuration System](../../F-0615-configuration-system/F-0615-configuration-system.md)**: Data Extraction depends on the Configuration System for all extraction parameters — source connection details, table definitions, extraction strategy (incremental or full), filter conditions, column maps, and batch sizes. Every extraction behavior is driven by the validated configuration produced by this system.
- **[State Management & Observability](../../F-0992-state-management-observability/F-0992-state-management-observability.md)**: Incremental extraction relies on watermark-based progress tracking provided by the state store. The state store records the high-water mark for each table after successful extraction, and subsequent runs use this value to determine where to resume. Extraction results — including row counts, timing, and error details — are also recorded in the state store for operational visibility.
- **[Email Alerting](../../F-1100-email-alerting/F-1100-email-alerting.md)**: When extraction fails for a table, the alerting system can notify operators via email. Data Extraction is an upstream producer of failure events that Email Alerting consumes.
- **[CLI Interface](../../F-1440-cli-interface/F-1440-cli-interface.md)**: Operators trigger extraction through the CLI — primarily via `feather run` (which invokes the full pipeline including extraction) and `feather discover` (which uses the extraction engine's source connectors to inspect available tables and columns).

## User Capabilities

### Multi-Source Data Retrieval

Operators can extract data from a wide variety of source systems using a single, consistent interface. Supported source types include flat files (CSV, JSON, Excel), embedded databases (DuckDB, SQLite), and enterprise database systems (SQL Server, PostgreSQL). Regardless of the source type, the extracted data is returned in a uniform columnar format that downstream pipeline stages can consume without adaptation.

### Incremental Extraction

Operators can configure tables for incremental extraction so that only new or recently changed records are pulled on each run. The system uses a timestamp-based watermark to determine which records are new since the last extraction. A configurable overlap window (defaulting to two minutes) ensures that records written near the boundary of the previous extraction are not missed due to clock skew or transaction timing. This reduces data transfer volumes and speeds up pipeline runs for large, frequently-updated tables.

### Full Extraction

Operators can configure tables for full extraction when they need the complete dataset refreshed on every run. This mode is appropriate for small reference tables, lookup data, or any source where incremental tracking is not feasible. Each run retrieves all records from the source without filtering by watermark.

### Filtered Extraction

Operators can define custom filter conditions on a per-table basis to restrict which records are extracted. Filters are expressed as SQL WHERE clause conditions in the pipeline configuration. This allows operators to extract only relevant subsets of large source tables — for example, filtering to a specific business unit, date range, or record status — without modifying the source system.

### Column Selection and Renaming

In production mode, operators can define a column map that specifies exactly which source columns to extract and what to rename them to. Only the mapped columns are included in the extracted result, and they appear with their new names. This allows operators to enforce a consistent, clean schema for downstream consumers without extracting unnecessary data from wide source tables.

### Chunked Extraction for Large Datasets

When extracting from database sources, the system retrieves data in configurable batch sizes rather than loading entire result sets into memory at once. This allows operators to extract from very large tables without exhausting system memory, making the pipeline suitable for production workloads with millions of rows.

## Scope

This feature encompasses all aspects of reading data from configured source systems and returning it in a uniform columnar format. It includes source-specific connection handling, query generation, watermark-based filtering, column selection, and batched retrieval.

Child features may be created to detail specific extraction behaviors such as individual source type adapters, watermark management strategies, or column mapping rules.

## Anchor

`src/feather_etl/sources/`
