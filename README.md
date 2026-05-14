# Miller-Jensen Lab — Claude Code Marketplace

A [Claude Code](https://docs.claude.com/en/docs/claude-code) plugin marketplace of skills for the [Miller-Jensen lab](https://www.miller-jensen.org/) at Yale. Once installed, Claude Code loads the right skill on demand when you ask it to do something lab-shaped — write an analysis script, fit a bursting model, gate a flow file, refactor a notebook, etc.

Two pillars:

1. **Be reproducible.** Lockfiles, seeds, raw-data-never-edited, plain-text everything.
2. **Be skillful.** Get the analysis done correctly and figure-worthy on the first try.

## Install

You need [Claude Code](https://docs.claude.com/en/docs/claude-code) installed. You can install either the Desktop or the command line version. Inside Claude Code:

```
/plugin marketplace add miller-jensen-lab/claude-code-marketplace
/plugin install mjlab@miller-jensen-lab
```

Aside: Anthropic ships a [life-sciences marketplace](https://github.com/anthropics/life-sciences) with MCP connectors (PubMed, bioRxiv, Consensus, BioRender, etc.) and a few skills (`single-cell-rna-qc`, `scvi-tools`, `nextflow-development`). Browse it if you want — most of it is pharma/clinical/drug-discovery and not central to a basic-research lab, and the relevant pieces (lit search, scRNA-seq QC) we cover ourselves with calibration tuned for the lab.

Update later with `/plugin marketplace update miller-jensen-lab` (and similarly for `life-sciences`).

## Skills shipped today

| Skill | Purpose |
|---|---|
| `coding-in-python` | uv, ruff, pathlib, notebook-vs-script discipline, portable paths. |
| `coding-in-r` | renv, tidyverse, `here::here()` for portable paths, Bioconductor staples (DESeq2/Seurat/flowCore). |
| `tabular-data` | DuckDB SQL on CSV/XLSX/Parquet as the default; qsv, xlsx2csv, Polars for the cases where DuckDB isn't ideal. |
| `programming-and-coding` | Cross-language coding philosophy: KISS, smoke tests on real data, working code is the documentation. |
| `code-overview` | Five-minute walk to orient inside an unfamiliar lab repo before editing. |
| `code-review` | Self-review and AI review tuned for lab landmines (hardcoded paths, raw data staged, missing seeds). |
| `using-git-and-github` | Agent judgment for branches, commits, repo naming, big-file pushback, and the lab org. |
| `zotero` | Use the Zotero local API to search, cite, and export bibliographies; manuscript citekey workflow. |
| `literature-search` | Live-oracle search across PubMed/OpenAlex/Crossref/Europe PMC/bioRxiv/Semantic Scholar/arXiv/Unpaywall + Ai2 Asta. |
| `local-lit-search` | Build a reproducible local SQLite FTS5 corpus from PubMed/PMC; answer questions with grounded `[PMID:…]` citations. Ships uv-PEP-723 scripts with download safeguards. |
| `cell-cell-communication` | Ligand-receptor inference pointer skill — LIANA consensus, CellChat v2, NicheNet. |
| `single-cell-secretion` | Microfluidic multiplex cytokine analysis; polyfunctionality / PSI; thin-ecosystem honesty. |
| `flow-cytometry` | flowCore/openCyto/ggcyto cytoverse (R primary), FlowKit (Python); reproducible gating, transforms, compensation. |
| `live-cell-imaging` | Reporter time-lapse (NF-κB / IRF / STAT) — bioio, cellpose, btrack, TrackMate, napari. |
| `smfish` | Per-cell transcript counts — big-fish, FISH-quant v2, RS-FISH; feeds bursting models. |
| `stochastic-gene-expression` | Telegraph / Beta-Poisson / NB fits, GillesPy2 SSA, FSP for the CME, txburst. |
| `bio-data-hygiene` | Sample sheets as source of truth, naming convention, donor anonymization, GEO/SRA prep. |
| `bio-stats` | Pseudobulk for scRNA-seq DE, mixed models for matched donors, FDR, effect sizes. |
| `plotting` | Publication-quality plotting (Python + R, in depth) — Okabe-Ito / viridis defaults, journal-spec dimensions, SuperPlot recipe, common-mistake catalog. |
| `scrna-qc` | Per-sample QC for droplet scRNA-seq — MAD filtering, scDblFinder doublets, SoupX/CellBender ambient RNA, macrophage-specific common mistakes. |

## Skills planned

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
