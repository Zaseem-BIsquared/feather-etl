---
id: R-1014
type: requirement
title: Run Command JSON Output
status: review
owner: team
created: "2026-04-10T05:53:56.777Z"
updated: "2026-04-10T05:53:56.777Z"
---
# Run Command JSON Output

When the run command is executed with `--json`, it emits one JSON object per table processed, providing structured details about the execution outcome for each table. This enables automation systems to track per-table success or failure, count rows loaded, and capture error details without parsing log output.

Each emitted object includes the table name, the execution status (e.g., success or failure), the number of rows loaded, and an error message field that is populated when a table fails. Objects are emitted as each table completes, allowing consumers to monitor progress in real time during multi-table pipeline runs.

If a table encounters an error, the corresponding JSON object includes the error details while the pipeline continues processing remaining tables. This allows CI/CD systems to identify exactly which tables failed and why, enabling targeted remediation.

## Acceptance Criteria

- [ ] Each processed table produces exactly one JSON object on stdout
- [ ] Each object includes the table name identifying which table was processed
- [ ] Each object includes the execution status indicating success or failure
- [ ] Each object includes the count of rows loaded during the run
- [ ] Each object includes an error message field that is null on success and populated on failure
- [ ] Objects are emitted incrementally as each table completes processing
