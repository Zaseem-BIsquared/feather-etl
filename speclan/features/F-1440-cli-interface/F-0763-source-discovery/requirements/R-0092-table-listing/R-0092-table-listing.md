---
id: R-0092
type: requirement
title: Table Listing
status: review
owner: speclan
created: "2026-04-10T05:50:46.664Z"
updated: "2026-04-10T05:50:46.664Z"
---
# Table Listing

Operators can retrieve a complete list of all tables available in their configured source system by running the `feather discover` command. This gives operators visibility into every dataset that can be included in their pipeline, serving as the starting point for selecting which tables to extract.

The discover command presents tables using their fully qualified names as they exist in the source system. For database sources, table names include their schema prefix (e.g., `dbo.SALESINVOICE`, `public.customers`). For file-based sources, table names are derived from the file or directory naming conventions used in the source location. The listing covers all tables the configured credentials have access to, ensuring operators see the full scope of available data.

The output is organized so operators can quickly scan and identify tables of interest. When no tables are found in the source, the system communicates this clearly rather than producing empty or ambiguous output.

## Acceptance Criteria

- [ ] Running `feather discover` lists all accessible tables in the configured source
- [ ] Database source tables display with their schema-qualified names
- [ ] File-based source tables display names derived from the source file structure
- [ ] The command produces clear output when no tables are found in the source
- [ ] The table listing reflects the current state of the source system at the time of discovery
- [ ] Only tables accessible with the configured credentials are listed
