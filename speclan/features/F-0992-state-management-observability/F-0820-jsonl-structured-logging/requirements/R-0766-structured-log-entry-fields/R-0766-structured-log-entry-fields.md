---
id: R-0766
type: requirement
title: Structured Log Entry Fields
status: review
owner: team
created: "2026-04-10T05:44:45.789Z"
updated: "2026-04-10T05:44:45.789Z"
---
# Structured Log Entry Fields

Each JSONL log entry contains a consistent set of core fields plus optional contextual fields that provide rich operational detail. This structure enables operators to filter, query, and analyze log data by time, severity, event type, or specific pipeline context such as table name or row counts.

Core fields present in every entry ensure baseline queryability, while optional structured fields capture context-specific details relevant to particular pipeline events. For example, a data loading event may include the target table name, number of rows loaded, and processing status, while an error event may include error details and the operation that failed.

## Acceptance Criteria

- [ ] Every JSONL log entry includes an ISO 8601 formatted timestamp
- [ ] Every JSONL log entry includes the log level (e.g., INFO, WARNING, ERROR)
- [ ] Every JSONL log entry includes a human-readable event message
- [ ] Log entries for table-related operations include the table name as a structured field
- [ ] Log entries for data loading events include the number of rows loaded
- [ ] Log entries for processing events include a status indicator (e.g., success, failure, skipped)
- [ ] Log entries for error events include error detail information
