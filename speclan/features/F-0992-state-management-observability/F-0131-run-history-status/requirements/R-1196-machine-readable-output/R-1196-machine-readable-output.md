---
id: R-1196
type: requirement
title: Machine-Readable Output
status: review
owner: team
created: "2026-04-10T05:39:55.547Z"
updated: "2026-04-10T05:39:55.547Z"
---
# Machine-Readable Output

Both the `feather history` and `feather status` commands support a `--json` output flag, enabling machine parsing for integration with external scripts, monitoring dashboards, and automation workflows. This ensures that operational data is not locked into human-readable terminal output and can be programmatically consumed.

When `--json` is specified, the command output is valid JSON containing the same data as the tabular format. This allows operators to pipe output into tools like `jq` for filtering, feed it into monitoring systems, or incorporate it into automated health-check scripts that trigger alerts or reports.

## Acceptance Criteria

- [ ] The `feather history` command accepts a `--json` flag that produces valid JSON output
- [ ] The `feather status` command accepts a `--json` flag that produces valid JSON output
- [ ] JSON output contains the same informational fields as the human-readable tabular output
- [ ] JSON output is well-formed and parseable by standard JSON tools
- [ ] The `--json` flag can be combined with other command options (e.g., `--table`, `--limit`)
