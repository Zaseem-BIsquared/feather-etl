---
id: R-1546
type: requirement
title: Destination Validation
status: review
owner: speclan
created: "2026-04-10T05:37:08.396Z"
updated: "2026-04-10T05:37:08.396Z"
---
# Destination Validation

Operators are informed when the configured destination directory does not exist or is not accessible, preventing pipeline failures during the data loading phase. This ensures the pipeline has a valid place to write output before any extraction work begins.

The validation process checks that the destination directory specified in the configuration exists and is a valid directory on the file system. If the destination path is missing or points to a non-directory location, the operator receives a clear error message identifying the problem. This check uses the resolved absolute path (after environment variable substitution and relative path resolution) to ensure accuracy.

## Acceptance Criteria

- [ ] Operator receives an error when the configured destination directory does not exist
- [ ] Operator receives an error when the configured destination path exists but is not a directory
- [ ] The destination check uses the fully resolved absolute path
- [ ] The error message identifies the resolved destination path that failed validation
