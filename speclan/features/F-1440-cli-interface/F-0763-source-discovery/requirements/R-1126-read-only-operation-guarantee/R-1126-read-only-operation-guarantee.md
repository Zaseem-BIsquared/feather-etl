---
id: R-1126
type: requirement
title: Read-Only Operation Guarantee
status: review
owner: speclan
created: "2026-04-10T05:51:12.148Z"
updated: "2026-04-10T05:51:12.148Z"
---
# Read-Only Operation Guarantee

The discovery command is strictly read-only — it retrieves metadata about available tables and their schemas without extracting, modifying, or loading any actual data. Operators can safely run discovery at any time, including in production environments, with confidence that no data movement or state changes will occur.

This guarantee is essential for operators who need to explore source systems during planning phases, validate available data before committing to pipeline configuration changes, or audit what tables are accessible without triggering any side effects. The command does not write to the target system, does not update state tracking, and does not create or modify any pipeline artifacts.

## Acceptance Criteria

- [ ] The discover command does not extract any row-level data from the source
- [ ] The discover command does not write any data to the target system
- [ ] The discover command does not modify pipeline state or run history
- [ ] The discover command can be run repeatedly without cumulative side effects
- [ ] The discover command does not create, modify, or delete any configuration files
