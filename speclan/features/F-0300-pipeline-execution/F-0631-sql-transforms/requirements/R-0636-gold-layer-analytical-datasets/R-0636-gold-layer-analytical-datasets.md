---
id: R-0636
type: requirement
title: Gold Layer Analytical Datasets
status: review
owner: speclan
created: "2026-04-10T05:10:24.187Z"
updated: "2026-04-10T05:10:24.187Z"
---
# Gold Layer Analytical Datasets

Operators can create gold-layer transforms that produce analysis-ready datasets optimized for dashboards, reports, and downstream consumption. Gold transforms combine, aggregate, and reshape data from silver-layer views or other gold transforms into purpose-built analytical datasets.

Gold-layer transforms are authored as plain SQL files placed in the designated gold directory. By default, each gold transform produces a database view. However, when dashboard query performance requires it, operators can opt into materialization by adding a simple annotation within the SQL file, causing the system to create a table instead of a view. This gives operators explicit control over the trade-off between always-current data (views) and faster query performance (materialized tables).

Materialized gold tables contain a snapshot of the query results at the time they were last built. Non-materialized gold transforms behave like silver views — always current and requiring no rebuild step. Operators choose materialization on a per-transform basis depending on the performance needs of the consuming dashboards or reports.

## Acceptance Criteria

- [ ] Operator can create a gold transform by placing a SQL file in the gold transforms directory
- [ ] Gold transforms produce database views by default
- [ ] Operator can annotate a gold transform SQL file to request materialization as a table
- [ ] Materialized gold transforms produce a database table containing a snapshot of query results
- [ ] Non-materialized gold transforms produce a view that always reflects current upstream data
- [ ] Gold transforms can reference silver-layer transforms
- [ ] Gold transforms can reference other gold-layer transforms
