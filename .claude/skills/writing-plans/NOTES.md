# Vendoring notes — writing-plans skill

**Upstream:** `claude-plugins-official/superpowers` v5.0.7,
`skills/writing-plans/SKILL.md`
**Vendored:** 2026-04-21

## Patches applied to upstream

### Patch 2 — Plan Preflight as final review gate

Inserted a new section titled **"Plan Preflight — final review gate"**
between the existing "Self-Review" and "Execution Handoff" sections.

The Preflight is the gate between plan-writing and plan-execution. It gives
the user a condensed altitude view of the plan for a go/no-go approval
before any subagent is dispatched. Six sections:

1. Scope & Boundaries
2. User-Facing Contract
3. Integration Surface
4. Task Breakdown
5. Dependency Chain
6. Done Signal

Wait for user approval; revise plan and re-present if requested; proceed
to Execution Handoff only once the Preflight is approved.

**Why:** The Preflight is a condensed altitude view for the decision-maker.
It belongs at the boundary between plan-writing and plan-execution. Without
it, the Execution Handoff autopilot (Patch 1 below) would dispatch against
an unreviewed plan.

### Patch 1 — Execution Handoff autopilot to Subagent-Driven

Replaced the original "Execution Handoff" section (which asked the user to
choose between Subagent-Driven and Inline execution) with an autopilot that
defaults to Subagent-Driven Development.

Original upstream offered a 2-way choice:

> "Which approach?"
> 1. Subagent-Driven (recommended)
> 2. Inline Execution

Vendored version announces and proceeds:

> "Plan complete and saved to `docs/superpowers/plans/<filename>.md`.
> Proceeding with Subagent-Driven execution."

Inline execution remains available on explicit user request ("use
executing-plans instead" / "do it inline"), but is never offered as a
default choice.

**Why:** Project standing preference (see the repo's `CLAUDE.md`). The
choice prompt was pure friction — the team always picks Subagent-Driven.

### Patch ordering

The two patches interact:

1. Plan is written (main body of skill)
2. Self-Review (existing section)
3. **Plan Preflight** (Patch 2 — new gate for user approval)
4. **Execution Handoff** (Patch 1 — autopilot to subagent-driven-development)

Patch 1 (autopilot) fires AFTER Patch 2 (gate). The Preflight ensures the
user has approved the plan before the autopilot kicks in.

## Re-syncing with upstream

When `superpowers` bumps past v5.0.7 and you want to pull improvements:

1. Read the new upstream `SKILL.md` from
   `~/.claude/plugins/cache/claude-plugins-official/superpowers/<version>/skills/writing-plans/SKILL.md`.
2. Diff against the v5.0.7 baseline to see upstream's changes.
3. Re-apply Patch 2 (insert Plan Preflight between Self-Review and
   Execution Handoff) and Patch 1 (replace Execution Handoff with
   autopilot) onto the new upstream text.
4. Update the "Upstream" line above to the new version.
