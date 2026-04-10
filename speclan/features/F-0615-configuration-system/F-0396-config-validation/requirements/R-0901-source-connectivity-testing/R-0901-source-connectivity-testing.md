---
id: R-0901
type: requirement
title: Source Connectivity Testing
status: review
owner: speclan
created: "2026-04-10T05:36:44.622Z"
updated: "2026-04-10T05:36:44.622Z"
---
# Source Connectivity Testing

Operators can verify that each configured data source is actually reachable from the current environment, catching network, permissions, and credential issues before attempting a pipeline run. This goes beyond structural validation to confirm that the sources described in the configuration are live and accessible.

After all structural validation checks pass, the validation process attempts to connect to each configured data source and reports the connection status. If a source is unreachable — due to network issues, incorrect credentials, permission restrictions, or the source being offline — the operator sees a clear report of which source failed and why. If all sources connect successfully, the operator receives confirmation that connectivity is verified.

Connectivity test results are included in the validation report alongside structural validation results. A connectivity failure does not prevent the rest of the validation from completing; operators see the full picture of both structural issues and connectivity problems.

## Acceptance Criteria

- [ ] The validation process attempts to connect to each configured data source after structural checks pass
- [ ] Operator sees a clear status for each source indicating whether the connection succeeded or failed
- [ ] Connection failure messages include enough detail for the operator to diagnose the issue
- [ ] A connectivity failure for one source does not prevent connectivity testing of other sources
- [ ] Connectivity results are included in the validation report file
- [ ] Connectivity testing is skipped if structural validation of the source definition fails
