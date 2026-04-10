---
id: F-0820
type: feature
title: JSONL Structured Logging
status: review
owner: team
created: "2026-04-10T05:44:24.234Z"
updated: "2026-04-10T05:46:05.360Z"
goals: []
---
# JSONL Structured Logging

## Overview

JSONL Structured Logging provides operators with dual-output logging that serves both interactive and automated workflows. During pipeline execution, operators see human-readable log messages on the console for real-time monitoring. Simultaneously, the system writes structured log entries in JSONL format to a dedicated log file (`feather_log.jsonl`), creating a machine-queryable operational history.

This dual approach ensures that operators can monitor pipeline runs interactively while also building a persistent, structured record that can be queried programmatically, piped to external monitoring tools, or ingested into log aggregation platforms.

## Related Specifications

- **[Pipeline Execution](../../../features/F-0300-pipeline-execution/F-0300-pipeline-execution.md)**: Pipeline Execution is the primary producer of the events that JSONL Structured Logging captures. Every stage of the extract → load → transform cycle — including table processing outcomes, row counts, errors, and warnings — generates log entries that this feature formats and persists. The structured log fields (table name, status, row counts, error details) directly reflect the operational data produced during pipeline runs.
- **[Run History & Status](../F-0131-run-history-status/F-0131-run-history-status.md)**: Sibling feature under State Management & Observability. Both features provide operational visibility into pipeline runs, but through complementary mechanisms: Run History & Status persists structured metadata to a queryable state store for historical analysis via CLI commands and SQL, while JSONL Structured Logging provides a real-time, append-only log stream optimized for console monitoring, command-line tools like `jq`, and integration with external log aggregation platforms.
- **[Email Alerting](../../../features/F-1100-email-alerting/F-1100-email-alerting.md)**: Log-based alerting is explicitly out of scope for this feature and is handled by Email Alerting. JSONL Structured Logging provides the operational record of pipeline events, while Email Alerting provides proactive push notifications for critical events such as pipeline failures, data quality issues, and schema changes.
- **[CLI Interface](../../../features/F-1440-cli-interface/F-1440-cli-interface.md)**: The console output component of JSONL Structured Logging operates alongside the CLI Interface's output modes. While the CLI provides `--json` mode for machine-readable command output, JSONL Structured Logging provides the real-time human-readable log stream that operators see during `feather run` execution, as well as the persistent JSONL file for post-hoc analysis.
- **[Retry & Backoff](../F-0378-retry-backoff/F-0378-retry-backoff.md)**: Sibling feature under State Management & Observability. Retry & Backoff decisions — including table skips due to active backoff windows and backoff state resets on successful extraction — are operational events that are captured through the structured logging system, giving operators visibility into which tables were skipped and why.

## User Capabilities

- **Interactive Monitoring**: Operators see clear, human-readable log output on the console while pipelines run, enabling real-time observation of pipeline progress, warnings, and errors.
- **Structured Operational History**: Every significant pipeline event is recorded as a structured JSONL entry containing an ISO timestamp, log level, event message, and contextual fields such as table name, processing status, row counts, and error details.
- **Programmatic Log Querying**: Operators can query the JSONL log file using standard command-line tools (e.g., `jq`, `grep`) or custom scripts to extract specific events, filter by severity, search by table name, or analyze operational trends.
- **External Tool Integration**: The structured log output can be piped to or consumed by external monitoring dashboards, alerting systems, or log aggregation platforms for centralized operational visibility.
- **Reliable Logging Across Runs**: The logging setup is resilient to repeated pipeline invocations within the same process, ensuring that log entries are never duplicated regardless of how many times the pipeline is executed.

## Scope

### In Scope
- Console output for human-readable log messages during pipeline execution
- JSONL file output with structured log entries
- Structured fields in log entries (timestamp, level, message, table name, status, row counts, error details)
- Idempotent logging setup across multiple pipeline runs

### Out of Scope
- Log rotation or archival policies
- Remote log shipping or direct integration with specific monitoring platforms
- Log-based alerting (covered by [Email Alerting](../../../features/F-1100-email-alerting/F-1100-email-alerting.md))
- Interactive log viewing UI
