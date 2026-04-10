---
id: R-0426
type: requirement
title: Global JSON Flag Availability
status: review
owner: team
created: "2026-04-10T05:53:32.793Z"
updated: "2026-04-10T05:53:32.793Z"
---
# Global JSON Flag Availability

Every CLI command supports a `--json` flag that switches the command's output from human-readable text to structured JSON. This provides a single, consistent mechanism for automated consumers to request machine-readable output regardless of which command they invoke.

When a user or automation script appends `--json` to any command, the entire stdout output switches to structured JSON format. The flag behaves identically across all commands — there are no commands that silently ignore it or produce partial JSON. If a command has no meaningful structured data to emit, it emits an empty NDJSON stream rather than falling back to text.

The flag is documented in each command's help text and in the global help output, making it discoverable for new users and automation authors.

## Acceptance Criteria

- [ ] The `--json` flag is accepted by every CLI command without error
- [ ] Adding `--json` to any command produces only valid JSON on stdout
- [ ] The `--json` flag appears in the global help output and each command's help text
- [ ] Commands that accept `--json` never mix human-readable text with JSON on stdout
- [ ] The flag can be placed before or after the command's positional arguments
- [ ] Running a command with `--json` and no matching data produces an empty output (no JSON lines) rather than an error
