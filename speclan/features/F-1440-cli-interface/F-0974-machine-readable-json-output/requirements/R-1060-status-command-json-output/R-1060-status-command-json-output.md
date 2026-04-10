---
id: R-1060
type: requirement
title: Status Command JSON Output
status: review
owner: team
created: "2026-04-10T05:54:02.433Z"
updated: "2026-04-10T05:54:02.433Z"
---
# Status Command JSON Output

When the status command is executed with `--json`, it emits one JSON object per table providing a structured snapshot of each table's current state. This allows monitoring dashboards, alerting systems, and LLM agents to programmatically assess pipeline health without parsing tabular text output.

Each emitted object includes the table name, the timestamp of the last run, the current status, the watermark position (indicating how far ingestion has progressed), and the number of rows loaded in the most recent run. This information gives consumers a complete picture of each table's operational state.

Automation systems can use this output to detect stale tables (last run too long ago), failed tables (error status), or tables that have fallen behind (watermark not advancing), enabling proactive alerting and self-healing workflows.

## Acceptance Criteria

- [ ] Each table in the pipeline produces exactly one JSON object on stdout
- [ ] Each object includes the table name
- [ ] Each object includes the timestamp of the most recent run
- [ ] Each object includes the current status of the table
- [ ] Each object includes the watermark position for the table
- [ ] Each object includes the row count from the most recent run
