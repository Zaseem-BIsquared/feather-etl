---
id: R-0661
type: requirement
title: Deduplication Configuration Validation
status: review
owner: system
created: "2026-04-10T05:21:21.278Z"
updated: "2026-04-10T05:21:21.278Z"
---
# Deduplication Configuration Validation

The system validates deduplication configuration to prevent conflicting settings. Exact row-level deduplication and key-based deduplication are mutually exclusive options — a table cannot have both enabled simultaneously. When a user attempts to configure both options for the same table, the system rejects the configuration and provides a clear error message explaining the conflict.

This validation protects users from ambiguous or unintended deduplication behavior. By enforcing mutual exclusivity upfront, the system ensures that the deduplication intent for each table is unambiguous and that pipeline execution proceeds with a well-defined deduplication strategy.

## Acceptance Criteria

- [ ] The system rejects a table configuration that specifies both exact deduplication and dedup columns simultaneously
- [ ] The validation error message clearly identifies the conflicting settings and the affected table
- [ ] Validation occurs before pipeline execution begins, preventing partial processing
- [ ] A table configuration with only exact deduplication enabled passes validation
- [ ] A table configuration with only dedup columns specified passes validation
- [ ] A table configuration with neither deduplication option passes validation
