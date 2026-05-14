---
name: code-overview
description: Quickly orient inside an unfamiliar Miller-Jensen lab repo before editing — find the entry points, the data flow, and the load-bearing files without slurping the whole codebase into context. TRIGGER when you've just `cd`d into a lab repo for the first time, are asked "what is this codebase?" or "where does X happen?", or need to plan a change in a repo you haven't seen.
related:
  - programming-and-coding
  - using-git-and-github
  - starting-a-new-project
updated: 2026-05-14
---
# Code overview

Lab repos are not large software projects. They're typically a few thousand lines split across notebooks, scripts, and a `lib.py` or `R/` directory. You can map the whole thing in five focused minutes — don't burn context reading every file.

## What you're trying to learn

In order of priority:

1. **What does the project do?** One sentence.
2. **What's the data flow?** Raw input → derived/intermediate → results/figures.
3. **What are the entry points?** Which script/notebook produces the headline figure or table.
4. **Where's the load-bearing logic?** The 1–2 files that, if broken, break everything.
5. **What conventions does this repo follow?** Lockfile format (`uv.lock` / `renv.lock`), test framework if any, gitignore patterns.

Skip everything else until you need it.

## The five-minute walk

```bash
# 1. The pitch — what is this?
cat README.md 2>/dev/null | head -50
test -f CLAUDE.md && head -80 CLAUDE.md
test -f AGENTS.md && head -80 AGENTS.md

# 2. The shape — directories at the top, file types overall
ls -la
find . -maxdepth 2 -type d -not -path '*/\.*' -not -path '*/__pycache__*' -not -path '*/node_modules*'
find . -maxdepth 3 -type f \( -name '*.py' -o -name '*.R' -o -name '*.ipynb' -o -name '*.qmd' -o -name '*.Rmd' \) | wc -l

# 3. The contract — what's tracked vs. ignored
cat .gitignore 2>/dev/null
cat pyproject.toml 2>/dev/null | head -40   # uv project / Python pkg
cat DESCRIPTION 2>/dev/null                  # R package
cat renv.lock 2>/dev/null | head -20         # R env

# 4. The entry points
test -d scripts && ls scripts
test -d notebooks && ls notebooks
grep -RIl --include='*.py' "if __name__" . 2>/dev/null | head -5
test -f justfile && cat justfile
test -f Makefile && head -40 Makefile

# 5. The library code — only after the above
test -f lib.py && wc -l lib.py
test -d src && find src -name '*.py' -exec wc -l {} +
test -d R && ls R
```

Read the actual files only after the walk tells you which ones matter.

## Typical lab-repo shape

```
project/
├── README.md          # read first
├── CLAUDE.md          # read second if present — agent instructions
├── pyproject.toml     # or DESCRIPTION/renv.lock for R
├── data/raw/          # never touched by code in repo; gitignored
├── data/derived/      # outputs of scripts; gitignored
├── scripts/           # batch entry points; one file per stage
├── notebooks/         # exploratory + figure generation
├── lib.py (or R/)     # shared helpers imported by both
└── results/           # final figures + tables
```

If you don't see `data/` and `results/`, check `.gitignore` — they're often present but ignored. Look for them on disk if the analysis context implies they should exist.

## Notebooks: read headers, skip cells

A 30-cell notebook is usually:
- Cell 1: imports
- Cells 2–4: load + filter data
- Cells 5–N: the actual question
- Last cell: save figure

Reading the headers + first/last cell is usually enough to know what the notebook does. Use `jupyter nbconvert --to script notebook.ipynb --stdout | head -100` if you need to scan the code without launching Jupyter.

## When to dig deeper

Stop reading when you have:
- A one-sentence project summary
- The data-flow shape
- The 1–3 files you need to edit

If a question can't be answered from the overview, *then* read full files. Don't preemptively load everything.

## Reporting back

When asked "what is this repo?", reply in this shape:

```
**Project:** [one sentence]
**Data flow:** raw → [step] → [step] → results
**Entry points:** scripts/X.py, notebooks/Y.ipynb
**Load-bearing:** lib.py (helpers used everywhere), config.yml
**Stack:** uv + Polars + scanpy (or whatever)
**Conventions:** locked env via uv.lock; results/ gitignored except results/final/
```

Then ask what they want to do, rather than dumping more detail unprompted.

## Further reading

- [`tree`](https://oldmanprogrammer.net/source.php?dir=projects/tree) — `brew install tree`; `tree -L 2 -I 'data|__pycache__|.venv'` is sometimes nicer than `find`
- [`tokei`](https://github.com/XAMPPRocky/tokei) — fast line-count by language if you want a one-shot size estimate
