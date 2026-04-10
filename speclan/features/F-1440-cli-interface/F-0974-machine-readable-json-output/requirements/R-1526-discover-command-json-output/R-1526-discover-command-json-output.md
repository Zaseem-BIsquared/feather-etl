---
id: R-1526
type: requirement
title: Discover Command JSON Output
status: review
owner: team
created: "2026-04-10T05:54:07.770Z"
updated: "2026-04-10T05:54:07.770Z"
---
# Discover Command JSON Output

When the discover command is executed with `--json`, it emits one JSON object per discovered table, providing structured schema information including the table name and its column definitions. This enables automation tools to programmatically inspect available source tables and their schemas for configuration generation, validation, and documentation.

Each emitted object includes the table name and a list of columns, where each column entry includes the column name and its data type. This structured schema representation allows LLM agents and scaffolding tools to auto-generate pipeline configurations, detect schema changes, and validate compatibility between sources and destinations.

The output covers all discoverable tables in the source, giving consumers a complete catalog of available data without requiring manual exploration or parsing of formatted text tables.

## Acceptance Criteria

- [ ] Each discovered table produces exactly one JSON object on stdout
- [ ] Each object includes the table name
- [ ] Each object includes a list of column definitions
- [ ] Each column definition includes the column name
- [ ] Each column definition includes the column data type
- [ ] Tables with no columns produce an object with an empty columns list
