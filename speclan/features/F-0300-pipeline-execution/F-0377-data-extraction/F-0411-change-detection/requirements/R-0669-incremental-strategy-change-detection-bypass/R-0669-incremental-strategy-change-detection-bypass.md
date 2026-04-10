---
id: R-0669
type: requirement
title: Incremental Strategy Change Detection Bypass
status: review
owner: speclan
created: "2026-04-10T05:24:50.046Z"
updated: "2026-04-10T05:24:50.046Z"
---
# Incremental Strategy Change Detection Bypass

For database sources configured with an incremental extraction strategy, the change detection system always reports the source as "changed," effectively bypassing independent change detection. This is because incremental sources rely on watermark-based filtering to determine which records to extract, and the watermark mechanism inherently handles the decision of whether new data exists. Applying a separate change detection check would be redundant and could interfere with the watermark-driven extraction logic.

Operators configuring a table for incremental extraction can rely on the watermark to manage extraction efficiency. The pipeline will always attempt extraction for incremental sources, but the watermark filter ensures that only new or recently modified records are actually retrieved. If no records fall beyond the watermark boundary, the extraction returns an empty result — which is handled gracefully by downstream stages.

This behavior ensures a clean separation of concerns: change detection governs skip decisions for full-extraction sources, while the watermark governs skip decisions for incremental sources. Operators do not need to understand this distinction — the system automatically applies the correct strategy based on the table's configured extraction mode.

## Acceptance Criteria

- [ ] Database sources configured with incremental extraction strategy always proceed to extraction regardless of change detection
- [ ] Change detection does not compute or compare fingerprints for incremental database sources
- [ ] The watermark-based filtering mechanism governs extraction scope for incremental sources independently of change detection
- [ ] Operators do not need to configure or disable change detection for incremental sources — the bypass is automatic
- [ ] Pipeline output clearly indicates when extraction proceeds for an incremental source (as distinct from a source that changed)
