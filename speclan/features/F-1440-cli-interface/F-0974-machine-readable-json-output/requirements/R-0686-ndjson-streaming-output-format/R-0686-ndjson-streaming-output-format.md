---
id: R-0686
type: requirement
title: NDJSON Streaming Output Format
status: review
owner: team
created: "2026-04-10T05:53:47.095Z"
updated: "2026-04-10T05:53:47.095Z"
---
# NDJSON Streaming Output Format

JSON output uses the Newline-Delimited JSON (NDJSON) format, where each line of stdout contains exactly one complete, self-contained JSON object. This streaming-friendly format allows consumers to process results incrementally as they arrive rather than waiting for the entire output to complete.

Each line is a valid JSON object terminated by a newline character. There is no wrapping array, no commas between lines, and no opening/closing brackets around the full output. This means consumers can parse each line independently, enabling real-time progress monitoring during long-running operations and efficient memory usage for large result sets.

The format is particularly valuable for pipeline execution where tables are processed sequentially — consumers see each table's result as soon as it completes rather than waiting for the entire pipeline to finish.

## Acceptance Criteria

- [ ] Each line of JSON output is a complete, independently parseable JSON object
- [ ] Lines are separated by newline characters with no trailing commas or array delimiters
- [ ] Output can be processed line-by-line by standard tools (e.g., piping through line-oriented filters)
- [ ] JSON objects are emitted as soon as their data is available, not buffered until command completion
- [ ] No JSON array wrapper encloses the full output stream
