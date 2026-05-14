---
name: single-cell-secretion
description: Pointer for analyzing microfluidic single-cell cytokine secretion data (IsoPlexis / IsoLight / IsoSpark and similar platforms). TRIGGER when the user mentions IsoPlexis, IsoLight, IsoSpark, IsoSpeak, IsoCode, CodePlex, polyfunctionality, PSI, Polyfunctional Strength Index, single-cell cytokine secretion, multiplex secretion CSV, or per-cell cytokine intensities.
related:
  - coding-in-python
  - coding-in-r
  - tabular-data
  - bio-stats
updated: 2026-05-14
---
# Single-cell secretion

Microfluidic single-cell multiplex cytokine secretion: each cell is isolated in a chamber/droplet, and 10-42 cytokines are quantified per cell. The lab uses this for macrophage cytokine heterogeneity (TLR responses, polarization) and T-cell polyfunctionality in HIV / latency-reversal contexts. The dominant platform is IsoPlexis (now Bruker Cellular Analysis) — IsoLight/IsoSpark instruments, IsoCode chips, CodePlex bulk panels, IsoSpeak analysis software.

## The ecosystem is thin — be honest

There is **no canonical open-source package** for this modality. No scanpy, no Seurat, no Bioconductor home. Most published analyses are either (a) done inside vendor IsoSpeak and exported as figures, or (b) custom Python/R scripts on the per-cell intensity CSV that IsoSpeak exports. Do **not** invent a library. If a workflow is needed, write it directly — PSI and polyfunctionality are short, well-defined formulas.

## Reach for

- **IsoSpeak CSV exports** → pandas / Polars + DuckDB (see `coding-in-python`, `tabular-data`) or tidyverse in R (`coding-in-r`). The per-cell file is wide: one row per cell, one column per cytokine, plus sample/donor/stim metadata.
- **PSI / polyfunctionality**: implement directly per Ma 2011. ~20 lines. Define a per-cytokine threshold first (vendor default, or fixed value sanity-checked against unstim controls), binarize, then `PSI = (% cells secreting >=2) * mean(sum of intensities across secreted cytokines)`. Confirm the exact formula against the paper / IsoSpeak documentation for your panel.
- **Dimensionality reduction on cytokine vectors**: UMAP via `umap-learn` or scanpy is fine, but the space is low-dim (5-32 features) and zero-inflated — PCA + heatmaps often communicate more.
- **Existing tool worth knowing**: `IsoAnalytics` (Palmer & Koh, Bioinf. Adv. 2023) — web server + Python code at https://github.com/zhanxw/Isoplexis_Data_Analysis for IsoSpeak exports. Read it before reimplementing.
- **Bead-based multiplex (Luminex / MSD)**: same tabular shape, same tools, but it is *bulk* — do not compute PSI or polyfunctionality (no per-cell resolution).

## Read first

- Ma et al., *Nature Medicine* 17:738 (2011) — the foundational microfluidic single-cell cytokine paper, original PSI framework: https://www.nature.com/articles/nm.2375
- Lu, Xue, ..., **Miller-Jensen**, Fan, *PNAS* 112:E607 (2015) — 42-plex macrophage secretion, deep functional heterogeneity under TLR ligands. Lab paper; use it as the methods reference for in-house work: https://www.pnas.org/doi/10.1073/pnas.1416756112
- Palmer & Koh, *Bioinformatics Advances* 3:vbad077 (2023) — IsoAnalytics; describes the canonical analysis steps for an IsoPlexis per-cell CSV: https://academic.oup.com/bioinformaticsadvances/article/3/1/vbad077/7204422

## Common mistakes

- **Inconsistent "secretion" thresholds.** Define one threshold per cytokine (vendor default, or fixed intensity) and apply identically across all samples/donors. Re-thresholding per sample inflates polyfunctionality differences.
- **Comparing PSI across donors without normalization.** Donor-to-donor variation dominates. Use paired pre-stim vs. stim deltas within donor, or include donor as a random effect (`bio-stats`).
- **Comparing PSI across panels.** PSI scales with panel size — a 32-plex PSI is not comparable to a 10-plex PSI from the same cells. Always report panel composition.
- **scRNA-seq-style clustering on raw cytokine vectors** without acknowledging that the feature space is small, sparse, and zero-inflated. Inspect raw distributions and dropout patterns before clustering; binary "secretion fingerprints" are often more interpretable than k-means on intensities.
- **Assuming IsoSpeak gating is reproducible.** Export gates/thresholds and version-control them alongside the CSV (see lab reproducibility guidance).

## Further reading

- Lu et al., *Analytical Chemistry* 85:2548 (2013) — original 14-plex single-cell secretomic platform: https://pubs.acs.org/doi/10.1021/ac400082e
- Bounab et al., *Cell Reports Methods* 3:100502 (2023) — droplet-based single-cell deep cytokine phenotyping, stimulation-specific signatures: https://pmc.ncbi.nlm.nih.gov/articles/PMC10391336/
- Vistain & Tay et al., reviewed in *Annual Review of Analytical Chemistry* — single-cell protein secretion detection and profiling: https://www.annualreviews.org/doi/10.1146/annurev-anchem-061318-115055
- Bruker Cellular Analysis / IsoPlexis IsoSpeak product docs (for current PSI definition and panel lists): https://isoplexis.com/solutions/isospeak-immune-polyfunctional-strength/
- *eLife* 2023 — Stimulation-induced cytokine polyfunctionality as a dynamic concept (critique and refinement of static PSI): https://elifesciences.org/articles/89781
- Junkin et al., *Cell Reports* (2016, paracrine macrophage signaling under TLR4, **Miller-Jensen lab**) — analytical approach to single-cell secretion + GGM network inference: https://pmc.ncbi.nlm.nih.gov/articles/PMC5735825/
