---
id: F-0378
type: feature
title: Retry & Backoff
status: draft
owner: spec-agent
created: "2026-04-10T05:41:52.379Z"
updated: "2026-04-10T05:43:41.899Z"
goals: []
---
# Retry & Backoff

## Overview

Retry & Backoff provides automatic retry management for tables that experience persistent extraction failures. Rather than allowing a single failing table to repeatedly hammer the source system on every scheduled pipeline run, this feature introduces a graduated cooldown period that increases with each consecutive failure.

## Related Specifications

- **[Data Extraction](../../../features/F-0300-pipeline-execution/F-0377-data-extraction/F-0377-data-extraction.md)**: Retry & Backoff is triggered by extraction failures reported during the Data Extraction stage. When a table fails to extract — whether due to source connectivity issues, query errors, or timeouts — this feature tracks the failure and computes the backoff window before the next attempt. The extraction engine consults the backoff state to determine whether a table should be attempted or skipped on each run.
- **[Pipeline Execution](../../../features/F-0300-pipeline-execution/F-0300-pipeline-execution.md)**: Pipeline Execution orchestrates independent table processing and invokes Retry & Backoff logic to decide which tables are eligible for extraction on each run. Tables within their backoff window are skipped during pipeline execution without affecting other tables.
- **[Run History & Status](../F-0131-run-history-status/F-0131-run-history-status.md)**: Sibling feature under State Management & Observability. Run History & Status records the outcomes of each pipeline run, including which tables were skipped due to backoff. Retry & Backoff relies on persisted failure counts in the state store to maintain accurate consecutive-failure tracking across pipeline runs.
- **[Email Alerting](../../../features/F-1100-email-alerting/F-1100-email-alerting.md)**: When tables enter backoff due to repeated failures, Email Alerting can notify operators of the persistent failure condition. Retry & Backoff and Email Alerting are complementary responses to extraction failures — backoff protects the source system while alerting ensures operators are aware of the issue.
- **[Source Connectors](../../../features/F-0300-pipeline-execution/F-0377-data-extraction/F-0663-source-connectors/F-0663-source-connectors.md)**: Source Connectors are the components that produce the extraction failures which trigger backoff. Connector-level errors — such as unreachable databases, authentication failures, or file access errors — are the primary failure signals that Retry & Backoff consumes.

## User Capability

Operators benefit from a self-healing pipeline that gracefully handles transient and semi-transient failures at the individual table level. When a table fails during extraction, the system automatically tracks the failure and assigns a progressively longer waiting period before the next retry attempt. This means:

- **Failing tables cool down automatically** — no manual intervention is needed to prevent repeated failing requests against the source system.
- **Healthy tables are unaffected** — failures in one table never delay or block extraction of other tables.
- **Recovery is automatic** — once a table succeeds again, its backoff state is fully cleared and it resumes normal scheduling.
- **Backoff is predictable** — wait times increase linearly (15 minutes per consecutive failure) up to a known maximum of 120 minutes, making behavior easy to reason about and communicate to stakeholders.

## Scope

This feature covers:

- Tracking per-table failure counts across pipeline runs
- Computing and enforcing graduated backoff periods after failures
- Skipping tables that are still within their backoff window
- Resetting retry state upon successful extraction
- Ensuring complete isolation between tables so one table's failures have no side effects on others

## Backoff Progression

| Consecutive Failures | Wait Before Next Retry |
|---------------------|----------------------|
| 1 | 15 minutes |
| 2 | 30 minutes |
| 3 | 45 minutes |
| 4 | 60 minutes |
| 5 | 75 minutes |
| 6 | 90 minutes |
| 7 | 105 minutes |
| 8+ | 120 minutes (cap) |
