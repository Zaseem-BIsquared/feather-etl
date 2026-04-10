---
id: R-0622
type: requirement
title: Run History Browsing
status: review
owner: team
created: "2026-04-10T05:39:44.019Z"
updated: "2026-04-10T05:39:44.019Z"
---
# Run History Browsing

Users can browse recent pipeline run history through the `feather history` command, providing a chronological view of pipeline activity. This allows operators to quickly review what has happened recently, investigate failures, and verify that scheduled runs completed as expected.

The command displays a summary of recent runs in reverse chronological order. Users can narrow results to a specific table using the `--table` filter, which is useful when investigating issues with a particular data source. The `--limit` option controls how many results are shown, allowing users to see just the last few runs or a broader window of activity.

The default output is a human-readable tabular format suitable for terminal viewing, showing key fields like run ID, table name, status, timing, and row counts at a glance.

## Acceptance Criteria

- [ ] The `feather history` command displays recent pipeline runs in reverse chronological order
- [ ] Users can filter history to a specific table using the `--table` option
- [ ] Users can control the number of results displayed using the `--limit` option
- [ ] The default output is a human-readable tabular format showing run ID, table, status, timing, and row counts
- [ ] The command works without any arguments, showing a default number of recent runs across all tables
