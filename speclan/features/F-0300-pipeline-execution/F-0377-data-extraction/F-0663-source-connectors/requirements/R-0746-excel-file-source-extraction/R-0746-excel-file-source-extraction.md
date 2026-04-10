---
id: R-0746
type: requirement
title: Excel File Source Extraction
status: review
owner: speclan
created: "2026-04-10T05:29:15.570Z"
updated: "2026-04-10T05:29:15.570Z"
---
# Excel File Source Extraction

Operators can extract data from Excel spreadsheet files as a source for their pipelines. Excel is widely used for reporting, data collection, and manual data management across organizations, and this capability allows operators to incorporate spreadsheet data into automated pipelines without requiring manual export to other formats.

The system supports both modern Excel files (`.xlsx`) and legacy Excel files (`.xls`). Operators configure the source with a file path, and the system automatically selects the appropriate reading strategy based on the file extension. This transparent format handling means operators do not need to use different source types or adjust configurations when working with different Excel versions.

When extracting from an Excel source, the system reads the spreadsheet content and returns it as a structured, columnar dataset. Operators can apply filter conditions and column mapping just as with other source types. Excel sources participate in the standard change detection lifecycle for skip-if-unchanged behavior.

## Acceptance Criteria

- [ ] Operators can configure an Excel file as a pipeline data source
- [ ] The system extracts data from `.xlsx` files and returns it as a structured columnar dataset
- [ ] The system extracts data from legacy `.xls` files and returns it as a structured columnar dataset
- [ ] The appropriate reading strategy is selected automatically based on file extension
- [ ] Operators do not need to change source configuration when switching between `.xlsx` and `.xls` files
- [ ] Operators can apply filter conditions to restrict extracted rows from Excel sources
- [ ] Operators can use column mapping to select and rename columns from Excel sources
- [ ] Excel sources support change detection for skip-if-unchanged behavior
