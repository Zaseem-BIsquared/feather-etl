---
id: R-0167
type: requirement
title: Silver Layer Canonical Views
status: review
owner: speclan
created: "2026-04-10T05:10:17.051Z"
updated: "2026-04-10T05:10:17.051Z"
---
# Silver Layer Canonical Views

Operators can create silver-layer transforms that produce standardized, canonical views over raw source data. Silver transforms provide a clean, consistent interface by normalizing column names and formatting, making downstream analysis and reporting easier to build and maintain.

Silver-layer transforms are authored as plain SQL files placed in the designated silver directory. Each silver transform always produces a database view — never a materialized table. Because views are lazy and always reflect the current state of the underlying data, silver transforms require no scheduled rebuilds and impose no pipeline execution overhead. Operators can add, modify, or remove silver transforms simply by editing SQL files, with changes taking effect the next time the transform layer is set up.

Silver transforms may reference raw source tables or other silver-layer transforms, enabling operators to build layered canonical views that progressively refine data. The resulting views serve as the foundation for gold-layer analytical datasets.

## Acceptance Criteria

- [ ] Operator can create a silver transform by placing a SQL file in the silver transforms directory
- [ ] Every silver transform produces a database view, never a materialized table
- [ ] Silver views always reflect the current state of the underlying source data without requiring a rebuild
- [ ] Silver transforms can reference raw source tables (e.g., bronze-layer data)
- [ ] Silver transforms can reference other silver transforms
- [ ] Modifying a silver SQL file and re-running setup updates the corresponding view definition
- [ ] Removing a silver SQL file results in the corresponding view no longer being created
