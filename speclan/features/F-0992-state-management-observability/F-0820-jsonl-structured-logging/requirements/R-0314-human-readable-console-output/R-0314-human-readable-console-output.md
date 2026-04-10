---
id: R-0314
type: requirement
title: Human-Readable Console Output
status: review
owner: team
created: "2026-04-10T05:44:33.085Z"
updated: "2026-04-10T05:44:33.085Z"
---
# Human-Readable Console Output

Operators see clear, human-readable log messages on the console during pipeline execution. This provides real-time visibility into pipeline progress, enabling operators to observe which tables are being processed, identify warnings, and spot errors as they occur without needing to inspect any files.

Console log messages display the severity level, a descriptive event message, and relevant contextual information in a format optimized for quick human scanning. Messages are written to the standard output streams appropriate to their severity, ensuring that normal progress information and error details are appropriately separated.

## Acceptance Criteria

- [ ] Pipeline execution produces human-readable log messages on the console
- [ ] Each console message includes the log severity level and a descriptive event message
- [ ] Console output covers key pipeline lifecycle events (start, progress, completion, errors)
- [ ] Warning and error messages are clearly distinguishable from informational messages
- [ ] Console output is legible and scannable during interactive terminal sessions
