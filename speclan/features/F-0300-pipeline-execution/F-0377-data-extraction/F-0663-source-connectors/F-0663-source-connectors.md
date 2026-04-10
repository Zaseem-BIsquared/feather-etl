---
id: F-0663
type: feature
title: Source Connectors
status: review
owner: speclan
created: "2026-04-10T05:28:10.554Z"
updated: "2026-04-10T05:31:42.026Z"
goals: []
---
# Source Connectors

## Overview

Source Connectors provide operators with a library of ready-to-use data source adapters that connect to a variety of file-based and database-backed systems. Each connector presents a uniform interface for connectivity verification, table and column discovery, data extraction, change detection, and schema inspection — regardless of the underlying source technology. Operators configure a source type and connection details in their pipeline configuration, and the appropriate connector handles all source-specific interaction transparently.

The system ships with seven built-in connectors spanning the most common data source categories: flat files (CSV, JSON, Excel), embedded databases (DuckDB, SQLite), and enterprise database systems (SQL Server, PostgreSQL). This coverage allows operators to build pipelines against a wide range of source systems without installing additional plugins or writing custom integration code.

The connector architecture is designed for extensibility. New source types can be added by implementing a small, well-defined contract and registering the connector with the system. This allows teams to support additional source systems as their data landscape evolves, without modifying existing connectors or pipeline logic.

## Related Specifications

- **[Data Extraction](../F-0377-data-extraction.md)**: Source Connectors are the mechanism through which Data Extraction interacts with external systems. The extraction engine delegates all source-specific operations — connecting, querying, reading data — to the appropriate connector. Every extraction capability described in the parent feature (incremental, full, filtered, column-mapped, batched) is realized through connector operations.
- **[Change Detection](../F-0411-change-detection/F-0411-change-detection.md)**: Each source connector provides a change detection capability that the Change Detection feature consumes. File-based connectors report modification timestamps and content fingerprints; database connectors report aggregate checksums. The Change Detection feature orchestrates when and how these signals are used to skip unchanged sources.
- **[Configuration System](../../../F-0615-configuration-system/F-0615-configuration-system.md)**: Source connector selection and parameterization are driven entirely by the pipeline configuration. The configuration specifies the source type, connection details, and per-table extraction settings that connectors use to perform their work.
- **[Schema Drift Detection](../../F-1406-schema-drift-detection/F-1406-schema-drift-detection.md)**: Source connectors provide schema inspection capabilities that Schema Drift Detection uses to compare current source structure against previously recorded baselines. Each connector can report the columns and data types available in a source table.
- **[CLI Interface](../../../F-1440-cli-interface/F-1440-cli-interface.md)**: The CLI's `discover` command uses source connectors to list available tables and their column schemas, allowing operators to inspect source systems before building pipeline configurations.
- **[Data Loading](../../F-0405-data-loading/F-0405-data-loading.md)**: Source Connectors produce data in a uniform columnar format that Data Loading consumes directly. The connector's output — including the column names, data types, and row data — is the immediate input to the loading stage. The loading strategy chosen for each table (full, incremental, or append) operates on the tabular result produced by the connector.
- **[State Management & Observability](../../../F-0992-state-management-observability/F-0992-state-management-observability.md)**: Source connectors generate fingerprints (file modification timestamps, content hashes, database checksums) that are persisted in the state store between pipeline runs. These stored fingerprints enable change detection across runs and provide an operational audit trail of source system state over time.

## User Capabilities

### Uniform Multi-Source Access

Operators can extract data from CSV files, JSON files, Excel spreadsheets, DuckDB databases, SQLite databases, SQL Server instances, and PostgreSQL instances using a consistent configuration pattern. Regardless of source type, operators configure a source connection, define tables, and run their pipeline — the connector handles all source-specific details. Extracted data is always returned in a uniform columnar format suitable for downstream processing.

### Source Connectivity Verification

Operators can verify that a configured source is reachable and accessible before running a full pipeline. The system tests whether the source exists (for files) or is connectable (for databases) and reports clear success or failure. This allows operators to diagnose configuration issues — such as incorrect file paths, missing credentials, or unreachable database servers — without waiting for a full pipeline run to fail.

### Table and Schema Discovery

Operators can discover what tables (or files) are available in a configured source, along with the column names and data types for each table. This is useful when setting up new pipelines, verifying source structure, or investigating what data is available before writing extraction configurations.

### File Pattern Matching

Operators working with file-based sources can use wildcard patterns (e.g., `sales_*.csv`) to treat multiple files matching a naming convention as a single logical table. This is particularly useful for sources that produce partitioned output files — such as daily export files or region-specific data dumps — allowing operators to extract from all matching files in a single table definition.

### Legacy and Modern Excel Support

Operators can extract data from both modern Excel files (`.xlsx`) and legacy Excel files (`.xls`) using the same source configuration. The system automatically selects the appropriate reading strategy based on file format, so operators do not need to adjust their configuration or use different source types for different Excel versions.

### Pluggable Source Extension

Teams can add support for new source systems by implementing a well-defined connector contract and registering it with the system. The contract is minimal — new file-based connectors require very little code, and new database connectors require only moderately more. Once registered, a new connector is available for use in pipeline configurations with the same capabilities as built-in connectors, including connectivity checks, table discovery, data extraction, change detection, and schema inspection.

## Scope

This feature covers the set of built-in source connectors, their shared capabilities (connectivity verification, discovery, extraction, change detection, schema inspection), source-type-specific behaviors (file pattern matching, Excel format handling), and the extensibility mechanism for adding new connectors.

This feature does not cover the extraction lifecycle orchestration (handled by [Data Extraction](../F-0377-data-extraction.md)), change detection decision logic (handled by [Change Detection](../F-0411-change-detection/F-0411-change-detection.md)), or schema drift evaluation (handled by [Schema Drift Detection](../../F-1406-schema-drift-detection/F-1406-schema-drift-detection.md)). Those features consume connector capabilities but manage their own workflows.

## Anchor

`src/feather_etl/sources/registry.py`
