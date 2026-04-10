---
id: R-0527
type: requirement
title: Table and Schema Discovery
status: review
owner: speclan
created: "2026-04-10T05:29:00.741Z"
updated: "2026-04-10T05:29:00.741Z"
---
# Table and Schema Discovery

Operators can discover the tables (or files) available in a configured source system, along with the column names and data types for each table. This capability supports pipeline setup workflows by allowing operators to inspect what data is available before writing extraction configurations, and it supports operational workflows by enabling verification that source structure matches expectations.

For file-based sources, discovery lists the files (or file groups matching a pattern) that are available at the configured path. For database sources, discovery lists the tables or views accessible through the configured connection. In both cases, column-level schema information — column names and their data types — is included in the discovery result for each table.

Discovery results are presented in a structured format that operators can review interactively (via the CLI) or that other system capabilities (such as schema drift detection) can consume programmatically. The discovery operation reads source metadata without extracting any data rows, making it a lightweight inspection tool.

## Acceptance Criteria

- [ ] Operators can list all available tables or files in a configured source
- [ ] Discovery returns column names and data types for each discovered table
- [ ] File-based source discovery identifies files matching configured path patterns
- [ ] Database source discovery lists accessible tables and views
- [ ] Discovery operates without extracting data rows from the source
- [ ] Discovery results are available in a structured format for both interactive and programmatic use
- [ ] Discovery works consistently across all supported source types
