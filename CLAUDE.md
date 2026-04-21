# feather-etl — agent context

Config-driven Python ETL for heterogeneous ERP sources → local DuckDB.

**Full project context:** `.claude/rules/feather-etl-project.md`
**Requirements:** `docs/prd.md`
**Architecture:** `README.md`
**Work conventions:** `docs/CONTRIBUTING.md`

## Before you write a single line of code

Run the test suite and confirm green:

```bash
uv run pytest -q               # currently: 720 tests
```

If anything is red before you touch anything, report immediately.

---

# Standing workflow preferences for superpowers skills

Superpowers skills honor CLAUDE.md preferences over their built-in defaults. The
rules below apply to every invocation of `/brainstorming`, `/writing-plans`,
`/subagent-driven-development`, and `/finishing-a-development-branch` when
working in this repo.

The patched versions of `brainstorming/SKILL.md` and `writing-plans/SKILL.md`
live vendored in `.claude/skills/`. See `.claude/skills/README.md` for
provenance and how to re-sync with upstream.

## After spec approval

Do NOT ask "Subagent-Driven vs Inline Execution." Always use Subagent-Driven
Development. Announce and proceed:

> "Plan complete. Proceeding with Subagent-Driven execution."

Inline execution is used only on explicit user request ("use executing-plans
instead").

## Branch setup

Before dispatching the first implementer subagent: automatically create a git
worktree on branch `feature/<slug>`, where `<slug>` = the plan filename minus
the `YYYY-MM-DD-` prefix and `.md` suffix. Do not ask; do not present options.

The worktree is created via the `superpowers:using-git-worktrees` skill (not
plain `git checkout -b`), so implementation work stays isolated from the main
workspace.

Plain in-place branching is used only on explicit user request ("stay in this
workspace" or "don't use a worktree").

## Spec review gate is preserved

The spec review gate in `brainstorming` (user approves the written spec before
implementation begins) is kept. All other questions in that flow are also kept
as defined by the skill. The autopilot starts ONLY after the spec is approved.
