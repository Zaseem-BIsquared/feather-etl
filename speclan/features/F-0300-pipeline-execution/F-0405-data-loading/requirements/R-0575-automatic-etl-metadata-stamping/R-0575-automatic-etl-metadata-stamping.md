---
id: R-0575
type: requirement
title: Automatic ETL Metadata Stamping
status: review
owner: speclan
created: "2026-04-10T05:07:52.932Z"
updated: "2026-04-10T05:07:52.932Z"
---
# Automatic ETL Metadata Stamping

Every row loaded into the destination database is automatically enriched with metadata columns that identify when the row was loaded and which pipeline run produced it. This gives operators full traceability from any individual row back to the exact pipeline execution that created it, without requiring manual configuration or additional processing steps.

Two metadata columns are added to every loaded row, regardless of which loading strategy is used. The first records the timestamp at which the row was loaded into the destination, and the second records a unique identifier for the pipeline run. These columns are added transparently by the loading process — operators do not need to define them in source configurations, column maps, or table schemas.

Operators can use these metadata columns to answer operational questions such as: when was this row last refreshed, which pipeline run loaded it, are there rows from a failed or partial run that need investigation, and how fresh is the data in a given table. The metadata supports data lineage, debugging, and compliance reporting across the analytical environment.

## Acceptance Criteria

- [ ] Every loaded row includes a metadata column recording the timestamp at which it was loaded
- [ ] Every loaded row includes a metadata column recording the unique identifier of the pipeline run that loaded it
- [ ] Metadata columns are added automatically without any operator configuration
- [ ] Metadata columns are present regardless of which loading strategy (full, incremental, or append) is used
- [ ] The load timestamp reflects the actual time of the loading operation
- [ ] The run identifier is consistent across all rows loaded in the same pipeline run
