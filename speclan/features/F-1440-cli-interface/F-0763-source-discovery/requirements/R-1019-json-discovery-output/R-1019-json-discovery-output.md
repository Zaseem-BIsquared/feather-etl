---
id: R-1019
type: requirement
title: JSON Discovery Output
status: review
owner: speclan
created: "2026-04-10T05:51:06.205Z"
updated: "2026-04-10T05:51:06.205Z"
---
# JSON Discovery Output

Operators can request discovery results in a structured JSON format by using the `--json` flag with the `feather discover` command. This machine-readable output enables automation tools, CI/CD pipelines, and scripting workflows to programmatically consume and process the list of discovered tables and their schemas.

When JSON output is enabled, each table is represented as a structured object containing the table's qualified name and an array of column definitions. Each column definition includes the column name and its data type. The JSON output replaces the default human-readable format entirely, ensuring clean output that can be parsed without filtering out decorative text or formatting.

This capability supports use cases such as automated pipeline configuration generation, schema comparison scripts, and integration with other tooling that operates on source metadata.

## Acceptance Criteria

- [ ] The `--json` flag produces structured JSON output for discovery results
- [ ] Each table object in the JSON output contains the table name
- [ ] Each table object contains an array of column definitions with name and type
- [ ] JSON output suppresses all human-readable formatting and decorative text
- [ ] The JSON output is valid, parseable JSON
- [ ] The `--json` flag follows the same convention used by other CLI commands
