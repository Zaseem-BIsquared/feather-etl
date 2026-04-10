---
id: R-0871
type: requirement
title: Pre-Discovery Connectivity Check
status: review
owner: speclan
created: "2026-04-10T05:51:00.755Z"
updated: "2026-04-10T05:51:00.755Z"
---
# Pre-Discovery Connectivity Check

Before performing any metadata discovery, the system automatically verifies that the configured source system is reachable and accessible. This upfront check ensures operators receive a clear and immediate diagnosis when connectivity is the problem, rather than encountering ambiguous errors during the discovery process itself.

When the connectivity check fails, the command exits immediately with a distinct exit code (exit code 2) that differentiates source connectivity failures from other error types. The operator receives a meaningful error message indicating the source could not be reached, allowing them to troubleshoot connection settings, network access, or credentials before retrying.

This behavior prevents operators from mistaking a connectivity problem for an empty source system or a misconfigured table filter, saving troubleshooting time and providing clear, actionable feedback.

## Acceptance Criteria

- [ ] The system verifies source connectivity before attempting table discovery
- [ ] A failed connectivity check produces a clear error message indicating the source is unreachable
- [ ] A failed connectivity check causes the command to exit with exit code 2
- [ ] No partial discovery results are produced when the connectivity check fails
- [ ] A successful connectivity check proceeds silently into the discovery phase
- [ ] The error message provides enough context for the operator to begin troubleshooting
