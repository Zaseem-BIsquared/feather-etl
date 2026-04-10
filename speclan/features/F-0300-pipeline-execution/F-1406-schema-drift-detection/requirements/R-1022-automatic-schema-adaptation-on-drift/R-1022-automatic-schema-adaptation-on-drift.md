---
id: R-1022
type: requirement
title: Automatic Schema Adaptation on Drift
status: review
owner: speclan
created: "2026-04-10T05:18:07.483Z"
updated: "2026-04-10T05:18:07.483Z"
---
# Automatic Schema Adaptation on Drift

When schema drift is detected, the system automatically adapts its behavior to handle each category of change without operator intervention, ensuring that data continues to flow through the pipeline even when the source schema evolves. This automatic handling means operators are informed of changes but do not need to take immediate corrective action to keep the pipeline running.

For added columns, the destination table is automatically expanded to include the new column. All previously loaded historical rows receive NULL values for the new column, reflecting that the data did not exist at the time those rows were originally extracted. New rows contain the actual values from the source.

For removed columns, the destination table retains the column from the original schema. Since the source no longer provides data for this column, incoming rows are loaded with NULL values in that position. Historical data in the column remains intact and queryable, preserving the complete record.

For type-changed columns, the system attempts to convert each value from the new source type to the expected destination type. Values that convert successfully are loaded normally. Values that fail conversion are quarantined — routed to a separate holding area rather than loaded into the destination table — so that operators can review and remediate them without risking data corruption in the main dataset.

## Acceptance Criteria

- [ ] Added columns automatically result in the destination table gaining the new column
- [ ] Historical rows in the destination receive NULL for newly added columns
- [ ] Removed columns remain in the destination table and are not dropped
- [ ] Incoming rows for removed columns are loaded with NULL values
- [ ] Historical data in removed columns remains intact and queryable
- [ ] Type-changed columns trigger automatic value conversion attempts
- [ ] Rows that fail type conversion are quarantined instead of being loaded into the destination
- [ ] Successfully converted rows are loaded normally into the destination table
