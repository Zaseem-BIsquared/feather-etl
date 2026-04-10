---
id: R-0532
type: requirement
title: Source Definition Validation
status: review
owner: speclan
created: "2026-04-10T05:36:23.116Z"
updated: "2026-04-10T05:36:23.116Z"
---
# Source Definition Validation

Operators are informed when their configured data source definitions are incomplete, incorrectly specified, or reference nonexistent locations. This prevents pipeline failures caused by the system being unable to locate or connect to source data.

The validation process checks each configured source against the rules appropriate for its type. For file-based sources such as CSV, Excel, and JSON, the system verifies that the specified source path exists and is a directory. For embedded database sources such as DuckDB and SQLite, the system verifies that the specified source path exists and is a file. For network database sources, the system verifies that the necessary connection details (host, port, credentials, database name) are present. If the declared source type is not one of the recognized types, the operator receives an error identifying the unrecognized value.

All source-related errors are reported together so that operators can fix every source issue in a single pass rather than discovering them one at a time.

## Acceptance Criteria

- [ ] Operator receives an error when a source type is not one of the recognized source types
- [ ] Operator receives an error when a file-based source path does not exist or is not a directory
- [ ] Operator receives an error when an embedded database source path does not exist or is not a file
- [ ] Operator receives an error when a network database source is missing required connection details
- [ ] All source validation errors are reported together in a single validation run
- [ ] Error messages identify which source definition contains the problem
