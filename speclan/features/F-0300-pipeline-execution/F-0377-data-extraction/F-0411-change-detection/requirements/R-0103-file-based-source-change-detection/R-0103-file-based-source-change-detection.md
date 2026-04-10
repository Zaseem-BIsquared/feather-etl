---
id: R-0103
type: requirement
title: File-Based Source Change Detection
status: review
owner: speclan
created: "2026-04-10T05:24:15.602Z"
updated: "2026-04-10T05:24:15.602Z"
---
# File-Based Source Change Detection

The system detects whether file-based data sources have changed since the last successful extraction using a two-tier verification approach. This ensures that extraction is skipped when file content is truly unchanged, even in scenarios where the file has been "touched" (its modification timestamp updated) without any actual content modification. Operators benefit from fast, reliable change detection that minimizes unnecessary extraction runs.

When a pipeline run begins for a file-based source, the system first compares the file's current modification timestamp against the timestamp recorded from the last successful extraction. If the timestamp has not changed, the source is immediately considered unchanged and extraction is skipped — this provides a fast, low-cost check that avoids reading file contents in the common case. If the timestamp has changed, the system reads the file and computes a content fingerprint to determine whether the actual data differs from the previously recorded fingerprint. Only if the content fingerprint differs does the system proceed with extraction.

This two-tier approach optimizes for the common case (file unchanged, skip quickly) while correctly handling edge cases such as files that are touched without modification, files rewritten with identical content, or files replaced with new content at the same path.

After each successful extraction, the system records both the current modification timestamp and the content fingerprint so they are available for comparison on the next run.

## Acceptance Criteria

- [ ] Extraction is skipped when a file-based source has not been modified since the last successful extraction
- [ ] The system checks the file's modification timestamp as a fast first-pass detection
- [ ] When the modification timestamp is unchanged, the file is considered unchanged without reading its contents
- [ ] When the modification timestamp has changed, the system computes a content fingerprint to verify whether actual data changed
- [ ] Extraction is skipped when the modification timestamp changed but the content fingerprint matches the previously recorded value
- [ ] Extraction proceeds when the content fingerprint differs from the previously recorded value
- [ ] Both the modification timestamp and content fingerprint are recorded after each successful extraction for use in future comparisons
