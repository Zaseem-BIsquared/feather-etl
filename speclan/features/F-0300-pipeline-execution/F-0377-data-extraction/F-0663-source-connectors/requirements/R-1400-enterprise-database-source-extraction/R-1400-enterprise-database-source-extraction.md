---
id: R-1400
type: requirement
title: Enterprise Database Source Extraction
status: review
owner: speclan
created: "2026-04-10T05:29:52.706Z"
updated: "2026-04-10T05:29:52.706Z"
---
# Enterprise Database Source Extraction

Operators can extract data from enterprise database systems — specifically SQL Server and PostgreSQL — as sources for their pipelines. Enterprise databases are the backbone of most organizational data infrastructure, and this capability allows operators to build pipelines that pull data directly from production or replica database instances.

When a source is configured as SQL Server or PostgreSQL, the system establishes a connection using the configured connection string and provides access to the database's tables and views. Operators can discover available tables, inspect column schemas, and extract data using the full range of extraction modes — full extraction, incremental extraction with watermark-based filtering, and filtered extraction with custom WHERE clause conditions.

Database sources support batched data retrieval, where the system reads data in configurable chunk sizes rather than loading entire result sets into memory. This makes extraction feasible for very large tables containing millions of rows. Watermark values are formatted appropriately for each database system's date and timestamp handling conventions, ensuring correct incremental filtering regardless of database-specific behavior.

Database sources participate in the database-oriented change detection lifecycle — the system computes aggregate checksums to determine whether source data has changed since the last extraction, enabling skip-if-unchanged behavior.

## Acceptance Criteria

- [ ] Operators can configure a SQL Server database as a pipeline data source
- [ ] Operators can configure a PostgreSQL database as a pipeline data source
- [ ] The system establishes connections using configured connection details
- [ ] Operators can discover available tables and views and inspect their column schemas
- [ ] Operators can apply filter conditions to restrict extracted rows from database sources
- [ ] Operators can use column mapping to select and rename columns from database sources
- [ ] Database sources support incremental extraction with watermark-based filtering
- [ ] Watermark values are formatted correctly for each database system's conventions
- [ ] Data retrieval uses configurable batch sizes to handle large tables without excessive memory use
- [ ] Database sources support change detection for skip-if-unchanged behavior
