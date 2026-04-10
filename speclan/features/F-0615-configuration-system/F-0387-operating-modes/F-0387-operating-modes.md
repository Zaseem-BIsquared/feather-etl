---
id: F-0387
type: feature
title: Operating Modes
status: review
owner: system
created: "2026-04-10T05:32:41.278Z"
updated: "2026-04-10T05:34:51.512Z"
goals: []
---
# Operating Modes

## Overview

Operating Modes allow users to run the same pipeline configuration across development, testing, and production environments without duplicating or modifying table or column definitions. By selecting a mode, users control how the pipeline behaves — where data lands, how transforms are materialized, and whether row limits apply — while keeping a single, shared YAML configuration file.

This capability eliminates the need to maintain separate configuration files per environment. Users write their pipeline definition once and switch between fast iterative development, limited-row test runs, and optimized production execution simply by changing the active mode.

## Related Specifications

- **[Pipeline Execution](../../../features/F-0300-pipeline-execution/F-0300-pipeline-execution.md)**: Operating Modes directly governs how Pipeline Execution orchestrates each run. The active mode determines whether extraction targets the bronze or silver layer, whether transforms are materialized as tables or views, and whether row limits are applied — all decisions that Pipeline Execution enforces during the extract → load → transform cycle.
- **[CLI Interface](../../../features/F-1440-cli-interface/F-1440-cli-interface.md)**: The CLI provides the highest-priority mechanism for mode selection through a command-line flag. Operators can override the configured or environment-variable-specified mode for a single run directly from the `feather` command, making the CLI the primary interactive control point for mode switching.
- **[SQL Transforms](../../../features/F-0300-pipeline-execution/F-0631-sql-transforms/F-0631-sql-transforms.md)**: Operating Modes controls how SQL Transforms materializes gold-layer transforms. In production mode, gold transforms marked for materialization are rebuilt as physical tables after each run; in development and test modes, all transforms are created as lightweight views regardless of materialization settings, enabling faster iteration.
- **[Data Loading](../../../features/F-0300-pipeline-execution/F-0405-data-loading/F-0405-data-loading.md)**: The active operating mode determines the data landing strategy that Data Loading follows. In development and test modes, all extracted columns land in the bronze schema; in production mode, extraction skips the bronze layer and loads only column-mapped columns directly into the silver schema.
- **[Data Extraction](../../../features/F-0300-pipeline-execution/F-0377-data-extraction/F-0377-data-extraction.md)**: Operating Modes affects Data Extraction behavior in two ways: test mode applies a configured row limit to constrain extraction volume, and production mode activates column map filtering so that only specified columns are extracted rather than the full source schema.

## Modes

### Development Mode
Development mode provides the full iterative workflow. All extracted columns land in a bronze schema, and silver/gold transforms are created as views for rapid feedback. This lets users experiment freely with transforms and inspect intermediate data at every stage.

### Production Mode
Production mode optimizes for efficiency and control. Extraction skips the bronze layer and lands only the columns specified in the column map directly into the silver schema. Gold transforms marked for materialization are rebuilt as tables after each run, ensuring downstream consumers read from performant, physical tables.

### Test Mode
Test mode mirrors the development workflow but automatically applies a configured row limit. This allows users to validate their full pipeline logic quickly using a representative subset of data, making it ideal for CI pipelines and pre-deployment checks.

## Mode Selection

Users select the active mode through a clear priority chain. A command-line flag takes highest precedence, followed by an environment variable, then the mode declared in the YAML configuration file, and finally a sensible default. This layered approach gives users flexibility: teams can set a default in their config, override it per-environment with a variable, or force a specific mode for a single run via the CLI.

## Scope

- Selecting and switching between operating modes
- Mode-specific pipeline behavior differences
- Mode resolution priority when multiple sources specify a mode
- Default mode when no explicit selection is made
