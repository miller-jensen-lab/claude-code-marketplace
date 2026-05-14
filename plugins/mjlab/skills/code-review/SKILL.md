---
name: code-review
description: Self-review and AI code review for Miller-Jensen lab repos — find real bugs and lab-specific landmines (hardcoded paths, raw data staged, missing seeds), not style nits. TRIGGER when reviewing code, diffs, PRs, or implementations in any lab repo, or when about to commit a change.
related:
  - programming-and-coding
  - using-git-and-github
  - coding-in-python
  - coding-in-r
updated: 2026-05-14
---
# Code review

Find bugs that would break the analysis or block the manuscript. Not improvements. Not style.

## A finding must be

1. **Introduced in this change** — not pre-existing.
2. **Provably impactful** — name the scenario or input that triggers it. Speculation is not a finding.
3. **Actionable** — there is a discrete fix.

## Severity

- **P0** — Blocks the merge / commit. Wrong answer, lost data, secret leaked, code that can't run on another machine.
- **P1** — Should fix before merge. Realistic inputs trigger it.
- **P2** — Worth fixing eventually. Unlikely in practice.
- **P3** — Nit. **Do not report.**

Don't inflate. A P2 labelled P0 erodes trust and gets ignored next time.

## Verdict

Every review ends with exactly one:

- **LGTM** — no P0/P1. Ship it. Keep it short; don't pad with praise.
- **FAIL** — P0/P1 found. Must fix before merging.

## Lab-specific landmines (always check these)

These are P0/P1 patterns specific to analysis code that a generic code review misses:

- **Hardcoded user paths.** `/Users/jdoe/Desktop/...`, `~/Dropbox/...`, `C:\Users\...`, an absolute path to a cluster scratch dir. Will fail on any other machine. **P0**.
- **Raw data, large outputs, or `.env` staged for commit.** Anything matching `*.h5ad`, `*.fcs`, `*.fastq*`, `*.bam`, `*.tif*`, `*.czi`, `*.nd2`, or `data/raw/`. **P0** — git is the wrong place; see [using-git-and-github](../using-git-and-github/SKILL.md).
- **No seed on a stochastic operation.** `np.random.default_rng()` without `42`, `set.seed()` missing entirely, UMAP/leiden without `random_state=`, scvi without `seed_everything`. Means the analysis won't reproduce. **P1**.
- **In-place mutation of raw data.** Anything that writes back to `data/raw/`, or overwrites the input DataFrame without a fresh assignment. **P0**.
- **Silent ignore of unexpected data.** `dropna()` without checking *how much* was dropped, `try: ... except: pass`, filtering with a magic-number threshold not documented anywhere. **P1**.
- **Hard-coded biology numbers** (gene lists, marker thresholds, gate cutoffs) buried inline. Should live in a `config.yml` or top of the script with a comment. **P2 → P1** if more than one place.
- **Missing units / scale in figure axes**. Common in flow + imaging. **P1** if the figure is destined for a paper.
- **Notebook outputs committed.** `.ipynb` cells with outputs blow up diffs and leak data. **P1**.
- **Lockfile out of sync with manifest.** `pyproject.toml` says `polars` but `uv.lock` doesn't have it; `renv.lock` missing a package the script `library()`s. Means a fresh clone can't run. **P0**.

## Process

1. Read the lab repo's `CLAUDE.md` / `README.md` if present.
2. Read each changed file end-to-end (`Read` tool, not "skim from context").
3. Run the script / notebook end-to-end on a real data slice if you can — does the output look right?
4. Run linter / type-checker if the repo has one configured.
5. Check `git status` — is anything staged that shouldn't be (data, secrets, outputs)?

## Output

```
## Findings

### [P0] Hardcoded path to /Users/jdoe/Desktop will break on any other machine
**File**: scripts/run_de.py:14
**Issue**: `data_path = "/Users/jdoe/Desktop/counts.csv"` — anyone else cloning this repo gets `FileNotFoundError`.
**Fix**: read the path from argparse or a project-relative `data/raw/counts.csv`.

### [P1] UMAP without random_state will not reproduce
**File**: notebooks/cluster.ipynb (cell 12)
**Issue**: `sc.tl.umap(adata)` — every run produces different embeddings.
**Fix**: `sc.tl.umap(adata, random_state=42)`.

## Verdict
FAIL
```

## On praise

A short "LGTM, nice clean diff" is fine. A paragraph of praise per file is noise.

## Further reading

- [Google's code review developer guide](https://google.github.io/eng-practices/review/reviewer/) — general principles
