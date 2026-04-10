---
id: R-1081
type: requirement
title: Environment-Aware Transform Execution
status: review
owner: speclan
created: "2026-04-10T05:10:39.848Z"
updated: "2026-04-10T05:10:39.848Z"
---
# Environment-Aware Transform Execution

The system adapts its transform execution strategy based on the current environment mode, ensuring that production environments maintain up-to-date materialized data while development and test environments prioritize speed and lightweight resource usage.

In production mode, materialized gold tables are automatically rebuilt after every successful data extraction run. This ensures that analytical datasets always reflect the latest source data, keeping dashboards and reports current without requiring operators to manually trigger rebuilds. Non-materialized transforms (both silver and gold views) require no rebuild since they always reflect current data.

In development and test modes, all transforms — including those annotated for materialization — are created as views. This eliminates the overhead of table rebuilds during iterative development, allowing operators to test and refine their transform SQL quickly. The operator's materialization annotations are preserved in the SQL files but are not acted upon until the transforms run in production mode.

## Acceptance Criteria

- [ ] In production mode, materialized gold transforms produce tables that are rebuilt after every successful extraction run
- [ ] In production mode, non-materialized gold transforms and all silver transforms remain as views
- [ ] In development mode, all transforms are created as views regardless of materialization annotations
- [ ] In test mode, all transforms are created as views regardless of materialization annotations
- [ ] Materialization annotations in SQL files are preserved and respected only when running in production mode
- [ ] Operators do not need to manually trigger transform rebuilds in production — rebuilds happen automatically after extraction
