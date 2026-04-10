---
id: F-0615
type: feature
title: Configuration System
status: review
owner: speclan
created: "2026-04-10T04:55:55.246Z"
updated: "2026-04-10T04:57:01.094Z"
goals: []
---
# Configuration System

## Overview

The Configuration System provides operators with a single, declarative file — `feather.yaml` — that fully defines a reproducible data pipeline deployment. By capturing every aspect of the pipeline's behavior in one place — source connections, destination settings, table definitions, schedules, alert routing, operational defaults, and environment mode — operators gain a portable, version-controllable artifact that can be moved between machines, environments, and teams with confidence.

An operator setting up a new deployment copies the `feather.yaml` file to the target machine, sets the required environment variables, and runs the pipeline. No additional manual configuration steps, database seeding, or interactive setup wizards are needed. This design ensures that deployments are repeatable and that the gap between "I have a config file" and "the pipeline is running" is minimal.

## Related Specifications

- **[Pipeline Execution](../F-0300-pipeline-execution/F-0300-pipeline-execution.md)**: The primary consumer of the configuration produced by this system. Pipeline Execution reads the validated configuration to determine which tables to process, what extraction strategies to use, which schedule tiers apply, and what operating mode governs runtime behavior.

## User Capabilities

### Single-File Deployment Definition

Operators define their entire pipeline deployment in a single YAML configuration file. This file serves as the definitive source of truth for what the pipeline does: which source to connect to, where data lands, which tables to process, how often they refresh, who gets alerted on failures, and what operational defaults apply. Because everything lives in one file, operators can review, compare, and version-control their pipeline configuration alongside their project.

### Environment Variable Substitution

Operators keep sensitive or environment-specific values — such as database credentials, API keys, and host addresses — out of the configuration file by using `${VAR_NAME}` placeholder syntax. These placeholders are resolved at load time from the process environment or from `.env` files. If any referenced variable is missing, the system reports a clear error before any pipeline execution begins, preventing silent misconfiguration.

### Automatic Environment File Loading

Operators can place a `.env` file alongside their `feather.yaml` to provide environment variables without setting them at the system level. The system automatically discovers and loads this file during configuration loading, making local development and isolated deployments straightforward. This eliminates the need for external tooling or shell wrapper scripts to inject environment values.

### Portable Path Resolution

All relative paths specified in the configuration file — such as paths to source databases, transform directories, or supplementary files — resolve relative to the location of the `feather.yaml` file itself, not the operator's current working directory. This means operators can invoke the pipeline from any directory, via cron jobs, or through scheduled task runners, and paths will always resolve correctly.

### Scalable Table Definitions

For deployments with many tables (20–30 or more), operators can organize table definitions into separate files within a `tables/` directory alongside the main configuration file. The system automatically discovers and merges these files, allowing teams to manage table configurations modularly — splitting by schema, domain, or owner — without modifying the main configuration file.

### Comprehensive Load-Time Validation

Before any pipeline execution begins, the system validates the entire configuration to catch errors early. Operators receive clear, actionable error messages for issues including: invalid extraction strategies, missing required fields (such as a timestamp column for incremental extraction), invalid schema naming conventions, invalid SQL identifiers in table or column names, unreachable source database paths, and structural problems in the YAML itself. This front-loaded validation prevents wasted time and partial pipeline runs caused by configuration mistakes.

### Operating Mode Selection

Operators designate an operating mode for the deployment (such as development, test, or production) within the configuration. The pipeline adapts its behavior based on this mode — for example, using faster but less durable strategies during development and more robust approaches in production. This allows operators to use the same configuration structure across all environments while the system optimizes for each context.

## Scope

This feature encompasses the definition, loading, resolution, validation, and interpretation of pipeline configuration. Child features are expected to address specific aspects of the configuration lifecycle — such as table definition schema, validation rules, environment resolution, and multi-file configuration management — with their own detailed requirements.

## Anchor

`src/feather_etl/config.py`
