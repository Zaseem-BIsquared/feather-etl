---
id: R-1013
type: requirement
title: Programmatic Log Querying
status: review
owner: team
created: "2026-04-10T05:44:51.264Z"
updated: "2026-04-10T05:44:51.264Z"
---
# Programmatic Log Querying

Operators can query the JSONL log file using standard command-line tools or custom scripts to extract specific events, filter by severity, search by table name, or analyze operational trends. The structured format makes the log file a first-class data source for operational analytics and troubleshooting.

Because each log entry is a self-contained JSON object on its own line, operators can use tools like `jq` to filter entries by any field, `grep` to search for specific patterns, or write scripts in any language to parse and aggregate log data. This supports a wide range of operational workflows, from ad-hoc debugging to automated reporting.

## Acceptance Criteria

- [ ] The JSONL log file can be parsed line-by-line with standard JSON parsers
- [ ] Operators can filter log entries by log level using standard tools (e.g., `jq`)
- [ ] Operators can search for entries related to a specific table by querying the table name field
- [ ] Operators can extract all error entries with their associated details
- [ ] The log format supports piping to external monitoring or log aggregation tools
