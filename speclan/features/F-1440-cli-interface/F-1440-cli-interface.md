---
id: F-1440
type: feature
title: CLI Interface
status: review
owner: speclan
created: "2026-04-10T05:02:46.600Z"
updated: "2026-04-10T05:03:55.437Z"
goals: []
---
# CLI Interface

## Overview

The CLI Interface is the single point of interaction for all operators working with the ETL system. Every operational action — from initializing a new project to monitoring run history — is available as a dedicated command through the `feather` command-line tool. Operators do not need to write scripts, import libraries, or interact with any programmatic API to perform day-to-day operations.

The CLI is designed around a workflow-oriented command set that mirrors the natural progression of setting up and operating a data pipeline: initialize a project, configure it, validate the configuration, discover available data sources, set up the target environment, run extractions, and monitor results.

## Related Specifications

- **[Pipeline Execution](../F-0300-pipeline-execution/F-0300-pipeline-execution.md)**: The CLI's `feather run` command delegates to Pipeline Execution for all extract → load → transform orchestration. The `feather status` and `feather history` commands surface run metadata produced by Pipeline Execution, and the `--json` output mode and semantic exit codes allow automation tools to interpret pipeline run outcomes programmatically.
- **[Configuration System](../F-0615-configuration-system/F-0615-configuration-system.md)**: The CLI depends on the Configuration System for loading and validating `feather.yaml`. The `feather validate` command triggers configuration validation, `feather init` scaffolds the initial configuration file, and the global `--config` flag selects which configuration file to load — all operating on the configuration artifact defined by this system.
- **[State Management & Observability](../F-0992-state-management-observability/F-0992-state-management-observability.md)**: The CLI's `feather setup` command initializes the state store managed by this feature, and the `feather status` and `feather history` commands query the state store to provide operators with run history and pipeline health visibility directly in the terminal.

## User Capabilities

### Project Initialization

Operators can scaffold a new client project using `feather init`. This generates the starting directory structure and default configuration files needed to begin defining a pipeline, giving operators a ready-to-customize starting point without manual file creation.

### Configuration Validation

Operators can validate their pipeline configuration using `feather validate`. The system parses the configuration file, tests the source connection, and produces a structured validation report. This allows operators to catch configuration errors and connectivity issues before attempting a full pipeline run.

### Source Discovery

Operators can explore available data in a connected source system using `feather discover`. The system lists all accessible tables along with their column names and data types. This helps operators understand what data is available and plan their pipeline configuration accordingly.

### Environment Setup

Operators can prepare the target environment using `feather setup`. This initializes the state tracking database, creates necessary schemas, and applies any configured transformations. Operators run this once when standing up a new environment or after making structural configuration changes.

### Pipeline Execution

Operators can trigger data extraction using `feather run`. They can optionally scope a run to specific tables or execution modes using filters. This is the primary command for moving data from source systems into the analytical environment.

### Run Status Monitoring

Operators can check the current state of their pipeline using `feather status`, which shows the last run status for each configured table. For deeper investigation, `feather history` provides a historical log of runs with filtering by table and result count. Together, these commands give operators visibility into pipeline health without leaving the terminal.

### Configurable Config File Path

All commands accept a `--config` option to specify an alternative configuration file location, defaulting to `feather.yaml` in the current directory. This allows operators to manage multiple pipeline configurations or work from non-standard directory layouts.

### Machine-Readable Output

Any command can produce machine-readable output in newline-delimited JSON (NDJSON) format using the `--json` flag. When enabled, the system suppresses human-formatted output and emits structured JSON records, one per line. This enables automation tools, CI/CD pipelines, and LLM-based agents to consume CLI output programmatically without parsing human-readable text.

### Semantic Exit Codes

The CLI communicates outcome status through well-defined exit codes. Operators and automation scripts can reliably distinguish between successful completion, configuration or validation errors, and source connection failures based on the exit code alone, without needing to parse output text.

## Scope

This feature encompasses the command-line interface layer — the set of commands, global options, output formatting modes, and exit code conventions that operators interact with directly. The underlying pipeline logic, state management, configuration parsing, and alerting capabilities are specified as separate sibling features. The CLI acts as a thin orchestration layer that delegates all substantive work to those capabilities.

## Anchor

`src/feather_etl/cli.py`
