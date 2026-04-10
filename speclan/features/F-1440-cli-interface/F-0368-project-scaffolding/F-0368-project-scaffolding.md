---
id: F-0368
type: feature
title: Project Scaffolding
status: draft
owner: speclan
created: "2026-04-10T05:46:56.102Z"
updated: "2026-04-10T05:49:21.393Z"
goals: []
---
# Project Scaffolding

## Overview

Project Scaffolding is the starting point for every new client onboarding. Operators run `feather init` to create a ready-to-customize project directory containing all the files needed for a working data pipeline deployment. Rather than manually creating configuration files and remembering required settings, operators receive a complete set of starter files with documented examples and sensible defaults — allowing them to move straight into editing their pipeline configuration and running their first extraction.

This feature eliminates setup friction and ensures consistency across client projects by producing the same reliable starting point every time.

## Related Specifications

- **[CLI Interface](../F-1440-cli-interface.md)**: Project Scaffolding is a command within the CLI Interface, accessible as `feather init`. It follows the CLI's conventions for argument handling, `--json` output mode, and exit code semantics.
- **[Configuration System](../../../features/F-0615-configuration-system/F-0615-configuration-system.md)**: The scaffolded `feather.yaml` file is the primary artifact consumed by the Configuration System. The template provides commented examples covering all supported source types, giving operators a self-documenting starting point for pipeline configuration.
- **[Source Connectors](../../../features/F-0300-pipeline-execution/F-0377-data-extraction/F-0663-source-connectors/F-0663-source-connectors.md)**: The scaffolded configuration file includes commented examples for every supported source type — CSV, JSON, Excel, DuckDB, SQLite, SQL Server, and PostgreSQL. These examples reflect the connection patterns and settings defined by the Source Connectors feature, ensuring that the starter configuration accurately documents each connector's configuration interface.
- **[Email Alerting](../../../features/F-1100-email-alerting/F-1100-email-alerting.md)**: The scaffolded `.env` template includes placeholder credentials for alert integrations, specifically SMTP connection details used by the Email Alerting feature. This gives operators a visible starting point for configuring email notifications as part of their initial project setup.
- **[Config Validation](../../../features/F-0615-configuration-system/F-0396-config-validation/F-0396-config-validation.md)**: After scaffolding a project, operators typically run `feather validate` to verify their edited configuration before executing their first pipeline run. Config Validation is the natural next step in the onboarding workflow that begins with Project Scaffolding.

## User Capabilities

### New Project Creation

Operators can create a new project by providing a project name as an argument to `feather init`. If no name is provided, the system prompts the operator interactively for a project name. The system creates a new directory named after the project and populates it with all necessary starter files.

### Starter Configuration File

The scaffolded project includes a configuration file (`feather.yaml`) pre-populated with commented examples for every supported source type, including file-based sources and database connections. Operators can uncomment and modify the relevant sections for their use case rather than writing configuration from scratch.

### Dependency and Environment Files

The scaffolded project includes a Python project file declaring the ETL tool as a dependency, a version control ignore file configured for common generated artifacts, and an environment variable template with placeholder credentials for all supported database platforms and alert integrations.

### Safety Validation

Before creating files, the system checks whether the target directory already contains non-hidden files. If it does, the operation is refused with a clear error message, preventing accidental overwriting of existing work.

### Creation Reporting

After scaffolding completes, the system reports which files were created, giving the operator a clear summary of their new project's contents. When `--json` output mode is enabled, this report is emitted as structured data suitable for consumption by automation tools.

## Scope

This feature covers the `feather init` command and the project scaffolding workflow. It does not cover the content validation of configuration files after editing (see [Config Validation](../../../features/F-0615-configuration-system/F-0396-config-validation/F-0396-config-validation.md)) or the runtime behavior of any scaffolded file.

## Anchor

`src/feather_etl/init_wizard.py`
