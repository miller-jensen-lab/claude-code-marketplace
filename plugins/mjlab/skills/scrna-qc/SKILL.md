---
name: scrna-qc
description: Per-sample quality control for droplet scRNA-seq — empty droplets, doublets, ambient RNA, dying cells — before any biology question. TRIGGER when working with .h5ad / 10x .h5 / cellranger output, scanpy or Seurat QC, doublet detection, ambient RNA removal, mito% filtering, or starting a fresh scRNA-seq analysis.
related:
  - coding-in-python
  - coding-in-r
  - bio-stats
  - bio-data-hygiene
  - cell-cell-communication
updated: 2026-05-14
---
# scRNA-seq QC

The gate everything else passes through. The Miller-Jensen lab runs droplet scRNA-seq on macrophages across stimulations (LPS, IL-4, TNF, IFN-γ, ...) and human PBMC donors; raw 10x output always contains empty droplets, doublets, dying cells, and ambient mRNA "soup" from highly secreting cells. QC is run **per sample** (per 10x lane / per GEM well), *then* samples are integrated — not pooled-then-filtered. Do this before clustering, before annotation, before DE, before [cell-cell-communication](../cell-cell-communication/SKILL.md). Document thresholds in a committed notebook so the filtering decisions are reproducible.

## Reach for

- **Python (primary):**
  - `scanpy` + `anndata` — core scverse stack; loads 10x `.h5` / `.mtx` / `.h5ad`. `sc.pp.calculate_qc_metrics` gives counts, genes, mito%, ribo%, hb% in one call.
  - `scvi-tools` — downstream (integration, doublet detection via `SOLO`); reach for it after QC.
  - `scrublet` — Python-native doublet caller. Older (2019), in maintenance mode but still widely used and fine as a first pass.
  - `doubletdetection` (Shor) — alternative Python doublet caller; co-cited with scrublet.
  - `CellBender` (Babadi lab, Broad) — deep-learning ambient RNA removal directly from raw `raw_feature_bc_matrix.h5`. Output is a corrected count matrix you then feed into scanpy.
  - `pegasus` — Broad's scanpy alternative; not required, but the QC defaults are sensible if you already use it.
- **R (Bioconductor):**
  - `Seurat` v5+ — counterpart stack; `PercentageFeatureSet` for mito/ribo/hb.
  - `DropletUtils::emptyDrops()` — empty-droplet calling from the **raw** `barcodes.tsv.gz` (not the filtered matrix). Use when Cell Ranger's default knee-point call looks wrong, or for non-10x platforms.
  - `scDblFinder` (Bioconductor) — currently the strongest doublet caller per Xi & Li 2021 and follow-up benchmarks. The Python port (`scDblFinder` via `rpy2` / `reticulate`) is the easiest cross-language bridge.
  - `SoupX` — ambient RNA estimation and correction; uses cluster markers to estimate the contamination fraction.
  - `miQC` — model-based joint filtering on (mito%, n_genes); avoids picking a single hard mito threshold.
  - `scran` / `scater` — sister Bioconductor packages; `scater::isOutlier` is the MAD-based outlier helper that the scverse book also uses.

**Defaults that travel well:** MAD-based filtering on `log1p(total_counts)`, `log1p(n_genes_by_counts)`, and `pct_counts_mt` (5×MAD as a starting point, per sample, per the scverse book). Doublets called per sample. Ambient RNA estimated per sample.

## Read first

- [scverse single-cell best-practices book — QC chapter](https://www.sc-best-practices.org/preprocessing_visualization/quality_control.html). The canonical modern walkthrough; covers MAD filtering, scDblFinder, SoupX, all in one chapter.
- [Heumos, Schaar, Lance et al. 2023, *Nat Rev Genet*, "Best practices for single-cell analysis across modalities"](https://www.nature.com/articles/s41576-023-00586-w) — the paper behind the book.
- [Xi & Li 2021, *Cell Systems*, "Benchmarking computational doublet-detection methods"](https://www.cell.com/cell-systems/fulltext/S2405-4712(20)30459-2) — the benchmark; informs why scDblFinder / DoubletFinder beat scrublet on accuracy.

## Common mistakes

- **Pooling samples before QC.** Per-sample distributions of counts, genes, and mito% differ; one global threshold filters real cells from "good" samples and keeps junk from "bad" ones. QC each lane, *then* integrate.
- **A single hard mito% cutoff (e.g., `pct_mt < 10`).** MAD-based filtering (5×MAD on `pct_counts_mt`, per sample) is the scverse default and adapts. Primary human macrophages run hot on mito relative to cell lines, and a stimulated sample isn't comparable to a resting one — a fixed threshold encodes a bias you didn't intend.
- **Skipping doublet detection.** 10x doublet rate is roughly ~0.8% per 1,000 cells loaded; an 8,000-cell lane is ~6% doublets. Run `scDblFinder` (or scrublet) on every sample before integration. Calling doublets *after* integration tends to flag rare-but-real biology as doublets.
- **Filtering twice.** Once at QC, with thresholds in a committed script. Re-filtering after clustering ("this cluster looks like dying cells, drop it") is a circular operation; if you must, document it as cluster removal, not QC.
- **Ignoring ambient RNA.** Macrophages secrete cytokines, complement, lysozyme, ferritin at high copy; that mRNA is everywhere in the soup. Without correction (SoupX or CellBender), every cluster will appear to "express" the dominant secreted markers. This is a Miller-Jensen-lab-specific failure mode.
- **Running CellBender on already-filtered data.** CellBender models the empty-droplet distribution and **needs the raw, unfiltered `raw_feature_bc_matrix.h5`** — not Cell Ranger's `filtered_feature_bc_matrix.h5`. Same warning for `emptyDrops`.
- **Aggressive `n_genes` floors that kill rare populations.** Setting `min_genes=500` (or worse, `min_genes=1000`) discards small or quiescent subpopulations the lab cares about — trained-immunity subsets, dormant HIV-latent cells, non-classical monocytes. Lean low, then revisit if a cluster looks like debris.
- **No per-sample QC notebook in git.** Commit a small `qc/` notebook or script per dataset with before/after plots (violins of counts/genes/mito% per sample, doublet score histogram, ambient-fraction estimate). See [bio-data-hygiene](../bio-data-hygiene/SKILL.md).
- **Treating Cell Ranger's filtered matrix as ground truth.** Cell Ranger's `emptyDrops`-style call is usually fine, but on low-input or non-standard chemistries it isn't. If your knee plot looks ambiguous, rerun `DropletUtils::emptyDrops` on the raw matrix.

## Further reading

- [scverse best-practices book (full)](https://www.sc-best-practices.org/) and its [GitHub repo](https://github.com/theislab/single-cell-best-practices).
- [scanpy docs](https://scanpy.readthedocs.io/) and [Seurat v5 docs](https://satijalab.org/seurat/).
- [scDblFinder Bioconductor page](https://bioconductor.org/packages/release/bioc/html/scDblFinder.html) — the doublet caller to default to.
- [Scrublet (Wolock et al. 2019, *Cell Systems*) — GitHub](https://github.com/AllonKleinLab/scrublet); maintenance mode but still useable as a Python-native option.
- [SoupX (Young & Behjati 2020) — GitHub](https://github.com/constantAmateur/SoupX) and CRAN.
- [CellBender docs](https://cellbender.readthedocs.io/) and [Fleming et al. 2023, *Nat Methods*](https://www.nature.com/articles/s41592-023-01943-7) — the CellBender method paper.
- [`DropletUtils` Bioconductor page](https://bioconductor.org/packages/release/bioc/html/DropletUtils.html) — `emptyDrops`, `barcodeRanks`, knee/inflection diagnostics.
- [`miQC` Bioconductor page](https://bioconductor.org/packages/release/bioc/html/miQC.html) — joint cell-and-mito QC model when a fixed cutoff feels wrong.
- [Luecken & Theis 2019, *Mol Syst Biol*, "Current best practices in scRNA-seq analysis: a tutorial"](https://doi.org/10.15252/msb.20188746) — older but still cited; read for historical context, prefer the 2023 book in practice.
- See also [coding-in-python](../coding-in-python/SKILL.md), [coding-in-r](../coding-in-r/SKILL.md), [bio-stats](../bio-stats/SKILL.md) (pseudobulk after QC), [bio-data-hygiene](../bio-data-hygiene/SKILL.md), [cell-cell-communication](../cell-cell-communication/SKILL.md).
