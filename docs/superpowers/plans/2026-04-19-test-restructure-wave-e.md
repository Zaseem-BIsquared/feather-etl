# Test Restructure — Wave E (Delete bash + docs) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task.

**Goal:** Finish issue #40. Fill the coverage map, delete `scripts/hands_on_test.sh`, update `CLAUDE.md` and `docs/CONTRIBUTING.md` to reflect the pytest-only workflow. After this wave the branch is ready for PR.

**Architecture:** Five small tasks. E1 fills the coverage-map (audit-based); E2 deletes the bash script; E3–E4 update the two agent-context docs; E5 does a final whole-branch verification.

**Tech Stack:** Markdown edits + file deletion. No new dependencies.

**Source spec:** [`docs/superpowers/specs/2026-04-19-test-restructure-design.md`](../specs/2026-04-19-test-restructure-design.md)
**Prior waves:** [`wave-a`](2026-04-19-test-restructure-wave-a.md), [`wave-b`](2026-04-19-test-restructure-wave-b.md), [`wave-c`](2026-04-19-test-restructure-wave-c.md), [`wave-d`](2026-04-19-test-restructure-wave-d.md)
**Branch:** `feat/test-restructure` (same branch; Wave E commits extend history).
**Expected final test count:** 720.

---

## Task E1: Complete the coverage map

**File:** `docs/superpowers/specs/2026-04-19-test-restructure-coverage-map.md`

The skeleton was seeded in Wave A (Task 9) with 5 rows filled (the 5 gap ports). All other rows have empty "Pytest test path" cells. Wave E fills every remaining row by mapping each numbered bash check to an equivalent pytest test.

### Steps

1. Re-read the bash script: `cat scripts/hands_on_test.sh`. Identify every `check "..."` invocation and the stage it belongs to (S1.1 through S-INCR-8). The script has 61 checks across ~15 stages.

2. For each bash check, find the equivalent pytest test by reading test names and docstrings across `tests/e2e/`, `tests/integration/`, and `tests/unit/`. The equivalent may be:
   - A single test that asserts the same thing
   - A class (cite as `tests/e2e/test_XX.py::TestClass` if a class covers a cluster of related checks)
   - Multiple tests (cite all with `|` separators if a single bash check maps to multiple pytest tests)

3. Update the coverage map in-place:
   - Expand multi-check rows (e.g., S2.* has 8 checks — expand to S2.1 ... S2.8 with specific mappings).
   - Fill every "Pytest test path" cell.
   - Preserve the header, the blockquote, the nested bash code block, and the two footer sections.

4. **Gate check:**
   ```bash
   grep -E "^\| S[^|]+\|[^|]+\|\s*\|" docs/superpowers/specs/2026-04-19-test-restructure-coverage-map.md
   ```
   Expected: **no output** (no rows with empty pytest path). If rows are still empty, the map isn't done.

5. Commit:
   ```
   test(e): complete hands_on_test.sh -> pytest coverage map (#40)

   Every numbered bash check now maps to an equivalent pytest test.
   Gate check (grep for empty pytest path cells) returns no output,
   clearing the way for Task E2 to delete the bash script.
   ```

### Risks

- Ambiguous bash checks: some `check "..."` calls in the script may verify the same behavior as one pytest test. Cite the pytest test for each; don't invent new pytest tests to match 1:1.
- The bash script's S-INCR series tests a specific chained scenario. The pytest equivalents may live in `tests/e2e/` (if CLI) or `tests/integration/test_incremental.py` (if pipeline-level). Both are acceptable pointers.

---

## Task E2: Delete `scripts/hands_on_test.sh`

**Files:**
- Delete: `scripts/hands_on_test.sh`

### Steps

1. **Prerequisites verified:**
   - `uv run pytest -q` is green (720 tests).
   - The coverage-map gate check (from E1) returns no output.
   - `bash scripts/hands_on_test.sh` still passes 61/61 (run one last time for the audit).

2. Delete:
   ```bash
   git rm scripts/hands_on_test.sh
   ```

3. Verify:
   ```bash
   test ! -f scripts/hands_on_test.sh && echo OK
   uv run pytest -q   # still 720 green
   ```

4. Commit:
   ```
   test(e): delete scripts/hands_on_test.sh (#40)

   Retired. Every numbered check is mapped to a pytest equivalent per
   docs/superpowers/specs/2026-04-19-test-restructure-coverage-map.md.
   Pytest is now the single test suite for feather-etl.
   ```

---

## Task E3: Update `CLAUDE.md`

**Files:**
- Modify: `CLAUDE.md`

The current file (15 lines around "Before you write a single line of code") references both `pytest` and the deleted bash script.

### Steps

1. Read `CLAUDE.md`.

2. Replace the "Before you write a single line of code" block:

**Current:**
```markdown
## Before you write a single line of code

Run both suites and confirm green:

```bash
uv run pytest -q               # currently: 653 tests
bash scripts/hands_on_test.sh  # currently: 61 checks
```

If anything is red before you touch anything, report immediately.
```

**New:**
```markdown
## Before you write a single line of code

Run the test suite and confirm green:

```bash
uv run pytest -q               # currently: 720 tests
```

If anything is red before you touch anything, report immediately.
```

3. Verify: `grep -n "hands_on\|bash scripts" CLAUDE.md` — no matches.

4. Commit:
   ```
   docs(claude): drop hands_on_test.sh, update test count (#40)

   Remove the second-suite line now that scripts/hands_on_test.sh is
   gone. Update test count from 653 to 720 (final Wave D post-migration
   count).
   ```

---

## Task E4: Update `docs/CONTRIBUTING.md`

**Files:**
- Modify: `docs/CONTRIBUTING.md`

Multiple sections reference `scripts/hands_on_test.sh` or describe `tests/test_integration.py::TestKnownBugs`. All need rewriting.

### Affected sections

1. **"Rules for the fixing agent" item 4** (around line 70):
   > 4. **Update `scripts/hands_on_test.sh`** BUG-labelled checks to assert the corrected behaviour and update the label.

   Rewrite to:
   > 4. **Update BUG-labelled tests** in the relevant layer (`tests/e2e/`, `tests/integration/`, or `tests/unit/`) to assert the corrected behaviour. Per `tests/README.md`, regression guards use `BUG-N` in the test docstring — invert the assertion, rename the function if it dropped the prefix, and move it out of any `TestKnownBugs` grouping if one existed.

2. **"Rules for the fixing agent" item 5** (around line 76):
   > 5. **Run both suites before opening for re-review:**
   >    ```bash
   >    pytest tests/            # must be all green
   >    bash scripts/hands_on_test.sh   # must be all green
   >    ```

   Rewrite to:
   > 5. **Run the test suite before opening for re-review:**
   >    ```bash
   >    uv run pytest -q   # must be all green
   >    ```

3. **"Rules for the reviewing agent" item 4** (around line 103):
   > - New hands-on scenarios to add to `scripts/hands_on_test.sh`.

   Rewrite to:
   > - New regression scenarios to add under the appropriate layer in `tests/` (e2e / integration / unit per `tests/README.md`).

4. **"Rules for the reviewing agent" item 5** (around line 107):
   > - Add new scenarios to `scripts/hands_on_test.sh`.

   Rewrite to:
   > - Add new regression tests under the appropriate layer in `tests/`.

5. **Subsection `### scripts/hands_on_test.sh`** (around line 127):

   **Delete** the entire subsection (about BUG-labelled check semantics in bash) and **replace** with a reference to `tests/README.md`:

   ```markdown
   ### Tests layout

   See `tests/README.md` for the three-way decision rule (`e2e/` / `integration/` / `unit/`), the `ProjectFixture` API, and the BUG-N regression test pattern.
   ```

6. **Subsection `### tests/test_integration.py`** (around the same area):

   This section describes `TestKnownBugs` — it's still valid conceptually but `TestKnownBugs` no longer exists after Wave C (the file moved to `tests/integration/test_integration.py`). Update the file reference:

   Change `### tests/test_integration.py` → `### tests/integration/test_integration.py`.

### Steps

1. Read `docs/CONTRIBUTING.md` around the affected lines.

2. Apply all 6 edits above using the Edit tool (NOT sed).

3. Verify:
   ```bash
   grep -n "hands_on\|bash scripts" docs/CONTRIBUTING.md   # no matches
   ```

4. Commit:
   ```
   docs(contributing): retire hands_on_test.sh references (#40)

   Rewrites the six sections of docs/CONTRIBUTING.md that referenced
   scripts/hands_on_test.sh. The "BUG-labelled tests" workflow now
   points at the relevant tests/ layer (e2e/integration/unit) and
   tests/README.md is cited as the canonical contract.
   ```

---

## Task E5: Final verification + Wave E completion

No file changes — just run the Wave E completion checklist and the issue-#40 final done-signal.

### Wave E completion checklist

```bash
# 1. Full suite green at 720
uv run pytest -q

# 2. Bash script is gone
test ! -f scripts/hands_on_test.sh && echo OK

# 3. No flat test files at tests/ root
ls tests/test_*.py 2>/dev/null | wc -l   # 0

# 4. tests/commands/ gone
test ! -d tests/commands && echo OK

# 5. Three layer directories exist
test -d tests/e2e && test -d tests/integration && test -d tests/unit && echo OK
ls tests/e2e/test_*.py tests/integration/test_*.py tests/unit/test_*.py | wc -l   # many

# 6. No active docs reference the deleted script
grep -rn "hands_on_test" CLAUDE.md docs/CONTRIBUTING.md README.md \
  | grep -v "docs/superpowers/specs/" \
  | grep -v "docs/superpowers/plans/" \
  | grep -v "docs/plans/" \
  | grep -v "docs/reviews/"
# expected: no output

# 7. Coverage map is complete
grep -E "^\| S[^|]+\|[^|]+\|\s*\|" docs/superpowers/specs/2026-04-19-test-restructure-coverage-map.md
# expected: no output

# 8. Architectural purity invariant still holds
uv run pytest tests/integration/test_architecture_purity.py -q
# expected: 10 passed (1 test × 10 parametrizations)
```

All 8 should produce the expected output. If so, Wave E is complete and the branch is ready for PR.

### Steps

1. Run each command above; capture output.
2. No commit in E5 — it's verification only.
3. Report the final PR-ready state.

---

## Done signal (from the spec)

After Wave E:
- `uv run pytest -q` passes with 720 tests.
- `scripts/hands_on_test.sh` is gone.
- `tests/test_*.py` (flat) is empty; `tests/commands/` is gone.
- `tests/e2e/`, `tests/integration/`, `tests/unit/` are populated.
- `CLAUDE.md`, `docs/CONTRIBUTING.md` have no references to the deleted script.
- The coverage-map has zero empty pytest-path cells.
- `tests/integration/test_architecture_purity.py` passes (#43 invariant).

All conditions per the spec's `## Done Signal` section.

---

## Self-review

**Spec coverage:** Tasks E1-E4 address the spec's "Documentation to update" section + the `scripts/hands_on_test.sh` deletion. Task E5 runs the spec's done signal.

**Placeholder scan:** no TBDs. Every rewrite has exact before/after text.

**Scope:** 4 small tasks + 1 verification. Wave E is the smallest wave.
