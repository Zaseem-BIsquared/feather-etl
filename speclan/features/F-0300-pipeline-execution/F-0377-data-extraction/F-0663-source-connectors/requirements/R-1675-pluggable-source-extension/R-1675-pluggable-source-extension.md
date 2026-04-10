---
id: R-1675
type: requirement
title: Pluggable Source Extension
status: review
owner: speclan
created: "2026-04-10T05:30:02.712Z"
updated: "2026-04-10T05:30:02.712Z"
---
# Pluggable Source Extension

Teams can extend the system with support for new data source types by implementing a well-defined connector contract and registering the new connector. This extensibility ensures that the system can grow to accommodate new source systems as an organization's data landscape evolves, without requiring modifications to existing connectors or to the pipeline execution engine.

The connector contract defines a small set of operations that every source must support: connectivity verification, table and schema discovery, data extraction, change detection, and schema inspection. The contract uses structural typing — a new connector only needs to implement the expected operations with the correct signatures; it does not need to inherit from or extend any specific base. This minimizes coupling and makes connector development straightforward.

For common source categories, the system provides shared foundation capabilities that new connectors can build upon. File-based connectors can leverage shared file change detection (modification timestamp and content hash tracking) and filter condition handling. Database connectors can leverage shared connection string management and watermark formatting. These shared capabilities significantly reduce the amount of work required to build a new connector — a new file-based connector requires minimal implementation effort, and a new database connector requires only moderately more.

Once registered, a new connector is immediately available for use in pipeline configurations and supports all standard pipeline operations — extraction, change detection, discovery, and schema inspection — just like the built-in connectors.

## Acceptance Criteria

- [ ] New source connectors can be added by implementing a defined set of operations (connectivity check, discovery, extraction, change detection, schema inspection)
- [ ] New connectors are not required to inherit from or extend any specific base type
- [ ] File-based connectors can leverage shared change detection and filter handling capabilities
- [ ] Database connectors can leverage shared connection management and watermark formatting capabilities
- [ ] A registered connector is available for use in pipeline configurations immediately
- [ ] Custom connectors support all standard pipeline operations (extraction, discovery, change detection, schema inspection)
- [ ] Adding a new connector does not require modifications to existing connectors or the pipeline engine
