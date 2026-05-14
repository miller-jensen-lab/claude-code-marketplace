---
name: smfish
description: Single-molecule FISH spot detection and per-cell transcript counts for Miller-Jensen lab bursting / HIV-transcription work. TRIGGER when working with smFISH images, big-fish, FISH-quant, RS-FISH, per-cell transcript count tables, or fitting bursting models.
related:
  - coding-in-python
  - live-cell-imaging
  - stochastic-gene-expression
  - bio-stats
updated: 2026-05-14
---
# smFISH

The lab uses smFISH to count individual transcripts per cell — typically HIV LTR-driven transcripts (with intronic probes flagging nascent transcription sites at the integrated provirus) or cellular target genes. The per-cell count distributions and the bright nuclear transcription-site spots feed bursting-model fits (telegraph, Beta-Poisson). This skill covers the **measurement** side (image -> spots -> counts). For the modeling side, cross to [stochastic-gene-expression](../stochastic-gene-expression/SKILL.md). For shared image ops (deconvolution, segmentation, registration) see [live-cell-imaging](../live-cell-imaging/SKILL.md).

## Reach for

- **Python (primary):**
  - `big-fish` — current canonical spot detection (Imbert, Mueller et al.); LoG + local-max + subpixel; `bigfish.detection.detect_spots`, `decompose_dense` for clustered/saturated regions.
  - `FISH-quant v2` — the broader framework built around big-fish: ImJoy plugins, segmentation, RNA-localization features, tutorial notebooks.
  - `starfish` — broader spatial-transcriptomics framework; works for smFISH but less actively maintained, prefer big-fish for single-molecule counting.
  - downstream: `cellpose` / `stardist` for nucleus + cell masks; pandas / Polars for per-cell count tables -> [stochastic-gene-expression](../stochastic-gene-expression/SKILL.md).
- **Fiji / GUI:**
  - **RS-FISH** (Preibisch lab, *Nat. Methods* 2022) — radial-symmetry spot detection, fast, scales to large/cleared volumes, scriptable.
  - **FISH-quant (original MATLAB)** — still cited; new work should use v2 / big-fish.
- **R:** not worth the switch for detection — bring counts into R for downstream stats.

## Read first

- [big-fish GitHub + docs](https://github.com/fish-quant/big-fish) — start with the Jupyter notebooks; `detect_spots` + `decompose_dense` is the core workflow.
- [Imbert et al., *RNA* 2022 — FISH-quant v2](https://rnajournal.cshlp.org/content/28/6/786.full) — the reference paper for the Python framework; read the modules section.
- [Bahry et al., *Nat. Methods* 2022 — RS-FISH](https://www.nature.com/articles/s41592-022-01669-y) — when you want the Fiji route or need to process big volumes.

## Common mistakes

- **Saturated / merged spots counted as one.** At high expression (and at transcription sites) spots overlap. Use `bigfish.detection.decompose_dense` or fit clusters; do not just thresh-and-count.
- **Cytoplasm-only counts for bursting.** The bright nuclear focus at the gene locus (1-2 per cell for HIV provirus) is the nascent-transcription signal — segment nucleus separately and treat TS spots distinctly from mature mRNA.
- **One global threshold for the whole slide.** Field-of-view brightness varies with illumination and depth; let big-fish auto-threshold per FOV, or calibrate per image.
- **No PSF / deconvolution awareness.** Spot sigma must match the imaging PSF — set `voxel_size` and `spot_radius` correctly in big-fish or detection accuracy collapses.
- **Too few cells for bursting fits.** Distributional fits need cells — aim for >=200, ideally >=500 per condition. See [stochastic-gene-expression](../stochastic-gene-expression/SKILL.md).
- **Mixing channels / probes without controls.** Always have a no-probe and a housekeeping-gene control on the same slide for thresholding sanity.

## Further reading

- [big-fish automated spot detection docs](https://big-fish.readthedocs.io/en/stable/detection/spots.html) — parameter meanings and the multi-scale detection API.
- [FISH-quant landing page](https://fish-quant.github.io/) — index of the ecosystem (big-fish, sim-fish, ImJoy plugins, tutorials).
- [RS-FISH GitHub](https://github.com/PreibischLab/RS-FISH) — Fiji install, macro examples, cluster mode.
- [Raj et al., *Nat. Methods* 2008](https://www.nature.com/articles/nmeth.1253) — the original smFISH method paper; still the conceptual baseline.
- [Rodriguez & Larson, *Annu. Rev. Biochem.* 2020 — Transcription in Living Cells](https://www.annualreviews.org/doi/10.1146/annurev-biochem-011520-105250) — bursting + smFISH context.
- [Leyes Porello, Trudeau & Lim 2023, *Development* — "Transcriptional bursting: stochasticity in deterministic development"](https://pmc.ncbi.nlm.nih.gov/articles/PMC10323239/) — what the count distributions mean.
