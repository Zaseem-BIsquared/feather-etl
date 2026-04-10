---
id: F-0992
type: feature
title: State Management & Observability
status: draft
owner: team
created: "2026-04-10T04:57:51.015Z"
updated: "2026-04-10T04:58:44.109Z"
goals: []
---
# State Management & Observability

## Overview

State Management & Observability provides a persistent operational record that survives data rebuilds. Users maintain a dedicated state store — separate from the analytical data — that tracks extraction progress, run history, data quality results, and schema snapshots. Because the state store is independent, users can safely delete and rebuild their data without losing operational history or breaking future pipeline runs.

## Related Specifications

- **[Pipeline Execution](../F-0300-pipeline-execution/F-0300-pipeline-execution.md)**: The primary producer of state data. Every pipeline run records its extraction progress, run metadata, data quality results, and schema snapshots into the state store managed by this feature. Pipeline Execution depends on the watermark-based progress tracking provided here to determine where each extraction should resume.
- **[Configuration System](../F-0615-configuration-system/F-0615-configuration-system.md)**: Provides the validated configuration that determines which tables and pipelines exist, informing the structure of progress tracking and run history within the state store. State initialization during `feather setup` or `feather run` operates on the configuration produced by this system.

## User Capabilities

### Automatic & Explicit State Initialization
Users receive a ready-to-use state store whenever they run a pipeline for the first time. The state store is created automatically during `feather run` or can be set up in advance with `feather setup`. Initialization is idempotent — running it multiple times is always safe and produces the same result. On Unix systems, the state file is created with owner-only permissions, protecting operational data from other users on shared machines.

### Resilient Extraction Progress Tracking
Users benefit from watermark-based progress tracking that guarantees no data window is silently skipped. Watermarks — the single source of truth for "where did we leave off" — advance only when an entire pipeline step completes successfully. If a run is interrupted or fails partway through, the next run automatically picks up from the last fully-completed position, so users never have partial or missing data windows.

### Run History & Operational Visibility
Users can observe the history of pipeline runs, including when each run occurred, what was processed, and what the outcome was. This operational visibility lets users diagnose problems, audit processing history, and verify that pipelines are running as expected.

### Data Quality Result Tracking
Users can review the results of data quality checks across runs. Quality results are preserved in the state store, giving users a longitudinal view of data health over time and the ability to detect emerging quality trends.

### Schema Snapshot Tracking
Users can see how source schemas have changed over time. The state store captures schema snapshots, enabling users to understand when upstream schema changes occurred and correlate them with data quality or pipeline behavior changes.

### Version Safety
The state store is versioned from its first use. If a user attempts to run an older version of the tool against a state store created by a newer version, the tool refuses to proceed — preventing silent corruption or data loss from version mismatches. Users receive a clear message explaining the incompatibility.

### Independent Lifecycle
Because the state store is a separate file from the analytical data, users can delete and fully rebuild their data store at any time without losing extraction progress, run history, quality results, or schema snapshots. This independence gives users confidence to experiment with data rebuilds, schema migrations, or fresh loads without sacrificing operational continuity.

## Scope

This feature encompasses all capabilities related to the persistent state store, including its creation, versioning, progress tracking, and observability. It is organized as a parent feature with child sub-features covering specific aspects of state management.

## Out of Scope

- The analytical data store and its schema
- Pipeline execution logic (covered by [Pipeline Execution](../F-0300-pipeline-execution/F-0300-pipeline-execution.md))
- Configuration file format and loading (covered by [Configuration System](../F-0615-configuration-system/F-0615-configuration-system.md))
