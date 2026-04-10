---
id: F-0763
type: feature
title: Source Discovery
status: draft
owner: speclan
created: "2026-04-10T05:50:29.028Z"
updated: "2026-04-10T05:52:32.052Z"
goals: []
---
# Source Discovery

## Overview

Source Discovery allows operators to explore the structure of a connected source system before configuring their data pipeline. By running `feather discover`, operators receive a complete inventory of available tables, including their column names and inferred data types, without extracting or modifying any data. This read-only introspection helps operators understand what data is accessible and make informed decisions when defining table selections in their pipeline configuration.

The discovery process works across all supported source types. Whether the source is a set of files in a directory or a relational database, operators get a consistent view of available tables and their schemas. This eliminates the need to manually inspect source systems using external tools or database clients, keeping the entire pipeline setup workflow within the `feather` CLI.

## Related Specifications

- **[CLI Interface](../F-1440-cli-interface.md)**: Source Discovery is a command within the CLI Interface, following its conventions for global options (`--config`, `--json`), output formatting, and semantic exit codes.
- **[Source Connectors](../../F-0300-pipeline-execution/F-0377-data-extraction/F-0663-source-connectors/F-0663-source-connectors.md)**: Discovery relies on source connectors to access metadata from each source type. The connectivity check that runs before discovery uses the same mechanism that Source Connectors provide for verifying reachable sources, and the table/column listing delegates to each connector's discovery interface.
- **[Configuration System](../../F-0615-configuration-system/F-0615-configuration-system.md)**: The discover command reads the source configuration from the pipeline configuration file (`feather.yaml`) to know which source system to introspect and how to connect to it.
- **[Data Extraction](../../F-0300-pipeline-execution/F-0377-data-extraction/F-0377-data-extraction.md)**: Source Discovery shares the extraction engine's source connector infrastructure. While Data Extraction uses connectors to pull data, Source Discovery uses the same connectors in a read-only metadata inspection mode to list tables and columns without extracting row data.
- **[Schema Drift Detection](../../F-0300-pipeline-execution/F-1406-schema-drift-detection/F-1406-schema-drift-detection.md)**: Both Source Discovery and Schema Drift Detection inspect source table schemas — column names and data types. Discovery provides a point-in-time snapshot for initial exploration, while Schema Drift Detection continuously compares live schemas against stored baselines across pipeline runs.
- **[Config Validation](../../F-0615-configuration-system/F-0396-config-validation/F-0396-config-validation.md)**: Both features perform pre-execution verification. Config Validation checks that the configuration is well-formed and that sources are reachable, while Source Discovery goes further by introspecting the source system's available tables and schemas. Operators typically validate their configuration and then use discovery to inform table selection.
- **[Project Scaffolding](../F-0368-project-scaffolding/F-0368-project-scaffolding.md)**: Source Discovery is the natural next step after scaffolding a new project. After `feather init` creates the initial project structure and configuration, operators use `feather discover` to inspect their source system and determine which tables and columns to include in their pipeline configuration.

## User Capabilities

### Listing Available Tables

Operators can discover all tables available in their configured source system. The output presents qualified table names (e.g., schema-prefixed names for database sources, or file-derived names for file-based sources), giving operators a clear map of what data can be included in their pipeline.

### Inspecting Table Schemas

For each discovered table, operators can see the column names and their data types. This schema information helps operators understand the shape of source data and plan column mappings, type handling, and transformation logic in their pipeline configuration.

### Connectivity Verification Before Discovery

Before attempting discovery, the system automatically verifies that the configured source is reachable. If the source cannot be contacted, the operator receives a clear failure indication with a distinct exit code, preventing confusion between connectivity problems and empty source systems.

### Machine-Readable Discovery Output

Operators can request discovery results in structured JSON format using the `--json` flag. Each table is represented as a structured object containing the table name and an array of column definitions, enabling automation tools and scripts to programmatically consume and act on discovery results.

## Scope

This feature covers the discovery command's ability to list tables and their schemas from configured source systems, including the pre-discovery connectivity check and both human-readable and JSON output modes. The actual source connection mechanisms, configuration file parsing, and data extraction are handled by their respective sibling features. Discovery is strictly read-only — it retrieves metadata only and never extracts, transforms, or loads data.

## Anchor

`src/feather_etl/cli.py`
