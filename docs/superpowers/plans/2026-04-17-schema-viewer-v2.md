# Schema Viewer v2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the dark-themed developer schema viewer with a client-facing light SaaS design featuring unified multi-source view, treemap/sparkline sidebar, and grouped column detail with type filtering.

**Architecture:** Single self-contained HTML file (inline CSS + JS, no build step, no CDN). Loads all `schema*.json` files from the served directory, merges them into a unified multi-source view. Two sidebar modes (treemap map + sparkline list) with toggle. Content area shows stacked bar chart, clickable type legend, and grouped-by-type column grid with sort controls.

**Tech Stack:** Vanilla HTML/CSS/JS. Served by existing `python http.server` via `feather view`.

**Spec:** `docs/superpowers/specs/2026-04-17-schema-viewer-v2-design.md`

---

### Task 1: Write the CSS foundation and HTML structure

**Files:**
- Create: `scripts/schema_viewer.html` (overwrite existing)

This task writes the complete static shell — all CSS and the HTML skeleton. No JavaScript yet. The page will render a styled but empty layout.

- [ ] **Step 1: Write the CSS and HTML skeleton**

Write the full file `scripts/schema_viewer.html` with all CSS and the HTML structure. JS will be added in subsequent tasks.

```html
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>feather — schema viewer</title>
  <style>
    :root {
      --bg: #f1f5f9;
      --surface: #ffffff;
      --surface-2: #fafafa;
      --border: #e5e7eb;
      --border-light: #f3f4f6;
      --text: #111827;
      --text-muted: #6b7280;
      --text-faint: #9ca3af;
      --accent: #2563eb;
      --accent-bg: #eff6ff;
      --accent-border: #bfdbfe;
      --row-hover: #f9fafb;
      --cell-bg: #f9fafb;

      /* Type colors — bar/dot/border */
      --type-text: #93c5fd;       --type-text-fg: #1e3a8a;    --type-text-bg: #dbeafe;   --type-text-border: #bfdbfe;   --type-text-label: #2563eb;
      --type-numeric: #86efac;    --type-numeric-fg: #14532d;  --type-numeric-bg: #dcfce7; --type-numeric-border: #bbf7d0; --type-numeric-label: #16a34a;
      --type-int: #a5b4fc;        --type-int-fg: #312e81;      --type-int-bg: #e0e7ff;    --type-int-border: #c7d2fe;    --type-int-label: #6366f1;
      --type-datetime: #fde047;   --type-datetime-fg: #713f12;  --type-datetime-bg: #fef9c3; --type-datetime-border: #fde68a; --type-datetime-label: #ca8a04;
      --type-bool: #c4b5fd;       --type-bool-fg: #4c1d95;     --type-bool-bg: #ede9fe;   --type-bool-border: #ddd6fe;   --type-bool-label: #7c3aed;
      --type-binary: #f9a8d4;     --type-binary-fg: #831843;   --type-binary-bg: #fce7f3; --type-binary-border: #fbcfe8; --type-binary-label: #db2777;
      --type-other: #d1d5db;      --type-other-fg: #374151;    --type-other-bg: #f3f4f6;  --type-other-border: #e5e7eb;  --type-other-label: #6b7280;

      /* Source palette */
      --src-0: #dbeafe; --src-0-border: #bfdbfe; --src-0-label: #2563eb; --src-0-strong: #1e40af;
      --src-1: #f0fdf4; --src-1-border: #bbf7d0; --src-1-label: #16a34a; --src-1-strong: #166534;
      --src-2: #fefce8; --src-2-border: #fde68a; --src-2-label: #ca8a04; --src-2-strong: #854d0e;
      --src-3: #faf5ff; --src-3-border: #e9d5ff; --src-3-label: #7c3aed; --src-3-strong: #6b21a8;
      --src-4: #fff1f2; --src-4-border: #fecdd3; --src-4-label: #e11d48; --src-4-strong: #9f1239;
      --src-5: #f0fdfa; --src-5-border: #99f6e4; --src-5-label: #0d9488; --src-5-strong: #115e59;
    }

    * { box-sizing: border-box; margin: 0; }
    html, body { height: 100%; }
    body {
      font: 13px/1.5 -apple-system, BlinkMacSystemFont, "SF Pro Text", Helvetica, Arial, sans-serif;
      background: var(--bg); color: var(--text);
      display: grid; grid-template-rows: auto 1fr; height: 100vh;
    }

    /* ---- Header ---- */
    header {
      padding: 10px 20px; background: var(--surface-2);
      border-bottom: 1px solid var(--border);
      display: flex; gap: 12px; align-items: center;
    }
    header .logo { font-size: 16px; font-weight: 700; color: var(--text); }
    header .client { font-size: 13px; color: var(--text-muted); }
    header .spacer { flex: 1; }
    header .stat {
      font-size: 11px; color: var(--text-muted);
      background: var(--border-light); padding: 4px 12px; border-radius: 99px;
    }
    header button {
      background: var(--surface); color: var(--text); border: 1px solid var(--border);
      padding: 5px 10px; border-radius: 6px; cursor: pointer; font-size: 11px;
    }
    header button:hover { background: var(--border-light); }

    /* ---- Main layout ---- */
    main { display: grid; grid-template-columns: 280px 1fr; overflow: hidden; background: var(--surface); }

    /* ---- Sidebar ---- */
    .sidebar {
      border-right: 1px solid var(--border); background: var(--surface-2);
      display: flex; flex-direction: column; overflow: hidden;
    }
    .sidebar-head {
      padding: 10px 14px; border-bottom: 1px solid var(--border);
      display: flex; align-items: center; justify-content: space-between;
    }
    .sidebar-head .label {
      font-size: 10px; text-transform: uppercase; color: var(--text-faint);
      letter-spacing: 0.06em; font-weight: 600;
    }
    .view-toggle { display: flex; gap: 2px; background: var(--border-light); border-radius: 6px; padding: 2px; }
    .view-toggle span {
      font-size: 10px; padding: 3px 8px; border-radius: 4px; cursor: pointer; color: var(--text-muted);
    }
    .view-toggle span.active {
      background: var(--surface); color: var(--text); font-weight: 500;
      box-shadow: 0 1px 2px rgba(0,0,0,0.06);
    }

    .search-box { padding: 8px 14px; border-bottom: 1px solid var(--border); }
    .search-box input {
      width: 100%; padding: 6px 10px; border: 1px solid var(--border); border-radius: 6px;
      font-size: 11px; color: var(--text); background: var(--surface);
    }
    .search-box input:focus { outline: none; border-color: var(--accent); }

    .sidebar-body { flex: 1; overflow-y: auto; }

    /* Sparkline list items */
    .src-section {
      padding: 6px 14px 3px; font-size: 9px; text-transform: uppercase;
      letter-spacing: 0.08em; font-weight: 700; background: var(--surface-2);
    }
    .tbl-item {
      padding: 7px 14px; display: flex; align-items: center; gap: 8px;
      cursor: pointer; border-bottom: 1px solid var(--border-light); transition: background 0.1s;
    }
    .tbl-item:hover { background: var(--row-hover); }
    .tbl-item.selected { background: var(--accent-bg); }
    .tbl-item .info { flex: 1; min-width: 0; }
    .tbl-item .tname {
      font-size: 11px; color: var(--text); white-space: nowrap;
      overflow: hidden; text-overflow: ellipsis;
    }
    .tbl-item.selected .tname { color: var(--accent); font-weight: 600; }
    .tbl-item .tcols { font-size: 10px; color: var(--text-faint); }
    .spark {
      width: 56px; display: flex; height: 5px; border-radius: 3px;
      overflow: hidden; flex-shrink: 0;
    }

    /* Treemap */
    .tm-source-label {
      font-size: 9px; text-transform: uppercase; letter-spacing: 0.06em;
      font-weight: 700; padding: 10px 6px 4px;
    }
    .tm-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 5px; padding: 0 6px 6px; }
    .tm-block {
      border-radius: 8px; padding: 10px; cursor: pointer;
      transition: transform 0.1s; display: flex; flex-direction: column; justify-content: center;
    }
    .tm-block:hover { transform: scale(1.02); }
    .tm-block .tm-name { font-weight: 600; }
    .tm-block .tm-count { font-weight: 300; }
    .tm-block .tm-unit { font-size: 9px; color: var(--text-muted); }

    /* ---- Content area ---- */
    .content { flex: 1; overflow-y: auto; padding: 24px 28px; }

    .empty-state {
      display: flex; flex-direction: column; align-items: center;
      justify-content: center; height: 100%; color: var(--text-muted); text-align: center;
    }
    .empty-state h2 { color: var(--text); margin-bottom: 4px; font-size: 15px; }
    .empty-state p { font-size: 12px; max-width: 280px; }

    .tbl-title { font-size: 20px; font-weight: 700; color: var(--text); margin-bottom: 2px; }
    .tbl-source { font-size: 12px; color: var(--text-muted); margin-bottom: 2px; }
    .tbl-meta { font-size: 12px; color: var(--text-muted); margin-bottom: 14px; }

    .sort-controls { display: flex; align-items: center; gap: 6px; margin-bottom: 14px; }
    .sort-label {
      font-size: 10px; text-transform: uppercase; color: var(--text-faint);
      letter-spacing: 0.06em;
    }
    .sort-pill {
      font-size: 11px; padding: 3px 10px; border-radius: 99px; cursor: pointer;
      border: 1px solid var(--border); color: var(--text-muted); background: var(--cell-bg);
    }
    .sort-pill.active { background: var(--accent-bg); color: var(--accent); border-color: var(--accent-border); font-weight: 500; }

    .bar-chart {
      display: flex; height: 30px; border-radius: 8px; overflow: hidden;
      margin-bottom: 6px; cursor: pointer;
    }
    .bar-chart div {
      display: flex; align-items: center; justify-content: center;
      font-size: 10px; font-weight: 600; transition: opacity 0.2s;
    }

    .legend { display: flex; gap: 6px; flex-wrap: wrap; margin-bottom: 22px; }
    .legend-pill {
      font-size: 11px; display: flex; align-items: center; gap: 5px;
      padding: 2px 8px; border-radius: 99px; cursor: pointer;
      border: 1px solid var(--border); transition: all 0.15s;
    }
    .legend-pill:hover { border-color: var(--accent-border); }
    .legend-pill .dot { width: 8px; height: 8px; border-radius: 2px; display: inline-block; }

    .type-group { margin-bottom: 18px; }
    .type-group-hdr {
      display: flex; align-items: center; gap: 8px;
      margin-bottom: 8px; padding-bottom: 6px;
    }
    .type-group-hdr .dot { width: 10px; height: 10px; border-radius: 2px; }
    .type-group-hdr .tg-name {
      font-size: 11px; text-transform: uppercase; letter-spacing: 0.05em; font-weight: 600;
    }
    .type-group-hdr .tg-count { font-size: 10px; color: var(--text-muted); }

    .col-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 3px; }
    .col-cell {
      padding: 5px 10px; background: var(--cell-bg); border-radius: 5px;
      font-size: 11px; color: var(--text);
    }
    .col-more {
      font-size: 10px; color: var(--accent); padding: 4px 10px; margin-top: 2px;
      cursor: pointer;
    }
    .col-more:hover { text-decoration: underline; }

    /* Flat table (A-Z / Original views) */
    table.flat { width: 100%; border-collapse: collapse; }
    table.flat th, table.flat td {
      text-align: left; padding: 6px 10px; border-bottom: 1px solid var(--border-light);
      font-size: 11px;
    }
    table.flat th {
      color: var(--text-faint); font-weight: 500; font-size: 10px;
      text-transform: uppercase; letter-spacing: 0.04em;
    }
    .type-badge {
      font-size: 10px; padding: 1px 6px; border-radius: 4px;
      font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
    }

    /* Drag/drop zone */
    .dropzone {
      margin-top: 16px; padding: 32px 24px;
      border: 2px dashed var(--border); border-radius: 12px;
      max-width: 400px; width: 100%; text-align: center;
    }
    .dropzone.hover { border-color: var(--accent); background: rgba(37,99,235,0.04); }
    .dropzone code {
      background: var(--border-light); padding: 2px 6px; border-radius: 4px;
      font-size: 11px; color: var(--accent);
    }
    .link-btn {
      background: none; border: none; color: var(--accent); cursor: pointer;
      text-decoration: underline; padding: 0; font-size: inherit; font-family: inherit;
    }
    #file-input { display: none; }
  </style>
</head>
<body>
  <header>
    <div class="logo">feather</div>
    <div class="client" id="client-label"></div>
    <div class="spacer"></div>
    <div class="stat" id="stats">no data loaded</div>
    <button id="reload-btn" title="Re-scan directory for schema files">Reload</button>
    <button id="load-btn">Load file…</button>
    <input id="file-input" type="file" accept=".json,.ndjson,application/json" />
  </header>
  <main>
    <aside class="sidebar">
      <div class="sidebar-head">
        <span class="label">Navigation</span>
        <div class="view-toggle" id="view-toggle">
          <span class="active" data-mode="map">Map</span>
          <span data-mode="list">List</span>
        </div>
      </div>
      <div class="search-box">
        <input id="search" placeholder="Filter tables…" autocomplete="off" />
      </div>
      <div class="sidebar-body" id="sidebar-body"></div>
    </aside>
    <section class="content" id="content">
      <div class="empty-state" id="empty-state">
        <h2>No schema loaded</h2>
        <p>Discovers all <code>schema*.json</code> files when served over HTTP.</p>
        <div class="dropzone" id="dropzone">
          Drop a <code>schema*.json</code> file here, or
          <button class="link-btn" id="pick-btn">click to choose</button>.
        </div>
      </div>
    </section>
  </main>

<script>
/* JS added in subsequent tasks */
</script>
</body>
</html>
```

- [ ] **Step 2: Open in browser to verify static layout renders**

Run: `cd /path/to/feather-etl && python -m http.server 8000 -d scripts/ &`

Open `http://localhost:8000/schema_viewer.html` and verify:
- Light background, white content area
- Header with "feather" logo, Reload and Load file buttons
- Sidebar with Map/List toggle and search input
- Empty state with drop zone message

- [ ] **Step 3: Commit**

```bash
git add scripts/schema_viewer.html
git commit -m "feat(viewer): CSS foundation + HTML skeleton for v2 redesign"
```

---

### Task 2: Write the JavaScript data layer

**Files:**
- Modify: `scripts/schema_viewer.html` (replace the `<script>` block)

This task adds the core JS: state management, schema parsing, unified multi-source loading, type classification, and source name parsing from filenames.

- [ ] **Step 1: Replace the `<script>` placeholder with the data layer**

In `scripts/schema_viewer.html`, replace `/* JS added in subsequent tasks */` with:

```javascript
(() => {
  /* ---- Constants ---- */
  const TYPE_FAMILIES = [
    { key: "text",     match: ["varchar","nvarchar","text","char","nchar","ntext","sysname","xml","uniqueidentifier","sql_variant"],
      color: "var(--type-text)", fg: "var(--type-text-fg)", bg: "var(--type-text-bg)", border: "var(--type-text-border)", label: "var(--type-text-label)" },
    { key: "numeric",  match: ["decimal","numeric","float","real","money","smallmoney"],
      color: "var(--type-numeric)", fg: "var(--type-numeric-fg)", bg: "var(--type-numeric-bg)", border: "var(--type-numeric-border)", label: "var(--type-numeric-label)" },
    { key: "int",      match: ["bigint","int","smallint","tinyint","integer","mediumint","serial","bigserial"],
      color: "var(--type-int)", fg: "var(--type-int-fg)", bg: "var(--type-int-bg)", border: "var(--type-int-border)", label: "var(--type-int-label)" },
    { key: "datetime", match: ["date","datetime","datetime2","datetimeoffset","smalldatetime","timestamp","time","timestamptz","timetz"],
      color: "var(--type-datetime)", fg: "var(--type-datetime-fg)", bg: "var(--type-datetime-bg)", border: "var(--type-datetime-border)", label: "var(--type-datetime-label)" },
    { key: "bool",     match: ["bit","boolean","bool"],
      color: "var(--type-bool)", fg: "var(--type-bool-fg)", bg: "var(--type-bool-bg)", border: "var(--type-bool-border)", label: "var(--type-bool-label)" },
    { key: "binary",   match: ["varbinary","binary","image","blob","bytea"],
      color: "var(--type-binary)", fg: "var(--type-binary-fg)", bg: "var(--type-binary-bg)", border: "var(--type-binary-border)", label: "var(--type-binary-label)" },
  ];
  const OTHER_FAMILY = {
    key: "other", color: "var(--type-other)", fg: "var(--type-other-fg)",
    bg: "var(--type-other-bg)", border: "var(--type-other-border)", label: "var(--type-other-label)"
  };
  const SOURCE_TYPES = ["sqlserver","postgres","sqlite","duckdb","csv","excel","json"];

  /* ---- State ---- */
  const state = {
    sources: [],       // [{name, filename, tables: [{table_name, columns}]}]
    allTables: [],     // [{table_name, columns, sourceName, sourceIdx}]
    selected: null,    // table_name
    selectedSource: null,
    filter: "",
    sidebarMode: "map",  // "map" | "list"
    sortMode: "type",    // "type" | "az" | "original"
    typeFilter: null,    // null or type-family key
  };

  /* ---- DOM refs ---- */
  const $ = id => document.getElementById(id);
  const $sidebar = $("sidebar-body");
  const $content = $("content");
  const $stats = $("stats");
  const $search = $("search");
  const $clientLabel = $("client-label");
  const $fileInput = $("file-input");
  const $loadBtn = $("load-btn");
  const $reloadBtn = $("reload-btn");
  const $pickBtn = $("pick-btn");
  const $dropzone = $("dropzone");
  const $viewToggle = $("view-toggle");

  /* ---- Helpers ---- */
  function esc(s) {
    return String(s).replace(/[&<>"']/g, c =>
      ({ "&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;" }[c]));
  }

  function classifyType(rawType) {
    const t = rawType.toLowerCase().replace(/\(.*/, "").trim();
    for (const fam of TYPE_FAMILIES) {
      if (fam.match.some(m => t === m || t.startsWith(m))) return fam;
    }
    return OTHER_FAMILY;
  }

  function typeCounts(columns) {
    const map = {};
    for (const c of columns) {
      const fam = classifyType(c.type);
      if (!map[fam.key]) map[fam.key] = { family: fam, count: 0, columns: [] };
      map[fam.key].count++;
      map[fam.key].columns.push(c);
    }
    return Object.values(map).sort((a, b) => b.count - a.count);
  }

  function parseSourceName(filename) {
    let stem = filename.replace(/^schema_/, "").replace(/\.(json|ndjson)$/i, "");
    // Strip known source-type prefix when followed by underscore (explicit name format).
    for (const st of SOURCE_TYPES) {
      if (stem.startsWith(st + "_")) { stem = stem.slice(st.length + 1); break; }
    }
    // Split on __ to separate client from source database name.
    const parts = stem.split("__");
    if (parts.length >= 2) return { client: parts.slice(0, -1).join("__"), source: parts[parts.length - 1] };
    return { client: "", source: stem };
  }

  function parseSchema(text) {
    const trimmed = text.trim().replace(/^\uFEFF/, "");
    if (!trimmed) return [];
    if (trimmed.startsWith("[")) return JSON.parse(trimmed);
    const out = [];
    let depth = 0, start = -1, inStr = false, escFlag = false;
    for (let i = 0; i < trimmed.length; i++) {
      const ch = trimmed[i];
      if (inStr) { if (escFlag) escFlag = false; else if (ch === "\\") escFlag = true; else if (ch === '"') inStr = false; continue; }
      if (ch === '"') { inStr = true; continue; }
      if (ch === "{") { if (depth === 0) start = i; depth++; }
      else if (ch === "}") { depth--; if (depth === 0 && start !== -1) { out.push(JSON.parse(trimmed.slice(start, i + 1))); start = -1; } }
    }
    if (!out.length) throw new Error("No JSON objects found");
    return out;
  }

  /* ---- Data loading ---- */
  async function listSchemaFiles() {
    try {
      const r = await fetch("./", { cache: "no-store" });
      if (!r.ok) return [];
      const html = await r.text();
      const doc = new DOMParser().parseFromString(html, "text/html");
      const names = new Set();
      doc.querySelectorAll("a[href]").forEach(a => {
        const href = decodeURIComponent(a.getAttribute("href") || "");
        if (/^schema[^/]*\.(json|ndjson)$/i.test(href)) names.add(href);
      });
      return [...names].sort();
    } catch { return []; }
  }

  async function loadAllSources() {
    const files = await listSchemaFiles();
    if (files.length === 0) {
      // Fallback: try schema.json directly.
      try {
        const r = await fetch("schema.json", { cache: "no-store" });
        if (r.ok) {
          const tables = parseSchema(await r.text());
          setUnifiedData([{ name: "default", filename: "schema.json", tables }]);
          return true;
        }
      } catch {}
      return false;
    }
    const sources = [];
    for (const fname of files) {
      try {
        const r = await fetch(fname, { cache: "no-store" });
        if (!r.ok) continue;
        const tables = parseSchema(await r.text());
        const parsed = parseSourceName(fname);
        sources.push({ name: parsed.source, client: parsed.client, filename: fname, tables });
      } catch (e) { console.warn("Failed to load", fname, e); }
    }
    if (sources.length === 0) return false;
    setUnifiedData(sources);
    return true;
  }

  function setUnifiedData(sources) {
    state.sources = sources;
    state.allTables = [];
    for (let si = 0; si < sources.length; si++) {
      for (const t of sources[si].tables) {
        state.allTables.push({ ...t, sourceName: sources[si].name, sourceIdx: si });
      }
    }
    // Derive client label from first source that has one.
    const clientName = sources.find(s => s.client)?.client || "";
    $clientLabel.textContent = clientName ? clientName + " — Schema Discovery" : "Schema Discovery";

    const totalCols = state.allTables.reduce((s, t) => s + t.columns.length, 0);
    $stats.textContent = `${sources.length} source${sources.length !== 1 ? "s" : ""} · ${state.allTables.length} tables · ${totalCols} columns`;

    state.selected = null;
    state.selectedSource = null;
    state.typeFilter = null;
    render();
  }

  function loadFromFile(file) {
    const reader = new FileReader();
    reader.onload = () => {
      try {
        const tables = parseSchema(reader.result);
        const parsed = parseSourceName(file.name);
        setUnifiedData([{ name: parsed.source || file.name, client: parsed.client, filename: file.name, tables }]);
      } catch (e) { alert("Failed to parse: " + e.message); }
    };
    reader.readAsText(file);
  }

  /* ---- Render placeholder (expanded in next tasks) ---- */
  function render() {
    renderSidebar();
    renderContent();
  }
  function renderSidebar() {
    $sidebar.innerHTML = '<div style="padding:16px;color:var(--text-faint);font-size:11px">Sidebar rendering — Task 3</div>';
  }
  function renderContent() {
    if (!state.selected) {
      const es = $("empty-state");
      if (es) es.style.display = "";
      return;
    }
  }

  /* ---- Events ---- */
  $search.addEventListener("input", e => { state.filter = e.target.value; render(); });
  $loadBtn.addEventListener("click", () => $fileInput.click());
  if ($pickBtn) $pickBtn.addEventListener("click", () => $fileInput.click());
  $fileInput.addEventListener("change", e => { const f = e.target.files[0]; if (f) loadFromFile(f); });
  $reloadBtn.addEventListener("click", () => loadAllSources().then(ok => {
    if (!ok) alert("No schema*.json files found — use Load file… instead.");
  }));
  if ($dropzone) {
    ["dragenter","dragover"].forEach(ev => $dropzone.addEventListener(ev, e => { e.preventDefault(); $dropzone.classList.add("hover"); }));
    ["dragleave","drop"].forEach(ev => $dropzone.addEventListener(ev, e => { e.preventDefault(); $dropzone.classList.remove("hover"); }));
    $dropzone.addEventListener("drop", e => { const f = e.dataTransfer.files[0]; if (f) loadFromFile(f); });
  }

  /* ---- Boot ---- */
  loadAllSources();
})();
```

- [ ] **Step 2: Verify data loading works**

Open `http://localhost:8000/schema_viewer.html` and verify:
- The header shows client name and aggregate stats (e.g., "4 sources · 48 tables · 1,065 columns")
- The sidebar shows the placeholder text "Sidebar rendering — Task 3"
- Console has no errors (check DevTools)

- [ ] **Step 3: Commit**

```bash
git add scripts/schema_viewer.html
git commit -m "feat(viewer): JS data layer — unified multi-source loading + type classification"
```

---

### Task 3: Write sidebar rendering (List + Treemap + Toggle)

**Files:**
- Modify: `scripts/schema_viewer.html` (replace `renderSidebar` function and add toggle wiring)

This task replaces the placeholder `renderSidebar()` with two modes: sparkline list and treemap. Adds the view toggle behavior and search filtering.

- [ ] **Step 1: Replace the renderSidebar function**

In `scripts/schema_viewer.html`, replace the entire `renderSidebar()` function with:

```javascript
  function renderSidebar() {
    if (state.sidebarMode === "map") renderTreemap();
    else renderSparkList();
  }

  function renderSparkList() {
    const f = state.filter.toLowerCase();
    let html = "";
    for (let si = 0; si < state.sources.length; si++) {
      const src = state.sources[si];
      const tables = src.tables.filter(t => t.table_name.toLowerCase().includes(f));
      if (tables.length === 0) continue;
      if (state.sources.length > 1) {
        html += `<div class="src-section" style="color:var(--src-${si % 6}-label)">${esc(src.name.toUpperCase())}</div>`;
      }
      for (const t of tables) {
        const sel = (t.table_name === state.selected && src.name === state.selectedSource) ? " selected" : "";
        const tc = typeCounts(t.columns);
        const total = t.columns.length || 1;
        const sparkBars = tc.map(g => `<div style="flex:${g.count};background:${g.family.color}"></div>`).join("");
        html += `<div class="tbl-item${sel}" data-table="${esc(t.table_name)}" data-source="${esc(src.name)}">
          <div class="info"><div class="tname">${esc(t.table_name)}</div><div class="tcols">${t.columns.length} cols</div></div>
          <div class="spark">${sparkBars}</div>
        </div>`;
      }
    }
    if (!html) html = '<div style="padding:16px;color:var(--text-faint);font-size:11px">No matches</div>';
    $sidebar.innerHTML = html;
    $sidebar.querySelectorAll(".tbl-item").forEach(el => {
      el.addEventListener("click", () => selectTable(el.dataset.table, el.dataset.source));
    });
  }

  function renderTreemap() {
    const f = state.filter.toLowerCase();
    let html = "";
    for (let si = 0; si < state.sources.length; si++) {
      const src = state.sources[si];
      const tables = src.tables
        .filter(t => t.table_name.toLowerCase().includes(f))
        .slice()
        .sort((a, b) => b.columns.length - a.columns.length);
      if (tables.length === 0) continue;
      if (state.sources.length > 1) {
        html += `<div class="tm-source-label" style="color:var(--src-${si % 6}-label)">${esc(src.name.toUpperCase())}</div>`;
      }
      html += '<div class="tm-grid">';
      const maxCols = tables[0]?.columns.length || 1;
      for (let ti = 0; ti < tables.length; ti++) {
        const t = tables[ti];
        const isLarge = ti < 2 && t.columns.length > maxCols * 0.5;
        const span = isLarge ? ' style="grid-column:span 2"' : "";
        const bgVar = `var(--src-${si % 6})`;
        const borderVar = `var(--src-${si % 6}-border)`;
        const nameColor = `var(--src-${si % 6}-strong)`;
        const countColor = `var(--src-${si % 6}-label)`;
        const fontSize = isLarge ? 13 : (t.columns.length > 20 ? 11 : 10);
        const countSize = isLarge ? 18 : (t.columns.length > 20 ? 14 : 12);
        const sel = (t.table_name === state.selected && src.name === state.selectedSource) ? ";outline:2px solid var(--accent);outline-offset:-2px" : "";
        html += `<div class="tm-block" data-table="${esc(t.table_name)}" data-source="${esc(src.name)}"
          ${span} style="background:${bgVar};border:1px solid ${borderVar}${sel}">
          <div class="tm-name" style="font-size:${fontSize}px;color:${nameColor}">${esc(t.table_name.replace(/^dbo\./, ""))}</div>
          <div class="tm-count" style="font-size:${countSize}px;color:${countColor}">${t.columns.length}</div>
          ${isLarge ? '<div class="tm-unit">columns</div>' : ""}
        </div>`;
      }
      html += "</div>";
    }
    if (!html) html = '<div style="padding:16px;color:var(--text-faint);font-size:11px">No matches</div>';
    $sidebar.innerHTML = html;
    $sidebar.querySelectorAll(".tm-block").forEach(el => {
      el.addEventListener("click", () => selectTable(el.dataset.table, el.dataset.source));
    });
  }

  function selectTable(tableName, sourceName) {
    state.selected = tableName;
    state.selectedSource = sourceName;
    state.typeFilter = null;
    render();
  }
```

- [ ] **Step 2: Add the view toggle event listener**

Add this code right after the existing `$reloadBtn` event listener (before the `$dropzone` block):

```javascript
  $viewToggle.querySelectorAll("span").forEach(btn => {
    btn.addEventListener("click", () => {
      state.sidebarMode = btn.dataset.mode;
      $viewToggle.querySelectorAll("span").forEach(s => s.classList.toggle("active", s === btn));
      renderSidebar();
    });
  });
```

- [ ] **Step 3: Verify sidebar rendering**

Open `http://localhost:8000/schema_viewer.html` and verify:
- **Map mode** (default): treemap blocks grouped by source, sized proportionally, largest tables prominent
- **List mode**: sparkline rows with source section headers and mini type bars
- **Toggle**: clicking Map/List switches between views
- **Search**: typing in the filter box filters tables in both modes
- **Click**: clicking a table highlights it (outline in map, blue bg in list)

- [ ] **Step 4: Commit**

```bash
git add scripts/schema_viewer.html
git commit -m "feat(viewer): sidebar rendering — treemap + sparkline list + toggle + search"
```

---

### Task 4: Write content area rendering (bar chart, legend, grouped list, sort)

**Files:**
- Modify: `scripts/schema_viewer.html` (replace `renderContent` function)

This task replaces the placeholder `renderContent()` with the full table detail view: stacked bar chart, clickable legend, sort controls, grouped-by-type column list, and flat A-Z/Original views.

- [ ] **Step 1: Replace the renderContent function**

In `scripts/schema_viewer.html`, replace the entire `renderContent()` function with:

```javascript
  function renderContent() {
    const emptyEl = $("empty-state");
    if (!state.selected) {
      $content.innerHTML = "";
      $content.appendChild(emptyEl || createEmptyState());
      return;
    }
    if (emptyEl) emptyEl.style.display = "none";

    const table = state.allTables.find(t => t.table_name === state.selected && t.sourceName === state.selectedSource);
    if (!table) { $content.innerHTML = '<div class="empty-state"><h2>Table not found</h2></div>'; return; }

    const tc = typeCounts(table.columns);
    const totalCols = table.columns.length || 1;
    const srcEntry = state.sources.find(s => s.name === state.selectedSource);
    const srcType = srcEntry ? inferSourceType(srcEntry.filename) : "";

    let html = "";

    // Table header
    html += `<div class="tbl-title">${esc(table.table_name)}</div>`;
    if (state.sources.length > 1) {
      html += `<div class="tbl-source">Source: ${esc(state.selectedSource)}${srcType ? " · " + esc(srcType) : ""}</div>`;
    }
    html += `<div class="tbl-meta">${table.columns.length} columns</div>`;

    // Sort controls
    html += `<div class="sort-controls">
      <span class="sort-label">Sort:</span>
      <span class="sort-pill${state.sortMode==="type"?" active":""}" data-sort="type">By Type</span>
      <span class="sort-pill${state.sortMode==="az"?" active":""}" data-sort="az">A → Z</span>
      <span class="sort-pill${state.sortMode==="original"?" active":""}" data-sort="original">Original</span>
    </div>`;

    // Stacked bar chart
    html += '<div class="bar-chart">';
    for (const g of tc) {
      const pct = g.count / totalCols * 100;
      const dimmed = state.typeFilter && state.typeFilter !== g.family.key ? ";opacity:0.25" : "";
      const label = pct > 8 ? g.family.key.replace("text","varchar").replace("numeric","decimal").replace("int","bigint").replace("datetime","date").replace("bool","bit") : "";
      html += `<div data-type="${g.family.key}" style="flex:${g.count};background:${g.family.color};color:${g.family.fg}${dimmed}">${label}</div>`;
    }
    html += "</div>";

    // Legend pills
    html += '<div class="legend">';
    for (const g of tc) {
      const active = state.typeFilter === g.family.key;
      const style = active ? `background:${g.family.bg};border-color:${g.family.border}` : "";
      html += `<span class="legend-pill" data-type="${g.family.key}" style="${style}">
        <span class="dot" style="background:${g.family.color}"></span>
        ${g.family.key} <b style="color:${g.family.label}">(${g.count})</b>
      </span>`;
    }
    if (state.typeFilter) {
      html += '<span class="legend-pill" data-type="" style="color:var(--accent);border-color:var(--accent-border)">✕ clear</span>';
    }
    html += "</div>";

    // Column list
    if (state.sortMode === "type") {
      html += renderGroupedColumns(tc);
    } else {
      html += renderFlatColumns(table, state.sortMode);
    }

    $content.innerHTML = html;

    // Wire sort controls
    $content.querySelectorAll(".sort-pill").forEach(el => {
      el.addEventListener("click", () => { state.sortMode = el.dataset.sort; renderContent(); });
    });
    // Wire bar chart segments
    $content.querySelectorAll(".bar-chart div").forEach(el => {
      el.addEventListener("click", () => toggleTypeFilter(el.dataset.type));
    });
    // Wire legend pills
    $content.querySelectorAll(".legend-pill").forEach(el => {
      el.addEventListener("click", () => toggleTypeFilter(el.dataset.type));
    });
    // Wire "show more" links
    $content.querySelectorAll(".col-more").forEach(el => {
      el.addEventListener("click", () => {
        const hidden = el.previousElementSibling;
        if (hidden) { hidden.style.display = ""; el.remove(); }
      });
    });
  }

  function toggleTypeFilter(typeKey) {
    state.typeFilter = (typeKey && state.typeFilter !== typeKey) ? typeKey : null;
    renderContent();
  }

  function renderGroupedColumns(tc) {
    let html = "";
    const groups = state.typeFilter ? tc.filter(g => g.family.key === state.typeFilter) : tc;
    for (const g of groups) {
      html += '<div class="type-group">';
      html += `<div class="type-group-hdr" style="border-bottom:2px solid ${g.family.bg}">
        <span class="dot" style="background:${g.family.color}"></span>
        <span class="tg-name" style="color:${g.family.label}">${g.family.key}</span>
        <span class="tg-count">(${g.count} columns)</span>
      </div>`;

      const VISIBLE = state.typeFilter ? g.columns.length : 10;
      const visible = g.columns.slice(0, VISIBLE);
      const rest = g.columns.length - VISIBLE;

      html += '<div class="col-grid">';
      for (const c of visible) html += `<div class="col-cell">${esc(c.name)}</div>`;
      html += "</div>";

      if (rest > 0) {
        html += `<div class="col-grid" style="display:none">`;
        for (const c of g.columns.slice(VISIBLE)) html += `<div class="col-cell">${esc(c.name)}</div>`;
        html += "</div>";
        html += `<div class="col-more">+ ${rest} more</div>`;
      }
      html += "</div>";
    }
    return html;
  }

  function renderFlatColumns(table, mode) {
    let cols = [...table.columns];
    if (state.typeFilter) cols = cols.filter(c => classifyType(c.type).key === state.typeFilter);
    if (mode === "az") cols.sort((a, b) => a.name.localeCompare(b.name));

    let html = '<table class="flat"><thead><tr><th style="width:36px">#</th><th>Column</th><th>Type</th></tr></thead><tbody>';
    cols.forEach((c, i) => {
      const fam = classifyType(c.type);
      html += `<tr>
        <td style="color:var(--text-faint)">${i + 1}</td>
        <td>${esc(c.name)}</td>
        <td><span class="type-badge" style="background:${fam.bg};color:${fam.label}">${esc(c.type)}</span></td>
      </tr>`;
    });
    html += "</tbody></table>";
    return html;
  }

  function inferSourceType(filename) {
    for (const st of SOURCE_TYPES) {
      if (filename.includes(st)) return st === "sqlserver" ? "SQL Server" : st.charAt(0).toUpperCase() + st.slice(1);
    }
    return "";
  }

  function createEmptyState() {
    const div = document.createElement("div");
    div.className = "empty-state";
    div.id = "empty-state";
    div.innerHTML = `<h2>Select a table</h2><p>Click any table in the sidebar to view its columns, types, and structure.</p>`;
    return div;
  }
```

- [ ] **Step 2: Verify the full content area**

Open the viewer in a browser with schema files present and verify:
- Click a table in the sidebar → content shows table name, source, column count
- Stacked bar chart shows type proportions with labels
- Legend pills show type names with counts
- Click a bar segment or legend pill → filters to that type only, "✕ clear" pill appears
- Sort pills: "By Type" shows grouped sections, "A → Z" shows alphabetical flat table, "Original" shows source-order flat table
- Grouped view: sections with colored headers, 2-column grid, "+ N more" links that expand on click
- Flat view: numbered table with colored type badges

- [ ] **Step 3: Commit**

```bash
git add scripts/schema_viewer.html
git commit -m "feat(viewer): content area — bar chart, legend, grouped columns, sort, type filter"
```

---

### Task 5: Sync to resources, run tests, final verification

**Files:**
- Modify: `src/feather_etl/resources/schema_viewer.html` (overwrite with new version)

- [ ] **Step 1: Copy to the packaged resources location**

```bash
cp scripts/schema_viewer.html src/feather_etl/resources/schema_viewer.html
```

- [ ] **Step 2: Run the existing test suite**

Run: `uv run pytest -q`

Expected: All 597 tests pass. The `TestSyncViewerHtml` tests compare `scripts/schema_viewer.html` against the packaged resource — since we copied the file, they should match.

- [ ] **Step 3: Run hands_on_test.sh**

Run: `bash scripts/hands_on_test.sh`

Expected: All 61 checks pass. The viewer HTML change does not affect CLI behavior.

- [ ] **Step 4: Visual verification with real schema files**

Run `feather view` from a directory containing schema files (e.g., from a previous `feather discover` run) and verify:

1. **Landing**: header shows client name + aggregate stats, sidebar shows treemap
2. **Treemap**: blocks are sized proportionally, grouped by source with colored labels
3. **List mode**: toggle to List, verify sparkline bars and source section headers
4. **Search**: type a table name fragment, verify both modes filter
5. **Table detail**: click a table, verify bar chart + legend + grouped columns
6. **Type filter**: click a bar segment, verify columns filter to that type
7. **Sort**: toggle A → Z, Original, By Type — verify each renders correctly
8. **Expand**: in grouped view, click "+ N more" to expand hidden columns
9. **Multi-source**: verify all sources appear in sidebar and content shows source label
10. **Drag/drop**: drag a schema JSON onto the drop zone, verify it loads
11. **Load file**: click "Load file…" button, pick a schema JSON

- [ ] **Step 5: Commit the synced copy**

```bash
git add src/feather_etl/resources/schema_viewer.html
git commit -m "chore(viewer): sync packaged schema_viewer.html with scripts/ copy"
```

---

### Task 6: Format and final commit

**Files:**
- All modified files

- [ ] **Step 1: Run ruff format**

```bash
ruff format .
```

- [ ] **Step 2: Run full test suite one more time**

```bash
uv run pytest -q
```

Expected: All tests pass.

- [ ] **Step 3: Final commit if ruff made changes**

```bash
git add -A
git commit -m "style: apply ruff formatting"
```
