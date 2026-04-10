---
id: R-0679
type: requirement
title: Drift Detection and Classification
status: review
owner: speclan
created: "2026-04-10T05:17:57.360Z"
updated: "2026-04-10T05:17:57.360Z"
---
# Drift Detection and Classification

On every extraction after the initial baseline is established, the system automatically compares the current source schema against the stored baseline and classifies every difference into one of three distinct drift categories. This gives operators an immediate, structured understanding of what has changed upstream without requiring manual schema inspection.

The three drift categories are:

- **Added**: A column exists in the current source schema that is not present in the stored baseline. This indicates that the source system has introduced a new field. The destination table is automatically expanded to include the new column, and all previously loaded rows receive NULL values for it.
- **Removed**: A column present in the stored baseline no longer exists in the current source schema. This indicates that the source system has dropped or renamed a field. The destination table retains the column, and incoming rows receive NULL for the missing data — ensuring no historical data is lost.
- **Type Changed**: A column exists in both the baseline and the current source, but its data type has changed. The system attempts to convert values to the expected type. Rows where conversion fails are quarantined rather than loaded with corrupt or truncated data.

Each detected change is reported with the column name, the drift category, and — for type changes — both the original and the new data type. When no differences are found, the system confirms that the schema is stable.

## Acceptance Criteria

- [ ] The system compares the current source schema to the stored baseline on every extraction after the first
- [ ] New columns in the source that are not in the baseline are classified as "added"
- [ ] Columns in the baseline that are missing from the source are classified as "removed"
- [ ] Columns with a different data type than the baseline are classified as "type_changed"
- [ ] Each drift entry includes the affected column name and the drift category
- [ ] Type-change entries include both the original and new data types
- [ ] When no schema differences exist, the system confirms schema stability with no drift reported
