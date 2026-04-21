# Vendoring notes — brainstorming skill

**Upstream:** `claude-plugins-official/superpowers` v5.0.7,
`skills/brainstorming/SKILL.md`
**Vendored:** 2026-04-21

## Patches applied to upstream

### Patch 2 — Atomic tasks rule

Added one bullet to the "Design for isolation and clarity" section, as the
last bullet:

> **Tasks must be atomic** — each task does exactly one thing. Never combine
> unrelated concerns into a single task, even if they seem small. If two
> things can be described, tested, or fail independently, they are separate
> tasks.

**Why:** Combined tasks hide risk, make progress unclear, and conflate
unrelated failure modes.

### Patch 3 — Spec template reference

Added one sub-bullet under the "Documentation" bullet in the "After the
Design" section, right under "Write the validated design (spec) to …":

> - Use the spec template at `docs/conventions/spec-template.md` as the
>   structural skeleton. It encodes cross-project spec-writing principles
>   around Parts, voice, section shape, and role mapping.

**Why:** The template embodies the cross-project spec-writing principles
(form-follows-grain, roles-to-documents-mapping, scope-describes-outcomes,
spec-sections-natural-shape, spec-sections-pull-unique-weight,
terrain-not-procedure, senior-lead-voice). Referencing it from the skill
ensures every brainstorming session produces specs that follow the
conventions, rather than drifting back to ad-hoc shapes.

### Patch 1 — reverted before vendoring (kept here for history)

An earlier patch tried to insert the six-section Plan Preflight template
into brainstorming's "Presenting the design" section. It was reverted on
2026-04-21: the Preflight reviews the **plan** doc (output of
`writing-plans`), not the **design spec** (output of brainstorming). Placing
it in brainstorming conflated two distinct artifacts. The Preflight now
lives in the writing-plans skill as Patch 2 — see
`.claude/skills/writing-plans/NOTES.md`.

## Re-syncing with upstream

When `superpowers` bumps past v5.0.7 and you want to pull improvements:

1. Read the new upstream `SKILL.md` from
   `~/.claude/plugins/cache/claude-plugins-official/superpowers/<version>/skills/brainstorming/SKILL.md`.
2. Diff against the v5.0.7 baseline to see upstream's changes.
3. Re-apply Patch 2 and Patch 3 from this file onto the new upstream text.
4. Update the "Upstream" line above to the new version.
