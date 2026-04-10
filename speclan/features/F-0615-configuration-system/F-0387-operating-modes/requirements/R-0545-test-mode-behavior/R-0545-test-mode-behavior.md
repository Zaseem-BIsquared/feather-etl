---
id: R-0545
type: requirement
title: Test Mode Behavior
status: review
owner: system
created: "2026-04-10T05:33:13.163Z"
updated: "2026-04-10T05:33:13.163Z"
---
# Test Mode Behavior

Users can run the pipeline in test mode to validate their full pipeline logic quickly using a limited subset of data. Test mode mirrors the development workflow — landing all columns into bronze and creating transforms as views — but automatically applies a configured row limit to extracted data.

This mode is designed for continuous integration pipelines, pre-deployment validation, and quick sanity checks where users need to confirm that their configuration, transforms, and data quality checks all work correctly without processing the full dataset. By capping the number of rows extracted, test runs complete significantly faster while still exercising every stage of the pipeline.

The row limit is drawn from the defaults section of the pipeline configuration, giving teams a consistent, predictable test dataset size across runs. Users can adjust this limit in their configuration to balance between speed and data representativeness.

## Acceptance Criteria

- [ ] Test mode follows the same bronze/silver/gold workflow as development mode
- [ ] Extraction is limited to the number of rows specified in the configuration defaults
- [ ] All pipeline stages (extraction, loading, transforms, quality checks) execute with the limited dataset
- [ ] Test mode completes faster than an equivalent development mode run on the full dataset
- [ ] The row limit is configurable in the pipeline YAML configuration
- [ ] Users receive clear feedback about the row limit being applied during test runs
