---
id: R-1222
type: requirement
title: Embedded Database Source Extraction
status: review
owner: speclan
created: "2026-04-10T05:29:44.203Z"
updated: "2026-04-10T05:29:44.203Z"
---
# Embedded Database Source Extraction

Operators can extract data from embedded database files — specifically DuckDB and SQLite databases — as sources for their pipelines. Embedded databases are commonly used for local analytics, application data storage, and portable data distribution. This capability allows operators to connect to these file-based databases and extract table data using the same configuration patterns as other source types.

When a source is configured as DuckDB or SQLite, the system opens the database file at the configured path and provides access to its tables and views. Operators can discover available tables, inspect column schemas, and extract data with filter conditions and column mapping. Because these are file-based databases, they also participate in the file-based change detection lifecycle — the system tracks modification timestamps and content fingerprints to skip extraction when the database file has not changed.

Embedded database sources support the full range of extraction capabilities, including incremental extraction with watermark-based filtering, full extraction, and filtered extraction with custom WHERE clause conditions. Data is returned in the same uniform columnar format as all other source types.

## Acceptance Criteria

- [ ] Operators can configure a DuckDB database file as a pipeline data source
- [ ] Operators can configure a SQLite database file as a pipeline data source
- [ ] The system opens embedded database files and provides access to their tables and views
- [ ] Operators can discover available tables and inspect column schemas in embedded databases
- [ ] Operators can apply filter conditions to restrict extracted rows from embedded database sources
- [ ] Operators can use column mapping to select and rename columns from embedded database sources
- [ ] Embedded database sources support incremental extraction with watermark-based filtering
- [ ] Embedded database sources support file-based change detection for skip-if-unchanged behavior
