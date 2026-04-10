---
id: R-0417
type: requirement
title: Database Source Change Detection
status: review
owner: speclan
created: "2026-04-10T05:24:32.552Z"
updated: "2026-04-10T05:24:32.552Z"
---
# Database Source Change Detection

The system detects whether database-backed data sources have changed since the last successful extraction by computing aggregate fingerprints that capture both content changes and row count changes. This ensures that extraction is skipped when database table contents are truly unchanged, while reliably detecting all categories of data modification — including row insertions, deletions, updates, and replacements that leave the row count the same.

When a pipeline run begins for a database source configured with full extraction strategy, the system computes two values against the source table: an aggregate content checksum that reflects the combined state of all rows, and a total row count. Both values must match the corresponding values recorded from the last successful extraction for the source to be considered unchanged. If either value differs, extraction proceeds.

Using both a content checksum and a row count provides robust detection. A content checksum alone could theoretically produce false matches due to hash collisions — two different datasets producing the same checksum. A row count alone would miss any modification that changes row content without adding or removing rows (e.g., updating a field value). By requiring both to match, the system achieves high-confidence change detection suitable for production workloads.

The specific checksum computation is appropriate to each database platform, but the user-observable behavior is consistent: unchanged tables are skipped, and any data modification triggers re-extraction.

After each successful extraction, the system records the current content checksum and row count so they are available for comparison on the next run.

## Acceptance Criteria

- [ ] Extraction is skipped when a database source's content checksum and row count both match the previously recorded values
- [ ] Extraction proceeds when the content checksum differs from the previously recorded value
- [ ] Extraction proceeds when the row count differs from the previously recorded value
- [ ] The system detects row insertions (row count changes)
- [ ] The system detects row deletions (row count changes)
- [ ] The system detects row content updates that do not change the row count (checksum changes)
- [ ] Both the content checksum and row count are recorded after each successful extraction for future comparisons
