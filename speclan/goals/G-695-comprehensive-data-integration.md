---
id: G-695
type: goal
title: Comprehensive Data Integration
status: review
owner: TBD
created: '2026-04-10T05:56:35.232Z'
updated: '2026-04-10T05:57:52.234Z'
contributors:
  - F-0377
  - F-0405
  - F-0631
  - F-0663
  - F-0763
  - F-1685
---
# Comprehensive Data Integration

## Overview

Enable feather-etl to extract data from the heterogeneous ERP landscape of Indian SMBs, transform it through plain SQL, and load it into analytical destinations — replacing the typical three-tool enterprise stack (dlt + dbt/SQLMesh + Dagster/Airflow) with a single, config-driven package.

Indian SMBs run on a patchwork of ERP systems — SQL Server, SAP Business One, SAP S/4HANA, PostgreSQL, and various custom-built systems — alongside CSV exports, Excel files, and JSON feeds. feather-etl must connect to all of these seamlessly, extract data efficiently, apply SQL-based transformations with dependency resolution across the bronze/silver/gold layer model, and load results using the appropriate strategy. This goal ensures the core ELT data movement capabilities are robust and extensible.

Source discovery and deduplication capabilities round out this goal, ensuring operators can quickly inventory available data sources and that loaded data is clean of unwanted duplicates.

## Business Value

- **Primary Value**: A single package replaces three enterprise tools, dramatically reducing deployment complexity and cost per client
- **Secondary Benefits**: Faster client onboarding — new ERP types can be supported by adding connectors without architectural changes
- **Stakeholder Impact**: The delivery team can onboard new Indian SMB clients in days rather than weeks; clients get a unified data pipeline without managing multiple tools

## Scope

This goal encompasses:
- Data extraction from 8+ source types (CSV, DuckDB, SQLite, Excel, JSON, SQL Server, PostgreSQL, SAP)
- Source connectors and connector extensibility
- Source discovery for inventorying available data
- Data loading with full, incremental, and append strategies
- SQL-based transforms with dependency resolution
- Deduplication logic for clean data loads

### Boundaries

- **In Scope**: Extract, load, and transform stages; source connectors; source discovery; deduplication
- **Out of Scope**: Pipeline orchestration and retry logic (separate goal), data quality checks and schema validation (separate goal)

## Success Indicators

- All 8 source types are reliably supported with consistent extraction behavior
- New source types can be added via a connector interface without modifying core code
- SQL transforms resolve dependencies correctly and execute in proper order
- Deduplication handles common ERP data patterns (duplicate invoices, repeated transaction rows)
- Client onboarding time from "received ERP credentials" to "first successful pipeline run" is under 2 days
