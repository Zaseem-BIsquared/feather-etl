---
id: R-0543
type: requirement
title: Column Schema Inspection
status: review
owner: speclan
created: "2026-04-10T05:50:53.350Z"
updated: "2026-04-10T05:50:53.350Z"
---
# Column Schema Inspection

For each discovered table, operators can see the column names and their associated data types. This schema detail helps operators understand the structure and content of source tables, enabling informed decisions about column selection, type mapping, and transformation planning when configuring their pipeline.

Each table's output includes a per-column breakdown showing the column name and its data type as understood by the source system. For database sources, data types reflect the source database's type system (e.g., `varchar`, `int`, `datetime`). For file-based sources, data types are inferred from the file content, providing operators with a best-effort type assessment for each column.

Columns are presented in a consistent order for each table, making it straightforward for operators to compare table structures and identify the columns they need for their pipeline.

## Acceptance Criteria

- [ ] Each listed table includes its column names in the discovery output
- [ ] Each column displays its associated data type
- [ ] Database source columns show data types from the source database's type system
- [ ] File-based source columns show inferred data types based on file content analysis
- [ ] Columns are displayed in a consistent, predictable order for each table
- [ ] Tables with many columns display all columns without truncation
