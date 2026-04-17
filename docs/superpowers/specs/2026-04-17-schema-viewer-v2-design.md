# Schema Viewer v2 — Visual Redesign

**Date:** 2026-04-17
**Status:** Approved
**Scope:** Replace `schema_viewer.html` with a client-facing, light-themed schema browser

## Context

The current schema viewer is a functional dark-themed developer tool. It needs to become a
client-facing deliverable that also serves as an ongoing data dictionary. Clients receive
this after `feather discover` runs against their ERP sources (SQL Server, Postgres, etc.).

**Primary audience:** Clients seeing their discovered schema for the first time.
**Secondary audience:** Ongoing reference as a living data dictionary.

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Visual tone | Clean SaaS (light theme) | Professional, approachable for non-technical clients |
| Source switching | Unified view — all sources on one page | Client sees entire data landscape without switching |
| Sidebar default | Treemap (proportional blocks) | Instant visual sense of which tables dominate |
| Sidebar alternate | Sparkline list (mini type bars) | Efficient navigation when you know what you want |
| Column layout | Grouped by type with 2-column grid | Reduces visual noise, groups related columns |
| Column summary | Stacked bar chart at top | Shows table shape at a glance before detail |
| Type filtering | Click bar segment or legend pill | Filter to just one type's columns |
| Sort controls | By Type / A-Z / Original order | Three views of the same column set |

## Architecture

### Navigation Hierarchy

```
Single page (unified)
  ├── Sidebar (toggleable: Map / List)
  │     ├── Map mode:  treemap blocks grouped by source
  │     └── List mode: sparkline list with source section headers
  └── Content area
        ├── Empty state: "Select a table"
        └── Table detail: bar chart → legend → grouped columns
```

### Page Layout

```
┌─────────────────────────────────────────────────────────┐
│  feather    Rama — Schema Discovery     4 src · 48 tbl  │
├────────────┬────────────────────────────────────────────┤
│ [Map|List] │                                            │
│            │  dbo.Sales                                 │
│ GOFRUGAL   │  Source: Gofrugal · SQL Server             │
│ ┌────┬───┐ │  74 columns                               │
│ │Sale│Pay│ │                                            │
│ │ 74 │72 │ │  Sort: [By Type] [A→Z] [Original]         │
│ ├──┬─┴───┤ │                                            │
│ │55│ 55  │ │  ┌─────────────────────────────────────┐   │
│ └──┴─────┘ │  │▓▓▓varchar▓▓▓│░decimal░│▒bigint▒│dt│   │
│            │  └─────────────────────────────────────┘   │
│ SAP        │  ● varchar (32) ● decimal (18) ...         │
│ ┌────┬───┐ │                                            │
│ │VBAK│VBA│ │  ── VARCHAR (32 columns) ─────────────     │
│ │ 42 │38 │ │  SKU          StoreNumber                  │
│ └────┴───┘ │  Store_ID     TransType                    │
│            │  ...                                       │
│ PORTAL     │                                            │
│ ...        │  ── DECIMAL (18 columns) ─────────────     │
│            │  Qty          Amount                        │
│            │  sold_mtr_qty free_qty                      │
│            │  ...                                       │
└────────────┴────────────────────────────────────────────┘
```

## Component Specifications

### 1. Header

- Logo text: "feather"
- Client/context label: parsed from schema filenames (e.g., "Rama — Schema Discovery")
- Aggregate stats pill: "{N} sources · {N} tables · {N} columns"
- Light background (#fafafa), bottom border
- Action buttons (right side): "Reload" (re-scan directory) and "Load file..." (file picker fallback)
- Buttons styled as subtle bordered pills, consistent with SaaS theme

### 2. Sidebar — Map Mode (Treemap)

- Grouped by source with colored section labels (uppercase)
- Each source gets a distinct color family:
  - Source 1: blue (#dbeafe / #bfdbfe)
  - Source 2: green (#f0fdf4 / #bbf7d0)
  - Source 3: amber (#fefce8 / #fde68a)
  - Source 4: purple (#faf5ff / #e9d5ff)
  - Additional sources cycle through these palettes
- Block size is proportional to column count within each source section
- Large tables (top 2 by column count per source) get full-width or span-2 blocks
- Smaller tables pack into 2-column grid rows
- Each block shows: table name, column count
- Click selects table and loads column detail
- Hover: subtle scale transform (1.02)

### 3. Sidebar — List Mode (Sparklines)

- Source section headers: colored uppercase labels matching treemap colors
- Each table row shows:
  - Table name (monospace-ish, 11px)
  - Column count subtitle
  - Mini stacked bar (56px wide, 5px tall) showing type distribution
- Selected row: blue background (#eff6ff), bold name
- Tables listed in original discovery order within each source

### 4. Sidebar Toggle

- Pill toggle in sidebar header: "Map" | "List"
- Active state: white background with subtle shadow
- Persists selection across table clicks (not reset on navigation)

### 5. Search / Filter

- Text input below sidebar toggle, above table list
- Filters across all sources simultaneously
- Matches against table name (case-insensitive substring)
- Works in both Map and List modes

### 6. Content Area — Empty State

- Centered vertically and horizontally
- Arrow icon, "Select a table" heading, brief instruction text
- Shown on initial load before any table is clicked

### 7. Content Area — Table Detail

#### 7a. Table Header
- Table name: 20px bold (e.g., "dbo.Sales")
- Source label: "Source: Gofrugal · SQL Server" in muted text
- Column count: "{N} columns"

#### 7b. Sort Controls
- Three pill toggles: "By Type" (default active), "A → Z", "Original"
- Active pill: blue background (#eff6ff), blue text
- "By Type": columns grouped under type headings (default view)
- "A → Z": flat alphabetical list, each cell shows column name + type badge
- "Original": columns in their source-order position (as discovered from the database)

#### 7c. Stacked Bar Chart
- Full-width horizontal bar, 32px tall, rounded corners (8px)
- Each segment represents a data type, width proportional to column count
- Type label text centered inside each segment (if segment wide enough)
- Segments are clickable — clicking filters the column list to that type only
- Color mapping (consistent across entire viewer):
  - varchar/text/nvarchar: blue (#93c5fd)
  - decimal/numeric/float: green (#86efac)
  - bigint/int/smallint: indigo (#a5b4fc)
  - date/datetime/timestamp: yellow (#fde047)
  - bit/boolean: purple (#c4b5fd)
  - Other types: gray (#d1d5db)

#### 7d. Clickable Legend
- Horizontal row of pills below the bar chart
- Each pill: color dot + type name + count in bold
- Clicking a pill filters the column list to show only that type
- Active filter: pill gets colored background + colored border
- Click again (or click "clear" / another pill) to remove filter
- When a filter is active, bar chart dims non-matching segments (opacity 0.3)

#### 7e. Grouped Column List (By Type view)
- One section per data type, ordered by count (most columns first)
- Section header: color dot + uppercase type name + "(N columns)" count
- Colored bottom-border on section header matching the type color
- Columns displayed in a 2-column grid of rounded cells (#f9fafb background)
- If a group has more than 10 columns: show first 10, then "+ N more" link that expands
- When type filter is active: only matching group is shown, fully expanded

#### 7f. Flat Column List (A→Z and Original views)
- Single table layout (not grouped)
- Columns: #, Column name, Type (with colored type badge)
- Sorted alphabetically (A→Z) or by discovery order (Original)
- Respects active type filter if one is set

## Data Flow

### Input
The viewer consumes the same `schema_*.json` files that `feather discover` already produces.
Each file is a JSON array:
```json
[
  {
    "table_name": "dbo.Sales",
    "columns": [
      {"name": "ID", "type": "bigint"},
      {"name": "SKU", "type": "varchar"}
    ]
  }
]
```

### Unified Loading
- On page load, auto-discover all `schema*.json` files in the served directory (existing behavior)
- Parse the source name from each filename: `schema_sqlserver_Rama__Gofrugal.json` → source "Gofrugal"
- Load ALL schema files and merge into a unified data structure:
  ```
  sources: [
    { name: "Gofrugal", filename: "schema_sqlserver_Rama__Gofrugal.json", tables: [...] },
    { name: "Portal",   filename: "schema_sqlserver_Rama__Portal.json",   tables: [...] },
    ...
  ]
  ```
- Assign each source a color from the palette (in discovery order)
- Compute aggregate stats across all sources

### Source Name Parsing
Extract from filename pattern `schema_{type}_{client}__{source}.json`:
- Split on `__` → last segment is source name
- If no `__`, use full filename minus `schema_` prefix and `.json` suffix
- Client name: segment between type and source (for header display)

## Constraints

- **Single HTML file** — the viewer must remain a single self-contained HTML file (no build step, no external dependencies). All CSS and JS inline.
- **No external CDN** — works offline, served from `python -m http.server`
- **Same JSON format** — no changes to `feather discover` output or the schema JSON structure
- **Backwards compatible** — existing `feather view` command continues to work unchanged
- **Same file path** — replaces `src/feather_etl/resources/schema_viewer.html` in place

## What Does NOT Change

- The `feather discover` command and its JSON output format
- The `feather view` command and `viewer_server.py` serving logic
- The `schema_viewer.html` filename and its packaging in `feather_etl.resources`
- The auto-discovery mechanism that scans for `schema*.json` files
- Drag-and-drop / file picker loading as a fallback

## Type Color Mapping

A single consistent palette used across bar charts, legend pills, sparklines, and group headers:

| Type family | Color | Hex | CSS var |
|-------------|-------|-----|---------|
| varchar, text, nvarchar, char | Blue | #93c5fd / #dbeafe | `--type-text` |
| decimal, numeric, float, real, money | Green | #86efac / #dcfce7 | `--type-numeric` |
| bigint, int, smallint, tinyint, integer | Indigo | #a5b4fc / #e0e7ff | `--type-int` |
| date, datetime, datetime2, timestamp, time | Yellow | #fde047 / #fef9c3 | `--type-datetime` |
| bit, boolean | Purple | #c4b5fd / #ede9fe | `--type-bool` |
| varbinary, binary, image, blob | Pink | #f9a8d4 / #fce7f3 | `--type-binary` |
| xml, json, sql_variant, uniqueidentifier | Gray | #d1d5db / #f3f4f6 | `--type-other` |

Type matching is case-insensitive and prefix-based (e.g., "varchar(255)" matches "varchar").
