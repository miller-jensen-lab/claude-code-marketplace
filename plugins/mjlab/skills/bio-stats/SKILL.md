---
name: bio-stats
description: Statistics that come up in Miller-Jensen lab work — multiple testing, mixed models for matched donors, pseudobulk for scRNA-seq DE, batch effects, effect sizes. TRIGGER when running a hypothesis test, scRNA-seq DE, repeated-measures design, paired donor comparison, multiple-testing correction, or batch correction.
related:
  - coding-in-r
  - coding-in-python
  - bio-data-hygiene
  - tabular-data
updated: 2026-05-14
---
# Bio-stats

Stats that come up in Miller-Jensen lab work: matched-donor PBMC experiments, before/after stimulation, scRNA-seq differential expression, multiplexed cytokine panels, microfluidic single-cell readouts. The same handful of mistakes recur — wrong unit of replication, no FDR, unpaired tests on paired designs, donor treated as fixed. This skill points at the right tools and flags those traps. For data wrangling see [tabular-data](../tabular-data/SKILL.md); for plotting/QC overlaps see [flow-cytometry](../flow-cytometry/SKILL.md).

## Reach for

- **R (primary for stats — most bio-stats teaching code is R):**
  - `lme4` + `lmerTest` — linear mixed models with p-values. Donor as a random effect for human PBMC work.
  - `emmeans` — estimated marginal means, contrasts, Tukey-style post-hoc on any supported model (incl. `lmer`, `glmer`, `glmmTMB`).
  - `broom` / `broom.mixed` — tidy model output into data frames for plotting/tables.
  - `multcomp` — multiple-comparison adjustments for general parametric models.
  - `DESeq2` / `edgeR` / `limma` — bulk and pseudobulk DE (see [coding-in-r](../coding-in-r/SKILL.md)).
  - `sva` (incl. `ComBat`) — batch correction or surrogate variable estimation.
- **Python (when the pipeline is already Python):**
  - `statsmodels` — GLMs, `MixedLM` for random-effects models, robust SEs.
  - `pingouin` — pandas-friendly paired tests, ANOVA/RM-ANOVA, effect sizes (Cohen d, Hedges g), built-in `padjust='fdr_bh'`.
  - `scipy.stats` — t-test, Wilcoxon, Mann-Whitney, Fisher exact.
  - `scikit-posthocs` — Dunn, Nemenyi, etc. after Kruskal-Wallis.
  - `pydeseq2` — DESeq2 ported to Python; use for pseudobulk DE without rpy2.
- **For scRNA-seq DE: always pseudobulk first.** Aggregate counts to donor × condition (often × cell type), then DESeq2 / edgeR / limma-voom. Cell-level Wilcoxon/t-test is the single most common stats error in this field — see below.

## Read first

- Squair et al. 2021, *Nat Commun* — ["Confronting false discoveries in single-cell differential expression"](https://www.nature.com/articles/s41467-021-25960-2). The pseudobulk paper. Read this before you run any scRNA-seq DE.
- Winter, ["A very basic tutorial for performing linear mixed effects analyses"](https://bodowinter.com/tutorial/bw_LME_tutorial2.pdf) (arXiv [1308.5499](https://arxiv.org/abs/1308.5499)) — clearest on-ramp to `lme4`, random intercepts vs. slopes.
- Benjamini & Hochberg 1995, *JRSS-B* — ["Controlling the false discovery rate"](https://www.jstor.org/stable/2346101). The reason you use `p.adjust(..., method = "BH")` and not Bonferroni at genome scale.

## Common mistakes

- **Cell-level t-test/Wilcoxon on scRNA-seq.** Inflates Type I error massively — cells from one donor are not independent replicates. Pseudobulk (donor × condition × cell type), then DESeq2/edgeR/limma. (Squair 2021.)
- **Unpaired test on a paired design.** Same donor pre/post stim, or matched controls → paired t / signed-rank, or donor random effect. Otherwise you throw away most of your power.
- **No FDR correction.** Any genome- or panel-scale screen needs Benjamini-Hochberg (`p.adjust(method="BH")` / `statsmodels.stats.multitest.multipletests(method='fdr_bh')`). Bonferroni is too conservative for thousands of features.
- **p-value only, no effect size.** Always report log2FC, Cohen's d, or Hedges' g with a 95% CI. A "significant" 1.05× change is not biology.
- **Wilcoxon by reflex.** Non-parametric is not free — it doesn't handle paired/repeated-measures designs gracefully, can't include covariates, and loses power when a linear mixed model would have worked.
- **Donor as a fixed effect** in human PBMC studies. Inter-donor variance is huge; donor is a random effect (`(1 | donor)` in `lme4`).
- **Confounded batches.** If batch is perfectly confounded with condition, no method (`ComBat`, `RUV`, covariate) can rescue you. Randomize at the bench.

## Further reading

- [`emmeans` "Comparisons and contrasts"](https://cran.r-project.org/web/packages/emmeans/vignettes/comparisons.html) — post-hoc done right after `lmer`/`glmer`.
- [statsmodels MixedLM docs](https://www.statsmodels.org/stable/mixed_linear.html) — when you must stay in Python.
- [pingouin `pairwise_tests`](https://pingouin-stats.org/generated/pingouin.pairwise_tests.html) — paired/within-subject tests with effect sizes and `padjust='fdr_bh'` in one call.
- [`sva` vignette (PDF)](https://bioconductor.org/packages/release/bioc/vignettes/sva/inst/doc/sva.pdf) — ComBat and surrogate variables for batch correction.
- [`scikit-posthocs`](https://scikit-posthocs.readthedocs.io/) — Dunn/Nemenyi after Kruskal-Wallis in Python.
- [Bioconductor RNA-seq workflow](https://bioconductor.org/packages/release/workflows/vignettes/rnaseqGene/inst/doc/rnaseqGene.html) — end-to-end DESeq2 including design matrices for paired/blocked layouts.
