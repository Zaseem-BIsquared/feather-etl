---
id: R-0269
type: requirement
title: Exact Row-Level Deduplication
status: review
owner: system
created: "2026-04-10T05:21:08.265Z"
updated: "2026-04-10T05:21:08.265Z"
---
# Exact Row-Level Deduplication

Users can enable exact row-level deduplication for any table by setting a dedup flag in the table configuration. When enabled, the pipeline removes fully identical rows before loading data into the destination, ensuring that no two rows with exactly the same values across all columns are loaded.

This is useful when upstream data sources produce exact duplicate records due to retries, replays, or source-system quirks. The deduplication occurs automatically during pipeline execution — users simply declare the intent in configuration and the pipeline handles the rest. Only the distinct set of rows is forwarded for loading.

## Acceptance Criteria

- [ ] User can enable exact deduplication for a table by setting the dedup option to true in configuration
- [ ] When exact deduplication is enabled, all fully identical rows are reduced to a single row before loading
- [ ] Deduplication preserves all columns and values of the retained rows without alteration
- [ ] Deduplication is applied automatically during pipeline execution without additional user action
- [ ] Tables without the dedup option enabled are not affected by row-level deduplication
