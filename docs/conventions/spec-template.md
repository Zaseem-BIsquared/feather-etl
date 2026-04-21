# <Feature Name>

Created: YYYY-MM-DD
Status: DRAFT | APPROVED | DONE
Issue: [#NN](url)

---

<!--
    Mirrored into this repo from Siraj's cross-project vault on 2026-04-21.
    This in-repo copy is the source of truth for feather-etl. Re-sync the
    vault copy separately if the template evolves here.

    This template embodies seven cross-project principles:
    - form-follows-grain          — match presentation form to the information's natural grain
    - roles-to-documents-mapping  — four SDLC roles (BA/Architect/Implementer/Tester) map to two docs (spec/plan); each section carries one voice
    - scope-describes-outcomes    — spec Scope names what the developer gets, not what files we edit
    - spec-sections-natural-shape — Problem/Goal = prose; Scope/Decisions = bullets; How-it-works = paragraphs or diagram
    - spec-sections-pull-unique-weight — each section contributes something no other section covers
    - terrain-not-procedure       — spec is declarative (terrain); plan is imperative (procedure)
    - senior-lead-voice           — spec speaks to a capable colleague, not an implementer needing a checklist

    Usage: fill in each section following its inline guidance. Delete sections that do
    not earn their place. For small specs (<4 sections), the Part headings may be dropped.
-->

# Part I — Requirements

<!--
    BA voice throughout Part I. Prose and bullets. No file paths, no function names,
    no implementation mechanism. Describes *what the system must do* and *why*.
-->

## 1. Problem

<!--
    Prose with a narrative arc: what's wrong → why it's wrong → what it costs us.
    Earn your length. Do not compress to bullets; the reader needs the "why this matters" hook.
    This is often the most reviewable section of the spec. Make it land.
-->

## 2. Goal

<!--
    One paragraph of prose. The single-sentence version of success, elaborated.
    What does the world look like after this ships? Concrete enough to be testable.
-->

## 3. Acceptance criteria

<!--
    Bullets. Testable, observable conditions that define "done."
    Given/when/then phrasing is natural here. One fact per bullet.
    Write as a Tester/BA hybrid voice: describe what is observable, not how to test.

    Optional sub-section: a concrete verification exemplar (bash sequence, pytest
    invocation, curl command) that the reader can run to confirm the criteria hold.
    Frame as "a concrete exemplar of the acceptance criteria, run by hand" — not as
    a step-by-step procedure.
-->

### End-to-end verification (optional)

<!-- Bash or shell block illustrating the AC concretely. Omit if AC is self-evident. -->

---

# Part II — Design

<!--
    Architect voice throughout Part II. Describes *how* the solution is structured.
    Still avoid imperative mood (delete, add, replace) — those belong in the plan.
    Speak in terms of what exists and what emerges, not what to do next.
-->

## 4. Scope

<!--
    Short prose lead-in establishing the outer bounds (e.g., "lives entirely in tests/").

    **In** bullets — *outcomes*, not mechanisms. "Missing X is created automatically,"
    not "tests/db_bootstrap.py creates X." Implementation mechanism belongs in §7 below.

    **Out** bullets — substantive boundaries a reviewer might otherwise assume are in scope.
    Drop any bullet that excludes something no reader would have assumed.

    **Outside this scope** (optional) — files or areas explicitly untouched, when that's
    a meaningful safety signal (e.g., "src/** is not touched — not a product change").
-->

**In**

- …

**Out**

- …

**Outside this scope**

- …

## 5. Key decisions

<!--
    Only the internal forks a reviewer would not have noticed from Scope alone.
    Skip decisions whose answer is obvious from Scope; skip defensive-coding "decisions"
    (e.g., "wrap in try/except") that no reasonable reviewer would litigate.

    Preferred shape: counterfactual headings. Each decision gets its own H3:

    ### <Topic>
    **Chose:** <the decision, one sentence>.
    **Why not <the most plausible alternative>?** <rationale, 1-2 sentences>.

    This structure embeds the "why not the other way?" test into the section's shape —
    if you can't articulate a plausible alternative, the decision isn't really a fork.

    For 5+ decisions with one-line rationale each, a comparison table may work better.
    But for 1-4 decisions with multi-sentence rationale, use the counterfactual shape.
-->

## 6. How it works

<!--
    Short paragraphs per subsystem, OR a text/ASCII diagram when the flow is parallel
    or branching. The diagram is often worth the maintenance cost when multiple paths
    or a success/failure fork are present — it communicates structure at a glance.

    Include non-obvious implementation quirks that future maintainers will need to know
    (e.g., "autocommit required because CREATE DATABASE cannot run inside a transaction").

    Do NOT duplicate content from Scope. This section's unique contribution is the
    sequence / interaction, not a re-listing of outcomes.
-->

## 7. Integration surface

<!--
    Describes the terrain — where the outcomes from §4 live in the codebase.
    Per-file edit procedure lives in the plan, not here.

    NO line numbers (they rot). NO imperatives (delete, add, replace). Use declarative
    "currently holds X; becomes home of Y" framing. The reader should be able to build
    a mental map from this section without being told what to do.

    **New**      — files created; one-line role per file.
    **Modified** — files changed; one-line terrain description (what's there now, what emerges).
    **Outside this scope** — files explicitly untouched (control signal, not enforcement).
-->

**New**

- `path/to/new_file.ext` — role description.

**Modified**

- `path/to/existing.ext` — currently holds …; becomes home of …

**Outside this scope**

- `path/to/preserved/**` — why it's not touched.

## 8. Test design

<!--
    Tester voice, at the design layer. What automated checks exist, at which layers,
    verifying which behaviors. Not the test code itself — that lives in the plan or
    in the test files.

    Organize by test layer: unit / integration / end-to-end / manual acceptance.
    For each layer, bullet the specific behaviors verified. If gated by markers, note it.

    This section is often a border-dweller between Design and Requirements — acceptance-
    oriented tests may drift into §3 AC, implementation-level tests stay here.
-->

Unit tests (mocked dependencies):

- …

Integration tests (real dependencies, gated by `@marker`):

- …
