---
id: F-0631
type: feature
title: SQL Transforms
status: draft
owner: speclan
created: "2026-04-10T05:09:59.199Z"
updated: "2026-04-10T05:12:09.789Z"
goals: []
---
# SQL Transforms

## Overview

SQL Transforms enables operators to define reusable data transformations as plain SQL files organized into two logical layers — silver and gold — that reshape and refine raw source data into analysis-ready datasets. This two-layer approach gives operators a structured way to build progressively refined views of their data, from standardized canonical representations to purpose-built analytical datasets optimized for dashboards and reporting.

Operators author transforms as standard SQL files and place them into the appropriate layer directory. The system automatically resolves dependencies between transforms, determines the correct execution order, and creates the corresponding database objects. This lets operators focus on writing SQL rather than managing execution workflows.

## Related Specifications

- **[Data Extraction](../F-0377-data-extraction/F-0377-data-extraction.md)**: SQL Transforms operates on raw source data that has been extracted by Data Extraction. The silver layer creates canonical views over this raw data, making extraction the upstream data producer that feeds into the transformation pipeline.
- **[Data Loading](../F-0405-data-loading/F-0405-data-loading.md)**: SQL Transforms depends on Data Loading to persist extracted data into the analytical database's bronze layer before transformations can run. Data Loading also provisions the silver and gold schema layers that transforms write into.
- **[Configuration System](../../F-0615-configuration-system/F-0615-configuration-system.md)**: SQL Transforms relies on the Configuration System for transform directory paths, variable substitution values, and the operating mode setting that determines whether gold transforms are materialized as tables (production) or created as lightweight views (development/test).
- **[State Management & Observability](../../F-0992-state-management-observability/F-0992-state-management-observability.md)**: Transform execution outcomes — including join health monitoring results, row count comparisons, and rebuild timing — contribute to the operational record maintained by the state store, enabling operators to audit transform behavior across pipeline runs.
- **[Email Alerting](../../F-1100-email-alerting/F-1100-email-alerting.md)**: When join health monitoring detects row count anomalies (join inflation or join loss), SQL Transforms produces alert events that Email Alerting delivers to operators, enabling rapid response before bad data reaches downstream consumers.
- **[CLI Interface](../../F-1440-cli-interface/F-1440-cli-interface.md)**: Operators trigger transform execution indirectly through the CLI — `feather run` invokes the full pipeline including transform rebuilds, and `feather setup` applies transform definitions to prepare the analytical environment.

## User Capabilities

### Silver Layer — Canonical Data Views

Operators define silver-layer transforms to create standardized, canonical views over raw source data. Silver transforms always produce lightweight views that stay current automatically — they require no scheduled rebuild and always reflect the latest underlying data. This layer is where operators normalize column names, apply consistent formatting, and create a clean interface over raw ingested data.

### Gold Layer — Analytical Datasets

Operators define gold-layer transforms to create analysis-ready datasets that combine, aggregate, or reshape silver-layer data for specific reporting and dashboard needs. Gold transforms are views by default, but operators can opt into materialized tables for transforms where dashboard query performance is critical. This gives operators control over the trade-off between data freshness and query speed.

### Dependency Declaration and Resolution

Operators declare dependencies between transforms using simple annotations within their SQL files. The system automatically resolves these dependencies and determines the correct execution order so that upstream transforms are always processed before downstream ones. If a required transform-layer dependency is missing, the system alerts the operator at setup time rather than failing silently during execution.

### Environment-Aware Execution

The system adapts its transform strategy based on the current environment. In production, materialized gold tables are rebuilt after every successful data extraction run to keep analytical datasets current. In development and test environments, all transforms are created as lightweight views regardless of materialization settings, enabling faster iteration without the overhead of table rebuilds.

### Variable Substitution in SQL

Operators can use variable placeholders within their transform SQL, allowing the same transform definitions to adapt to different environments, schemas, or configurations without duplicating SQL files.

### Join Health Monitoring

Operators can annotate gold transforms with fact table references, enabling the system to automatically compare result row counts against source fact tables after each run. This detects join inflation (unexpected row multiplication) or join loss (missing rows) — common data quality issues — and alerts operators before bad data reaches downstream consumers.

## Scope

This feature covers the authoring, dependency management, execution, and health monitoring of SQL-based data transformations across the silver and gold layers. It does not cover data extraction from source systems (handled by [Data Extraction](../F-0377-data-extraction/F-0377-data-extraction.md)) or data loading into the analytical database (handled by [Data Loading](../F-0405-data-loading/F-0405-data-loading.md)), which are sibling features under Pipeline Execution.

## Anchor

`src/feather_etl/transforms.py`
