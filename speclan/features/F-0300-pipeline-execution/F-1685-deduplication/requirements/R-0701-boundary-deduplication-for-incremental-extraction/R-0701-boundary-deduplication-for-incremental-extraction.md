---
id: R-0701
type: requirement
title: Boundary Deduplication for Incremental Extraction
status: review
owner: system
created: "2026-04-10T05:21:28.590Z"
updated: "2026-04-10T05:21:28.590Z"
---
# Boundary Deduplication for Incremental Extraction

The pipeline automatically prevents duplicate loading of rows at the boundary of incremental extraction windows. When incremental extraction uses an overlap window, rows that fall exactly on the watermark timestamp boundary may be re-fetched in the next pipeline run. The system identifies these boundary rows, records their identity, and filters them out on subsequent runs so that no row is loaded twice.

This capability works transparently once incremental extraction is configured. The system tracks the identity of boundary rows between runs using stored fingerprints derived from each row's primary key values. On each new run, the pipeline compares incoming boundary rows against the stored fingerprints from the previous run and discards any matches. The stored fingerprints are then updated to reflect the new boundary for the next run.

## Acceptance Criteria

- [ ] Rows that were loaded in a previous run at the watermark boundary are not loaded again in subsequent runs
- [ ] Boundary row identity is determined by the row's primary key values
- [ ] The system persists boundary row fingerprints between pipeline runs so that deduplication survives pipeline restarts
- [ ] Boundary deduplication operates automatically without requiring additional user configuration beyond incremental extraction setup
- [ ] Only rows at the exact watermark boundary are subject to boundary deduplication; rows outside the boundary are unaffected
- [ ] Updated boundary fingerprints replace previous values after each successful pipeline run
- [ ] Boundary deduplication works correctly even when multiple rows share the same watermark timestamp
