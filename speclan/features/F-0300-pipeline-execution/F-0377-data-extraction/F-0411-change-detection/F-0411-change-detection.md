---
id: F-0411
type: feature
title: Change Detection
status: review
owner: speclan
created: "2026-04-10T05:23:53.852Z"
updated: "2026-04-10T05:26:40.181Z"
goals: []
---
# Change Detection

## Overview

Change Detection enables operators to avoid unnecessary re-extraction of data that has not changed since the last pipeline run. When a pipeline executes, the system automatically compares each source's current state against the state recorded from the previous successful extraction. If the source data is unchanged, extraction is skipped entirely — saving time, reducing load on source systems, and avoiding redundant downstream processing.

This capability is particularly valuable for pipelines that run on frequent schedules (e.g., every few minutes or hourly) against sources that change infrequently. Without change detection, every run would re-extract and re-process identical data, wasting compute resources and increasing source system load.

Change detection operates transparently: operators do not need to configure it explicitly. The system selects the appropriate detection strategy based on the source type and extraction configuration. Operators observe the effect through pipeline run logs and status reports that indicate when extraction was skipped due to unchanged data.

## Related Specifications

- **[Data Extraction](../F-0377-data-extraction.md)**: Change Detection is a sub-capability of Data Extraction. It runs before extraction begins for each source and determines whether extraction should proceed or be skipped. The extraction engine consults the change detection result and either performs the extraction or reports that the source is unchanged.
- **[State Management & Observability](../../../F-0992-state-management-observability/F-0992-state-management-observability.md)**: Change detection relies on the state store to persist source fingerprints (modification times, content hashes, checksums) between pipeline runs. After each successful extraction, the current source fingerprint is saved. On the next run, the stored fingerprint is compared against the live source to determine whether data has changed.
- **[Configuration System](../../../F-0615-configuration-system/F-0615-configuration-system.md)**: The extraction strategy configured for each table (full vs. incremental) influences how change detection behaves. Incremental sources delegate skip logic to the watermark mechanism rather than performing independent change detection.
- **[Schema Drift Detection](../../F-1406-schema-drift-detection/F-1406-schema-drift-detection.md)**: Change Detection and Schema Drift Detection are complementary inspection mechanisms that both operate during the extraction phase. Change Detection evaluates whether source *content* has changed (determining whether to skip extraction), while Schema Drift Detection evaluates whether source *structure* has changed (recording drift for operational awareness). Both rely on comparing current source state against a previously stored baseline.
- **[Deduplication](../../F-1685-deduplication/F-1685-deduplication.md)**: When change detection determines that source data has changed and incremental extraction proceeds with an overlap window, Deduplication is responsible for filtering out rows that were already loaded in a previous run. Change Detection and Deduplication are complementary mechanisms in the incremental extraction lifecycle — Change Detection prevents unnecessary extraction, while Deduplication prevents duplicate rows when extraction does occur.
- **[Data Loading](../../F-0405-data-loading/F-0405-data-loading.md)**: When Change Detection determines that source data is unchanged and skips extraction, no loading occurs for that source in the current run. The change detection decision directly controls whether the downstream loading stage executes for each table, making it a gating factor in the extract-load pipeline flow.

## User Capabilities

### Automatic Extraction Skipping

When source data has not changed since the last successful extraction, the system automatically skips re-extraction. Operators see a clear indication in pipeline output that extraction was skipped for a given source, along with the reason (e.g., "source unchanged"). This behavior requires no explicit configuration — it is built into the extraction lifecycle.

### Source-Appropriate Detection

The system uses the most effective change detection approach for each source type. File-based sources are checked using fast filesystem metadata first, with content verification only when needed. Database sources are checked using aggregate checksums that detect both row-level content changes and row count changes. Operators benefit from optimized detection without needing to understand or configure the underlying mechanism.

### Reliable Detection Across Edge Cases

The system correctly handles scenarios that could cause false positives or false negatives. For example, if a file is modified (its timestamp changes) but its content remains identical, extraction is correctly skipped. Conversely, if database rows are modified in ways that a simple count check would miss, the system still detects the change. Operators can trust that the system will extract when — and only when — source data has genuinely changed.

## Scope

This feature covers the detection of source data changes and the decision to skip or proceed with extraction. It includes fingerprint computation for all supported source types, fingerprint persistence and comparison, and the integration with the extraction lifecycle that enables skipping.

This feature does not cover the extraction process itself (handled by [Data Extraction](../F-0377-data-extraction.md)), watermark-based incremental filtering (handled by Data Extraction's incremental extraction capability), or state persistence infrastructure (handled by [State Management & Observability](../../../F-0992-state-management-observability/F-0992-state-management-observability.md)).

## Anchor

`src/feather_etl/sources/file_source.py`
