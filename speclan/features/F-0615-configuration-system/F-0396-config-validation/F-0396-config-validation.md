---
id: F-0396
type: feature
title: Config Validation
status: review
owner: speclan
created: "2026-04-10T05:35:54.232Z"
updated: "2026-04-10T05:38:42.512Z"
goals: []
---
# Config Validation

## Overview

Config Validation gives operators a dedicated pre-flight check — invoked through the `feather validate` command — that thoroughly examines the pipeline configuration before any data is touched. Rather than discovering misconfigurations mid-run (when tables may have already been partially processed), operators can surface every issue up front, fix them in one pass, and proceed with confidence.

The validation step parses the configuration file, resolves all environment variables and relative paths, and then applies a comprehensive suite of checks covering source definitions, destination settings, table definitions, extraction strategies, column specifications, and naming conventions. After completing all checks, the system writes a structured validation report alongside the configuration file so that operators — and any surrounding automation — can inspect the results programmatically.

## Related Specifications

- **[Configuration System](../F-0615-configuration-system.md)**: Config Validation is the enforcement layer of the Configuration System. It ensures that the declarative configuration produced by operators conforms to all rules and constraints before the pipeline acts on it.
- **[Pipeline Execution](../../F-0300-pipeline-execution/F-0300-pipeline-execution.md)**: Pipeline Execution depends on validated configuration. Running validation before execution prevents partial runs caused by configuration errors discovered mid-flight.
- **[CLI Interface](../../F-1440-cli-interface/F-1440-cli-interface.md)**: The `feather validate` command is the user-facing entry point that triggers configuration validation.
- **[Operating Modes](../F-0387-operating-modes/F-0387-operating-modes.md)**: Config Validation verifies that the operating mode specified in the configuration is valid. Since operating mode selection affects extraction targets, transform materialization, and row limits, catching an invalid mode during validation prevents surprising behavior at runtime.
- **[Source Connectors](../../F-0300-pipeline-execution/F-0377-data-extraction/F-0663-source-connectors/F-0663-source-connectors.md)**: Config Validation exercises source connector connectivity verification during its pre-flight checks. When the validator tests whether each configured data source is reachable, it delegates to the appropriate source connector to perform the actual connection test.
- **[Data Quality Checks](../../F-0300-pipeline-execution/F-1086-data-quality-checks/F-1086-data-quality-checks.md)**: Config Validation checks the validity of declarative quality check definitions — such as null checks, uniqueness constraints, and deduplication settings — that operators configure per table. Catching malformed or conflicting quality check configurations during validation prevents silent quality monitoring gaps at runtime.

## User Capabilities

### On-Demand Configuration Verification

Operators invoke `feather validate` at any time to check their configuration without running the pipeline. This is especially valuable after editing the configuration file, when setting up a new deployment, or as a gate in a deployment script. The command reports all detected issues at once, enabling operators to fix multiple problems in a single editing pass rather than encountering them one at a time during pipeline runs.

### Comprehensive Error Detection

The validation process examines every facet of the configuration that could cause a runtime failure or data integrity issue. Operators receive clear, specific feedback about problems including: unrecognized source types, missing source paths, absent connection details for database sources, nonexistent destination directories, invalid extraction strategies, missing timestamp columns for time-based strategies, incorrect schema prefixes on target tables, invalid SQL identifiers in table or column names, conflicting deduplication settings, and out-of-range numeric parameters.

### Source Connectivity Verification

Beyond structural checks, the validation process attempts to connect to each configured data source and reports whether the connection succeeded or failed. This tells operators not just that the configuration is well-formed, but that the sources it references are actually reachable from the current environment — catching network, permissions, and credential issues before a pipeline run is attempted.

### Machine-Readable Validation Report

After validation completes, the system writes a structured report file (`feather_validation.json`) alongside the configuration file. This report includes the validation outcome, all resolved paths, any errors or warnings, source connectivity results, and a timestamp. Operators can inspect this file directly, and automation tools — such as deployment pipelines or monitoring scripts — can parse it to make go/no-go decisions without scraping command output.

## Scope

This feature covers the complete pre-execution validation lifecycle: parsing and resolving the configuration, applying all validation rules, testing source connectivity, and producing the validation report. It does not cover runtime re-validation during pipeline execution or live configuration reloading.

## Anchor

`src/feather_etl/config.py`
