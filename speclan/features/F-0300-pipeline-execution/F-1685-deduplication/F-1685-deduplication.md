---
id: F-1685
type: feature
title: Deduplication
status: draft
owner: system
created: "2026-04-10T05:20:57.236Z"
updated: "2026-04-10T05:22:39.161Z"
goals: []
---
# Deduplication

## Overview

Deduplication ensures that data loaded into destination tables is free from unwanted duplicate rows. Users can configure two complementary levels of deduplication that address different sources of duplicates in data pipelines.

**Config-driven deduplication** allows users to declare deduplication rules directly in table configuration. Users can choose between exact row-level deduplication (removing fully identical rows) or key-based deduplication (keeping only the first occurrence for each unique combination of specified columns). The system validates that these two options are not used simultaneously, providing clear feedback when configuration is invalid.

**Boundary deduplication** automatically prevents duplicate rows that arise during incremental extraction with overlap windows. When the pipeline re-fetches data near the boundary of the last extraction watermark, it recognizes rows that were already loaded in a previous run and filters them out. This happens transparently, requiring no manual intervention once incremental extraction is configured.

## Related Specifications

- **[Data Extraction](../F-0377-data-extraction/F-0377-data-extraction.md)**: Boundary deduplication is directly coupled to the incremental extraction overlap window provided by Data Extraction. When extraction re-fetches rows near the watermark boundary to guard against clock skew and transaction timing, Deduplication is responsible for filtering out rows that were already loaded in a previous run, ensuring the overlap window does not introduce duplicates in the destination.
- **[Data Loading](../F-0405-data-loading/F-0405-data-loading.md)**: Deduplication operates as part of the loading phase — after data is extracted and before it is committed to the destination. Config-driven deduplication filters duplicate rows from the extracted dataset before the loader persists them, and boundary deduplication compares incoming rows against previously loaded data. The ETL metadata stamping provided by Data Loading supports row-level traceability that complements deduplication tracking.
- **[Configuration System](../../F-0615-configuration-system/F-0615-configuration-system.md)**: Config-driven deduplication rules — including the choice between exact row-level and key-based deduplication — are declared in the table's YAML configuration. The Configuration System validates these settings at load time, ensuring conflicting options (e.g., both exact and key-based deduplication on the same table) are rejected with clear error messages before the pipeline runs.
- **[State Management & Observability](../../F-0992-state-management-observability/F-0992-state-management-observability.md)**: Boundary deduplication requires persistent tracking of boundary row identity across pipeline runs, which is provided by the state store. The state store records which rows were loaded near the watermark boundary so that subsequent runs can identify and filter duplicates. Deduplication outcomes are also recorded in the run state for operational visibility.
- **[Data Quality Checks](../F-1086-data-quality-checks/F-1086-data-quality-checks.md)**: Deduplication and Data Quality Checks are complementary mechanisms addressing duplicate data. Data Quality Checks detect and report duplicate rows as advisory findings after loading, while Deduplication actively prevents duplicates from reaching the destination in the first place. Together, they provide both prevention and detection coverage — Deduplication handles known duplicate sources (configuration-defined and boundary overlap), while Data Quality Checks catch any remaining anomalies.

## Scope

### In Scope

- Exact row-level deduplication via table configuration
- Key-based deduplication using user-specified column combinations
- Configuration validation to prevent conflicting deduplication settings
- Automatic boundary deduplication for incremental extraction overlap windows
- Persistent tracking of boundary row identity across pipeline runs

### Out of Scope

- Cross-table or cross-pipeline deduplication
- Fuzzy or approximate matching for near-duplicate detection
- User-defined merge strategies for duplicate resolution (beyond keeping the first occurrence)
- Manual deduplication commands outside the pipeline execution flow
