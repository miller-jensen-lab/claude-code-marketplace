---
name: coding-in-r
description: R implementation rules for Miller-Jensen lab analysis code — renv, tidyverse, here::here() for portable paths, Bioconductor staples for immunology/single-cell/flow work. TRIGGER when editing .R, .Rmd, .qmd files; writing analysis scripts; structuring an R project; or working with Seurat/DESeq2/edgeR/flowCore in a lab repository.
related:
  - programming-and-coding
  - notebooks
  - tabular-data
  - plotting
  - starting-a-new-project
  - reproducible-envs
updated: 2026-05-14
---
# Coding in R

Rule: lock the environment with `renv`, write portable paths with `here::here()`, and treat the script as the source of truth — never the global workspace.

For general coding philosophy, also load [programming-and-coding](../programming-and-coding/SKILL.md).

## Tooling defaults

- **`renv`** for project-isolated package versions. `renv::init()` once, `renv::snapshot()` before committing. Commits `renv.lock`.
- **`pak`** for fast installs (`pak::pkg_install("DESeq2")`). Much faster than `install.packages` for Bioconductor.
- **`rig`** for R version management — like `pyenv` but for R. <https://github.com/r-lib/rig>.
- **`styler`** for auto-format (`styler::style_dir(".")`). Run before committing.
- **`lintr`** for lint — configure with a `.lintr` file in the repo.
- **`here::here()`** for paths. Never `setwd()` in a tracked script.
- **`readr`** > base `read.csv()` for everything (better defaults, faster, returns a tibble).

Optional (add when the analysis grows beyond a few scripts):

- **`testthat`** for tests. For analysis code, **smoke tests on real data** (rerun on a small slice and eyeball the output) beat unit tests almost always. Skip tests for one-off scripts.
- **`optparse`** when a script needs CLI args — but most lab scripts are notebooks or `source()`d one-shots that don't need it.

## Project setup with renv

```R
# from the project root, once
renv::init()                   # creates renv/, renv.lock, .Rprofile
renv::install("BiocManager")
renv::install("bioc::DESeq2")
renv::install("Seurat")
renv::install(c("tidyverse", "here", "fs", "styler", "lintr"))
renv::snapshot()               # update renv.lock
```

Commit `renv.lock` and `.Rprofile`. Anyone re-clones the project and runs `renv::restore()` to recreate the exact env. See [reproducible-envs](../reproducible-envs/SKILL.md).

## Project layout

Flat is fine for analyses:

```
2026-il4-macrophages/
├── renv.lock
├── .Rprofile
├── README.md
├── notebooks/           # .Rmd / .qmd, one per question
├── scripts/             # batch entry points
├── R/                   # shared helpers; source() from notebooks/scripts
├── data/raw/            # never edit; gitignored
├── data/derived/        # intermediate; gitignored
└── results/             # figures, tables; gitignored except final exports
```

Reach for an R *package* layout (`DESCRIPTION`, `R/`, `man/`, `tests/`) only if shared helpers will be used by more than one project. For most lab work, a flat repo with a `R/utils.R` is enough.

## Portable paths — don't hardcode

A `setwd("/Users/jdoe/Documents/...")` at the top of a script will fail on every other machine. Don't ever commit one. Instead:

```R
library(here)
# always anchors to the project root, regardless of where the script is run from
counts_path <- here("data", "raw", "counts.csv")
counts <- readr::read_csv(counts_path)
```

`here::here()` finds the project root by walking up from the working directory looking for `.here`, `.Rproj`, `DESCRIPTION`, or `.git`. Add an empty `.here` file at the project root if none of those exist.

For shared lab data on a fileserver, read the mount point from an env var loaded in `.Renviron` (gitignored), not from a hardcoded `/Volumes/MJ-lab/...`.

## R style (tidyverse style guide)

- `snake_case` for variables and functions.
- `<-` for assignment, not `=` (which is for arguments only).
- Native pipe `|>` preferred over `%>%` (no magrittr dependency).
- 2-space indent; spaces around operators; ~80-char lines, 120 max.
- Named arguments for clarity: `mean(x, na.rm = TRUE)` not `mean(x, T)`.
- Implicit return — only use `return()` for early exits.
- **Never** `attach()` or `<<-`. Manage scope explicitly.
- `library()` at top of scripts, not scattered `require()` calls.
- Set seeds before any stochastic step: `set.seed(42)`. Document the seed in a comment when the analysis depends on it.

## Notebooks vs. scripts

- `.Rmd` / `.qmd` for exploratory work and figure generation.
- `.R` scripts for batch operations producing a single artifact (a `.parquet`, a list of DE genes, a fitted model).
- A code chunk longer than ~30 lines is a function in disguise — move it into `R/utils.R` and `source()` it.
- Never `source()` a notebook. Notebooks consume helpers; they don't export them.

See [notebooks](../notebooks/SKILL.md) for full discipline.

## Data manipulation

Default to **tidyverse** (`dplyr`, `tidyr`, `purrr`) for clarity. Reach for **`data.table`** when:

- Datasets are >1 GB and dplyr is provably slow (benchmark first).
- You need in-place modification (`set()`, `:=`).
- The function you need is a one-liner in `data.table` but a 5-line `dplyr` chain.

**`dtplyr`** bridges both: dplyr syntax, data.table speed.

For SQL-on-files / multi-format / DuckDB / Polars patterns, see [tabular-data](../tabular-data/SKILL.md).

## Essential packages

**Core**: `tidyverse`, `data.table`, `dtplyr`, `here`, `fs`, `readr`, `arrow`, `jsonlite`.

**Visualization**: `ggplot2`, `patchwork` (combine plots), `scales`, `ggpubr` (publication-quality), `ggrepel` (non-overlapping labels), `RColorBrewer`/`viridis` (colorblind-safe palettes).

**Bioinformatics — Miller-Jensen lab core**:

- **Differential expression**: `DESeq2`, `edgeR`, `limma` (still the gold-standard trio)
- **Single-cell**: `Seurat` (v5+), `SingleCellExperiment`, `scran`, `scater`, `scDblFinder` (doublet detection), `harmony` (integration), `Nebulosa` (gene smoothing on UMAP)
- **Cell-cell communication**: `CellChat`, `liana`, `nichenetr`
- **Flow cytometry**: `flowCore`, `flowWorkspace` (read FlowJo .wsp), `ggcyto`, `CytoExploreR`
- **Genomic ranges**: `GenomicRanges`, `rtracklayer`, `plyranges`
- **Pathway / GSEA**: `clusterProfiler`, `fgsea`, `msigdbr`
- **Stats**: `lme4` (mixed models), `emmeans` (estimated marginal means), `broom` (tidy model output)

Install Bioconductor packages with `pak::pkg_install("bioc::DESeq2")` or `BiocManager::install("DESeq2")`. `renv::snapshot()` captures them in `renv.lock`.

## Error handling

- For expected failures (a missing file the user might not have, a flaky API), use `tryCatch()` and fall back gracefully.
- For everything else, let R's default error bubble up. A traceback at the analysis layer is signal, not noise.
- Set `options(warn = 1)` at the top of a long script so warnings print immediately rather than queue.

## Checklist before committing

- [ ] `styler::style_dir(".")` clean
- [ ] `lintr::lint_dir(".")` clean (or any flags justified)
- [ ] No `setwd()` or absolute paths to your laptop
- [ ] `set.seed()` set before any stochastic operation
- [ ] `renv::snapshot()` run and `renv.lock` committed
- [ ] No raw data, large outputs, `.RData`, or `.Rhistory` staged

## Further reading

- [Tidyverse style guide](https://style.tidyverse.org/)
- [R for Data Science (2e)](https://r4ds.hadley.nz/) — the canonical tidyverse text
- [renv documentation](https://rstudio.github.io/renv/)
- [pak](https://pak.r-lib.org/) — fast installs
- [Bioconductor](https://bioconductor.org/) — package landing page
- [`here` documentation](https://here.r-lib.org/) — portable paths
- [Seurat tutorials](https://satijalab.org/seurat/articles/get_started.html)
- [DESeq2 vignette](https://bioconductor.org/packages/release/bioc/vignettes/DESeq2/inst/doc/DESeq2.html)
