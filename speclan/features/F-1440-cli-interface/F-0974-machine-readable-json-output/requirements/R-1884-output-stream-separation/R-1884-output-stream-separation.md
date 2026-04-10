---
id: R-1884
type: requirement
title: Output Stream Separation
status: review
owner: team
created: "2026-04-10T05:54:16.363Z"
updated: "2026-04-10T05:54:16.363Z"
---
# Output Stream Separation

When the `--json` flag is active, structured JSON output is written exclusively to stdout while all logs, warnings, progress indicators, and diagnostic messages are directed to stderr. This clean separation ensures that consumers can pipe or redirect stdout to receive pure, parseable JSON without contamination from non-JSON content.

This separation is critical for reliable automation. A CI/CD script can capture stdout into a file or pipe it to a JSON processor and be confident that every line is valid JSON. Meanwhile, operators can still observe logs and diagnostics on stderr for troubleshooting, and logging verbosity settings continue to work independently of the JSON output flag.

Without this separation, a single log line mixed into stdout would break JSON parsers and cause automation failures. The strict stdout/stderr contract makes the CLI a dependable building block in automated workflows.

## Acceptance Criteria

- [ ] All structured JSON output appears exclusively on stdout when `--json` is active
- [ ] Log messages, warnings, and progress output appear on stderr, not stdout
- [ ] Piping stdout to a JSON parser produces no parse errors from non-JSON content
- [ ] Diagnostic output on stderr does not interfere with JSON output on stdout
- [ ] Error conditions produce JSON error objects on stdout in addition to any stderr diagnostics
- [ ] Redirecting stdout to a file captures only valid NDJSON content
