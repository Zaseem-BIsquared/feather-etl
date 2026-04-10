---
id: R-0090
type: requirement
title: Production Mode Behavior
status: review
owner: system
created: "2026-04-10T05:33:05.575Z"
updated: "2026-04-10T05:33:05.575Z"
---
# Production Mode Behavior

Users can run the pipeline in production mode to optimize for efficiency and controlled data delivery. Production mode is designed for scheduled, automated runs where only the necessary columns are extracted and gold outputs are materialized for downstream consumers.

In production mode, the pipeline skips the bronze layer entirely. Instead of landing all columns into a staging area, only the columns specified in the column map are extracted and loaded directly into a silver-schema table named after the source. This reduces storage, processing time, and unnecessary data exposure in production environments. Gold transforms that are marked for materialization are rebuilt as physical tables after each pipeline run, ensuring that downstream dashboards, reports, and applications read from performant, pre-computed tables rather than views.

Gold transforms that are not marked for materialization remain as views, giving users fine-grained control over which outputs justify the cost of physical table rebuilds.

## Acceptance Criteria

- [ ] No bronze-schema table is created during production pipeline runs
- [ ] Only columns defined in the column map are extracted from the source
- [ ] Extracted data lands directly into a silver-schema table named after the source
- [ ] Gold transforms marked for materialization are rebuilt as physical tables after each run
- [ ] Gold transforms not marked for materialization remain as views
- [ ] The pipeline completes without requiring a bronze schema to exist
- [ ] Users can distinguish which gold outputs will be materialized before running the pipeline
