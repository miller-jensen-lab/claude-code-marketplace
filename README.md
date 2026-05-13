# Miller-Jensen Lab — Claude Code Marketplace

A [Claude Code](https://docs.claude.com/en/docs/claude-code) plugin marketplace of skills for the [Miller-Jensen lab](https://www.miller-jensen.org/) at Yale. Once installed, Claude Code loads the right skill on demand when you ask it to do something lab-shaped — write an analysis script, fit a bursting model, gate a flow file, refactor a notebook, etc.

Two pillars:

1. **Be reproducible.** Lockfiles, seeds, raw-data-never-edited, plain-text everything.
2. **Be skillful.** Get the analysis done correctly and figure-worthy on the first try.

## Companion marketplace

For generic bioinformatics skills (single-cell QC, scVI, 10x Genomics, Nextflow, PubMed/bioRxiv search), install Anthropic's life-sciences marketplace alongside this one. We deliberately don't duplicate those skills.

```
/plugin marketplace add anthropics/life-sciences
```

This marketplace focuses on what's specific to the lab's work — single-cell secretion, stochastic gene-expression models, live-cell reporter imaging, cell-cell communication inference, flow cytometry, smFISH — plus general Python/R hygiene tuned for analysis (not web apps or CLI tools).

## Install

You need [Claude Code](https://docs.claude.com/en/docs/claude-code) installed. Inside Claude Code:

```
/plugin marketplace add miller-jensen-lab/claude-code-marketplace
/plugin install mjlab@miller-jensen-lab
```

Update later with `/plugin marketplace update miller-jensen-lab`.

Per-project install, GUI install paths (VS Code, Cursor, JetBrains), and verification — see the [Yale SOM HPC marketplace README](https://github.com/yale-som-hpc/claude-code-marketplace#install) for the full menu; the steps are identical.

## What's in the `mjlab` plugin

**General programming** — Python, R, and analysis hygiene tuned for lab work.

| Skill | Purpose |
|---|---|
| `overview` | Mental model, two-pillar manifesto, pointers into other skills. |
| `programming-and-coding` | Cross-language coding philosophy (KISS, small functions, smoke tests). |
| `coding-in-python` | uv, ruff, pytest, pathlib, notebook-vs-module discipline. |
| `coding-in-r` | renv, tidyverse, lintr/styler, testthat, Bioconductor staples. |
| `tabular-data` | Polars/DuckDB/Parquet defaults; when to leave pandas. |
| `parallel-python` | Process vs. thread vs. async; when adding parallelism actually pays. |
| `notebooks` | When to use a notebook, when to refactor, headless execution. |
| `plotting` | Publication-quality ggplot2 / matplotlib defaults; colorblind-safe palettes. |
| `starting-a-new-project` | Reproducible project layout (`data/`, `src/`, `notebooks/`, `results/`). |
| `reproducible-envs` | renv, uv, Apptainer/Docker — pinning, lockfiles, restore. |
| `code-review` | Self-review checklist before opening a PR. |
| `code-overview` | How to read into an unfamiliar lab repo quickly. |
| `web-scrape` | curl with curl_chrome, playwright-cli for JS-heavy sites, GEO/SRA APIs. |

**Lab-specific analyses** — gap-filling skills, mostly first-of-kind as Claude Code skills.

| Skill | Purpose |
|---|---|
| `cell-cell-communication` | CellChat / NicheNet / CellPhoneDB; ligand-receptor scoring. |
| `single-cell-secretion` | Microfluidic multiplex cytokine analysis; polyfunctionality scoring. |
| `flow-cytometry` | FCS handling, compensation, biexponential transforms, reproducible gating. |
| `live-cell-imaging` | Reporter time-lapse, single-cell tracking, fold-change detection. |
| `smfish` | Spot detection, per-cell transcript counts, fitting to bursting models. |
| `stochastic-gene-expression` | Telegraph model, Gillespie/CME simulation, MLE on mRNA distributions. |
| `bio-data-hygiene` | Sample sheets as source of truth, GEO/SRA submission prep, naming. |
| `bio-stats` | Multiple testing, batch effects, mixed models for repeated-measures data. |

**Domain primers** — onboarding maps for an agent that needs to come up to speed.

| Skill | Purpose |
|---|---|
| `macrophage-immunology` | M1/M2 axes, TLR/TNF/IFN signaling, TAMs, network-motif framing. |
| `hiv-latency` | Reservoir biology, reactivation strategies, reporter systems. |
| `transcriptional-bursting` | Telegraph model intuition, burst size vs. frequency, key papers. |
| `systems-immunology` | Heterogeneity, single-cell methods, cell-cell communication. |

## Repository layout

```
.claude-plugin/
└── marketplace.json            # marketplace manifest
plugins/mjlab/
├── .claude-plugin/
│   └── plugin.json             # plugin manifest (bump version on release)
└── skills/<name>/SKILL.md      # one directory per skill
```

A skill is a single `SKILL.md` with YAML frontmatter and a directive playbook body. Claude Code's skill loader reads the frontmatter to decide when to load each skill into context.

## Contributing

Most skills are short — a fix or new section is usually a one-PR change. If you're not ready to write a fix, file an issue.

### Skill acceptance criteria

Every skill should:

- Have YAML frontmatter: `name`, `description`, `related`, `updated`.
- Have a `description` with a `TRIGGER when …` clause naming concrete signals (file extension, library name, analysis modality). This stops the skill from firing on unrelated work.
- Be directive and agent-usable: rules, not essay prose.
- Include copy-paste code examples with language-tagged fences.
- Cross-link related skills with relative paths.
- Set seeds in any stochastic example (`np.random.default_rng(42)`, `set.seed(42)`).
- Never commit raw data, large outputs, or notebook checkpoints. Mention `.gitignore` patterns where relevant.
- End with a short checklist and a `## Further reading` section.

## License

Released into the public domain under [The Unlicense](LICENSE).
