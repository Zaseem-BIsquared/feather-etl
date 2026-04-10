---
id: R-0607
type: requirement
title: Key-Based Deduplication
status: review
owner: system
created: "2026-04-10T05:21:14.857Z"
updated: "2026-04-10T05:21:14.857Z"
---
# Key-Based Deduplication

Users can configure key-based deduplication for a table by specifying a list of dedup columns. When configured, the pipeline identifies groups of rows that share the same values across the specified columns and keeps only the first occurrence from each group, discarding subsequent duplicates.

This capability addresses scenarios where rows are not fully identical but represent the same logical entity — for example, records with the same composite key but different metadata or timestamps. Users declare which columns define uniqueness, and the pipeline ensures that only one row per unique key combination is loaded. This gives users precise control over how duplicates are defined for each table.

## Acceptance Criteria

- [ ] User can specify a list of one or more dedup columns in the table configuration
- [ ] When dedup columns are configured, only the first row for each unique combination of those column values is retained
- [ ] Subsequent rows with matching dedup column values are discarded before loading
- [ ] All columns of the retained row (not just the dedup columns) are preserved in the loaded data
- [ ] The dedup column specification supports any column names present in the extracted data
- [ ] Tables without dedup columns configured are not affected by key-based deduplication
