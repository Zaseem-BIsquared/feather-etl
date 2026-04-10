---
id: R-0051
type: requirement
title: Development Mode Behavior
status: review
owner: system
created: "2026-04-10T05:32:58.026Z"
updated: "2026-04-10T05:32:58.026Z"
---
# Development Mode Behavior

Users can run the pipeline in development mode to get the full iterative workflow with maximum visibility into data at every stage. Development mode is designed for building and refining pipelines, where fast feedback and access to all intermediate data are more important than production efficiency.

In development mode, all extracted columns are landed into a bronze-schema table named after the source. This gives users complete access to the raw data as it was received, making it easy to explore, debug, and understand the source before applying transforms. Silver and gold transforms are created as views rather than physical tables, so changes to transform logic take effect immediately without waiting for data to be re-materialized. This rapid feedback loop lets users iterate quickly on their SQL transforms.

Development mode is the default when no mode is explicitly selected, ensuring that new users and local development workflows get the most forgiving and transparent behavior out of the box.

## Acceptance Criteria

- [ ] All extracted columns from the source are landed into a bronze-schema table
- [ ] The bronze table is named according to the configured source name
- [ ] Silver transforms are created as views rather than physical tables
- [ ] Gold transforms are created as views rather than physical tables
- [ ] Changes to transform SQL are reflected immediately on the next query against the view
- [ ] Users can query bronze tables to inspect raw extracted data
- [ ] Development mode is active by default when no mode is specified
