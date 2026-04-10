---
id: R-0917
type: requirement
title: Multi-File Source Change Tracking
status: review
owner: speclan
created: "2026-04-10T05:25:07.016Z"
updated: "2026-04-10T05:25:07.016Z"
---
# Multi-File Source Change Tracking

When a file-based source is configured with a pattern that matches multiple files (e.g., a glob pattern matching all CSV files in a directory), the system tracks change state independently for each individual file rather than treating the entire set as a single unit. This enables the system to detect changes at per-file granularity, correctly identifying when individual files within a collection have been added, removed, or modified.

Operators working with file collections — such as a directory of daily CSV exports or a set of data files from multiple upstream systems — benefit from precise change detection. If only one file in a collection of hundreds has changed, the system detects exactly which file changed. This per-file tracking state is persisted between runs so that the system can compare each file's current state against its previously recorded state.

When new files appear that match the pattern, they are detected as new (no prior recorded state exists) and extraction proceeds. When previously tracked files are removed, the system recognizes their absence. When existing files are modified, the same two-tier detection logic (modification timestamp then content fingerprint) applies to each file individually.

The per-file state is stored in a structured format that maps each file path to its recorded modification timestamp and content fingerprint. This allows efficient comparison even when the file collection is large.

## Acceptance Criteria

- [ ] Each file matching a multi-file source pattern is tracked independently for change detection
- [ ] A change in one file within a collection is detected without requiring re-evaluation of unchanged files' content
- [ ] New files that appear and match the pattern are detected as changed (no prior state)
- [ ] Removal of previously tracked files is recognized by the system
- [ ] Per-file change state (modification timestamp and content fingerprint) is persisted between pipeline runs
- [ ] The two-tier detection approach (timestamp first, then content fingerprint) applies to each individual file in the collection
