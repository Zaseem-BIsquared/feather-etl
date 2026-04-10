---
id: F-0974
type: feature
title: Machine-Readable JSON Output
status: draft
owner: team
created: "2026-04-10T05:53:16.079Z"
updated: "2026-04-10T05:55:22.369Z"
goals: []
---
# Machine-Readable JSON Output

## Overview

Machine-Readable JSON Output provides a universal `--json` flag across all CLI commands that switches output from human-readable text to structured, newline-delimited JSON (NDJSON) on stdout. This capability enables LLM agents, CI/CD pipelines, and automation scripts to parse command results programmatically without scraping or interpreting human-readable text.

## Related Specifications

- **[Pipeline Execution](../../../features/F-0300-pipeline-execution/F-0300-pipeline-execution.md)**: The `feather run` command's JSON output emits per-table progress and result objects — including table name, status, row counts, and error details — that directly reflect the operational data produced during pipeline execution. The structured JSON schema for run output is shaped by the events and outcomes that Pipeline Execution generates.
- **[Run History & Status](../../../features/F-0992-state-management-observability/F-0131-run-history-status/F-0131-run-history-status.md)**: The `feather status` and `feather history` commands support `--json` mode, emitting per-table status and run history objects as NDJSON. Machine-Readable JSON Output defines the output format contract, while Run History & Status provides the underlying data — last run times, watermark positions, row counts, and quality check results — that populates these JSON objects.
- **[Source Discovery](../F-0763-source-discovery/F-0763-source-discovery.md)**: The `feather discover` command's JSON output emits per-table schema objects containing table names and column definitions with names and types. Machine-Readable JSON Output provides the `--json` flag and NDJSON format, while Source Discovery defines the specific schema introspection data that populates the structured output.
- **[JSONL Structured Logging](../../../features/F-0992-state-management-observability/F-0820-jsonl-structured-logging/F-0820-jsonl-structured-logging.md)**: Both features produce structured JSON output, but through complementary channels and for different purposes. Machine-Readable JSON Output sends command results to stdout for programmatic consumption by automation tools, while JSONL Structured Logging writes operational event logs to a persistent file and human-readable messages to stderr. The stdout/stderr separation ensures these two JSON streams do not interfere with each other during pipeline execution.
- **[Project Scaffolding](../F-0368-project-scaffolding/F-0368-project-scaffolding.md)**: The `feather init` command supports `--json` mode to emit a structured creation report listing scaffolded files, enabling automation tools to programmatically verify project initialization results.

## User Value

Operators and automated systems need a reliable, stable contract for consuming CLI output. Human-readable text is fragile — formatting changes break parsers, and extracting structured data from tables or prose is error-prone. The `--json` flag provides a well-defined output contract that automated consumers can depend on, making the CLI a first-class integration point for orchestration workflows, monitoring dashboards, and agent-driven pipelines.

## Scope

- **Global flag**: The `--json` flag is available on every CLI command and consistently switches output to structured JSON
- **Streaming format**: Output uses NDJSON (one JSON object per line) rather than a single JSON array, enabling consumers to process results incrementally as they stream in
- **Command-specific schemas**: Each command emits JSON objects with well-defined, documented fields appropriate to that command's purpose
- **Stdout separation**: JSON output goes to stdout while logs and diagnostics remain on stderr, allowing clean piping and redirection

## Key Commands

- **Run**: Emits per-table progress and result objects including table name, status, row counts, and error details
- **Status**: Emits per-table status objects including last run time, current status, watermark position, and row counts
- **Discover**: Emits per-table schema objects including table name and column definitions with names and types
- **All other commands**: Each emits structured objects appropriate to their function, following consistent field naming conventions
