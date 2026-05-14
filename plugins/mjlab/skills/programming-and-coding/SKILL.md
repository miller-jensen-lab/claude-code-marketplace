---
name: programming-and-coding
description: General coding philosophy for Miller-Jensen lab work — KISS, small functions, smoke tests on real data, working code is the documentation. TRIGGER when writing, reviewing, refactoring, or debugging code in any language in a lab repo.
related:
  - coding-in-python
  - code-review
  - code-overview
updated: 2026-05-14
---
# Programming and coding

Cross-language baseline. Loaded alongside `coding-in-python` / `coding-in-r` / etc. as the *why*; those skills cover the *what*.

The audience is bench scientists writing analysis code, not software engineers shipping a product. The bar is "correct enough to publish from," not "production-ready service."

## Core principles

- **KISS** — abhor complexity. If a function is hard to understand, that's a signal to simplify, not to add comments.
- **Incremental changes** — small, testable edits. Run the analysis after every change and check the answer hasn't moved.
- **Smoke tests on real data beat unit tests.** Manually run the script on a small slice of actual lab data after a change. Catches the bugs that matter; unit tests rarely do, for analysis code.
- **Working code is the documentation.** Express intent through good names and focused functions. Don't litter the code with comments explaining what it does.

## Code structure

- Small, focused functions (~20 lines). One thing per function.
- Descriptive variable names — `umap_coords` not `df2`, `dropout_rate` not `dr`, `gated_cells` not `data`.
- Use the language's type system where it costs little (Python type hints on function signatures, R argument types via assertions).
- **Boring, proven solutions** — stdlib first, established libraries second. No esoteric framework for a one-off analysis.
- Keep files small. Aim for <500 lines per file. Big files signal you should split by concern.
- **Set seeds** on any stochastic operation. `np.random.default_rng(42)`, `set.seed(42)`. Pass the rng through; don't rely on globals.

## How you work on a task

1. Read the request and any context (`CLAUDE.md`, `README`, lab notebook entries).
2. Skim the existing code in the area you'll touch. Match its style unless it violates best practices here.
3. Make the smallest change that could work.
4. Run the analysis on a real-data slice — does the output make sense?
5. Clean up dead code and stale comments before moving on.

## Testing in moderation

- For analysis code, **smoke tests on real data > unit tests**. One trustworthy end-to-end check per analysis script.
- Write a unit test only when you have a function whose correctness you can't sanity-check by eyeballing the output (e.g., a normalization formula, a stats helper).
- Skip tests entirely for one-off scripts.

## Error handling

- Handle errors only where you can recover meaningfully. Otherwise let them bubble — a traceback in an analysis script is signal, not noise.
- Catch the specific exception class. Never bare `except:` or `tryCatch(error = function(e) NULL)`.
- Log enough context that someone reading the traceback later can reconstruct what happened.

## Code-review mindset

- Clarity over cleverness.
- Explicit over implicit.
- Flat over nested.
- Readability over performance — unless performance is *proven* critical.
- See [code-review](../code-review/SKILL.md) for the full review playbook.

## Persona

Direct, honest, and practical. Point out unnecessary complexity and suggest simpler alternatives. Embody the wisdom of someone who has stared at the wrong figure at 11pm the night before a deadline and now writes code that future-them can rerun in five minutes.

## Further reading

- [The Pragmatic Programmer](https://pragprog.com/titles/tpp20/the-pragmatic-programmer-20th-anniversary-edition/) — the cross-language baseline
- [How to write reusable & reproducible Bioconductor code](https://bioconductor.org/checkResults/) — biology-specific
- [Ten Simple Rules for Reproducible Computational Research (Sandve et al. 2013)](https://journals.plos.org/ploscompbiol/article?id=10.1371/journal.pcbi.1003285) — the seminal short paper
