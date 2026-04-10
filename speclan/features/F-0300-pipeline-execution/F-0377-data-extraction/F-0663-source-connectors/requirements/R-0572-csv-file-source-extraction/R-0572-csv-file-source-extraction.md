---
id: R-0572
type: requirement
title: CSV File Source Extraction
status: review
owner: speclan
created: "2026-04-10T05:29:09.277Z"
updated: "2026-04-10T05:29:09.277Z"
---
# CSV File Source Extraction

Operators can extract data from CSV files as a source for their pipelines. CSV is one of the most common data exchange formats, and this capability allows operators to ingest data from flat-file exports, scheduled data drops, and other systems that produce CSV output.

When a source is configured as CSV, the system reads the specified file and returns its contents as a structured, columnar dataset with appropriate data types inferred from the file content. Operators can configure filter conditions (expressed as WHERE clauses) to restrict which rows are extracted, and can use column mapping to select and rename specific columns.

CSV sources support glob patterns (e.g., `sales_*.csv`, `region_??_export.csv`) in the file path configuration, allowing operators to treat multiple files matching a naming convention as a single logical table. When a glob pattern is used, all matching files are read and their contents are combined into a single result set. This is especially useful for source systems that produce partitioned or time-stamped output files.

CSV sources participate in the standard change detection lifecycle — the system tracks file modification timestamps and content fingerprints to skip extraction when files have not changed.

## Acceptance Criteria

- [ ] Operators can configure a CSV file as a pipeline data source
- [ ] The system reads CSV files and returns data as a structured columnar dataset
- [ ] Data types are inferred appropriately from CSV file content
- [ ] Operators can apply filter conditions to restrict extracted rows
- [ ] Operators can use column mapping to select and rename columns from CSV sources
- [ ] Glob patterns in the file path are resolved to all matching files
- [ ] Multiple files matching a glob pattern are combined into a single result set
- [ ] CSV sources support change detection for skip-if-unchanged behavior
