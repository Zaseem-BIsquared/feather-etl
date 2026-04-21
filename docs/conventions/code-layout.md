# Code Layout Convention

This project organizes code files using a hybrid template that combines three practices:

1. **DHH TOC** — visual section banners + docstring CONTENTS block (David Heinemeier Hansson / Basecamp / Rails)
2. **Stepdown Rule** — most-summative / highest-abstraction first within each section (Robert C. Martin / *Clean Code*)
3. **Agent-first** — greppable section labels + explicit SEE ALSO + input/output contracts (emerging LLM-era convention)

Files organized this way are easier for new team members to skim, for maintainers to navigate, and for AI agents (Claude Code, Copilot, agent-driven refactors) to consume.

**Audience:** this doc exists for both **team members** and **AI agents** working in the codebase. Both should read it before making non-trivial layout changes.

## The template

```python
"""<one-line tagline>

<one paragraph: what this module does, where it sits in the architecture>

CONTENTS
  == Public Interface ==
    • <symbol> — <one-line hint>

  == Data Types ==
    • <symbol> — <one-line hint>

  == Private Helpers ==
    • <symbol> — <one-line hint>

CALL ORDER (when the module's public functions run in a specific sequence)
  1. <step>
  2. <step>

SEE ALSO
  <related module> — <why it matters>
"""

from __future__ import annotations

<imports>


# == Public Interface ==

# ── Sub-banner when a section has distinct sub-groups ──


def main_entry(...) -> Result:
    ...


def secondary(...) -> Other:
    ...


# == Data Types ==


@dataclass
class Result:
    ...


# == Private Helpers ==


def _helper(...):
    ...
```

## Section order rationale

- **Public Interface first** — Stepdown puts policy above detail. Functions are policy; they're what the file exists for.
- **Data Types second** — They describe the shape of what flows through the public interface. They're vocabulary, not the main thing.
- **Private Helpers last** — Implementation details that most readers don't need to see first.

This is safe because `from __future__ import annotations` at the top of the file makes all type annotations lazy strings. Forward references to types defined later in the file resolve naturally.

## Banner conventions

| Banner | Style | Use for |
|---|---|---|
| Top-level | `# == Section ==` | The three main sections: Public Interface, Data Types, Private Helpers |
| Sub-level | `# ── Sub-group description ──` | When a section has two or more distinct sub-groups (e.g. "main loop" vs. "prelude functions") |

Leave a blank line above and below every banner. Banners are greppable — use them as search anchors.

## Docstring conventions

Keep each block short. The docstring is the table of contents; it is not the full story.

- **One-line tagline** — what the module is, in a sentence.
- **Paragraph** — what the module does + where it sits in the architecture.
- **CONTENTS** — every public + private symbol with a one-line hint. Mirrors the file's section structure.
- **CALL ORDER** — when the module's functions run in a specific sequence, list them. See "Pipeline in Prose" below.
- **SEE ALSO** — related modules + why they matter.

## Pipeline in Prose — when temporal order disagrees with importance

Sometimes the order in which a module's functions run (pipeline order) differs from the order in which a reader cares about them (importance order). Example: three public functions called as `detect → apply → run_discover`, but `run_discover` is the main thing the file exists for.

**Don't force a single ordering.** Encode both:

- **Code order** follows importance, stepdown, or 80-20 reading frequency. The main function goes at the top of its section.
- **Prose order** (in the docstring `CALL ORDER` block) preserves the temporal/pipeline order.
- **Sub-banner inline** explains any position inversion so a reader scrolling past doesn't need to consult the docstring to understand the layout.

Concrete example from `src/feather_etl/discover.py`:

```python
# == Public Interface ==

# ── Main discovery loop ──

def run_discover(...):       # most important → code order puts it first
    ...

# ── Rename resolution (runs before run_discover in the CLI flow) ──

def detect_renames_for_sources(...):   # sub-banner explains position
    ...

def apply_rename_decision(...):
    ...
```

And in the module docstring:

```
CALL ORDER (Typer wrapper invokes these in sequence)
  1. detect_renames_for_sources → RenameDetection
  2. (wrapper prompts the user to accept/reject proposals)
  3. apply_rename_decision      (applies the resolved decision)
  4. run_discover                → DiscoverReport
```

Scanners see `run_discover` first. Deep-divers see the pipeline in prose. Both win.

The full principle is documented in the Obsidian vault as **Pipeline in Prose** (`cross-project/principle-pipeline-in-prose.md`).

## Docstring sizing: "Just Enough"

Size docstrings to the minimum that lets a reader use the function without reading the body. For complex public functions, that's usually:

- **Lead sentence** — what the function does, active voice.
- **One paragraph** — the key invariant or non-obvious behavior.
- **Short bullet list** for modes/flags when they aren't self-documenting from the signature.
- **One sentence** demoting caller responsibilities, if any.

Skip "Returns" sections that restate the type annotation. Skip "Raises" unless the behavior is surprising. Skip "Examples" if tests exist.

Strip test: for any sentence, ask "if I deleted this, would a reader still know how to act?" If yes, delete it.

See the **Just Enough** principle (`cross-project/principle-just-enough.md` in the Obsidian vault) for the fuller articulation.

## When NOT to apply this template

- **Files under ~50 lines.** Ceremony outweighs benefit. A short utility with one public function doesn't need banners.
- **Single-purpose files.** One class, one function — the file name is the TOC.
- **Already well-organized short files.** Don't add banners just to match the convention; they should aid navigation.
- **Test files.** Tests have their own organization (class per feature, function per case) that doesn't need this template.

## Reference implementation

[`src/feather_etl/discover.py`](../../src/feather_etl/discover.py) is the canonical example. Open it to see the template applied to a real ~300-line orchestration module.

## Related principles

These notes live in the project maintainer's personal knowledge vault and are optional deeper reading. **Everything load-bearing for applying this template is already in this doc; vault access is not required.**

- **Pipeline in Prose** — when pipeline order and importance order disagree (covered in full with worked example above).
- **Chesterton's Commit** — before reformatting, read the commit that created the file; what looks like an inconsistency today may be pre-convention code that was correct at the time.
- **Just Enough** — calibrate docstrings and comments to the minimum that serves the reader (covered in "Docstring sizing" above).
- **Design for Agents and Humans** — design artifacts must work for both TTY and non-TTY, both humans and agents.

## Maintenance

When you reformat or reorganize a file in this repo:

1. **Check the git history first.** Don't reformat unfamiliar code before understanding the commit that introduced it. What looks like an inconsistency today may be pre-convention code that was correct at the time. `git log --follow <file>` + `git blame` are the tools.
2. Verify `from __future__ import annotations` is present before moving types below functions.
3. Keep docstring CONTENTS in sync with the actual file structure.
4. Keep `CALL ORDER` in sync with the actual pipeline — stale prose is worse than none.
5. Run `uv run pytest -q` before and after — layout changes should be behavior-preserving.
