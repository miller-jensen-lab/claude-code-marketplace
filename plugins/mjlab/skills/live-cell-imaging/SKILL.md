---
name: live-cell-imaging
description: Time-lapse fluorescence imaging for Miller-Jensen lab reporter dynamics (NF-kB / IRF / STAT translocation, HIV LTR reporters) — segmentation, tracking, and per-cell trace extraction. TRIGGER when working with .tif/.tiff stacks, .czi, .nd2, OME-TIFF, OME-Zarr, napari, cellpose, btrack, TrackMate, CellProfiler, or single-cell time-course data.
related:
  - coding-in-python
  - tabular-data
  - flow-cytometry
  - single-cell-secretion
updated: 2026-05-14
---
# Live-cell imaging

Time-lapse fluorescence imaging of macrophages with nuclear-translocation reporters (NF-kB p65, IRF, STAT) and HIV LTR reporters. The goal is almost always per-cell time-course traces — segment nuclei (and cytoplasm), track across frames, extract dynamics features (amplitude, timing, fold-change, oscillation period), then quantify heterogeneity across the population. Single-cell, not field-averaged.

## Reach for

- **Python (primary):**
  - `bioio` (successor to `aicsimageio`, now in maintenance) — read `.czi`, `.nd2`, OME-TIFF without losing metadata
  - `cellpose` (v3+, one-click image restoration → segmentation) for whole cells; `stardist` for nuclei (star-convex shapes)
  - `btrack` — Bayesian single-cell tracking, handles divisions and gaps; `trackpy` if you only need particle linking
  - `napari` — viewer + plugin ecosystem; pair with `napari-aicsimageio` / `napari-bioio` for direct loading
  - `scikit-image` — registration, flat-field, morphology, regionprops
  - `ome-zarr` / `zarr` — chunked storage for multi-TB datasets; stop saving giant TIFFs
- **GUI / Fiji (often paired):**
  - Fiji + TrackMate — gold-standard interactive tracker, scriptable headless via Jython/Groovy for batch
  - ilastik — interactive pixel/object classifier; good for generating seeds or hard-to-segment channels
  - CellProfiler — pipeline-based, headless on a cluster
- **R (alternative):** `celltrackR` for downstream track statistics. Otherwise stay in Python.

## Read first

- [Cellpose3 (Stringer & Pachitariu, Nat Methods 2025)](https://www.nature.com/articles/s41592-025-02595-5) — restoration + segmentation; start here for any new segmentation pipeline. Docs: <https://cellpose.readthedocs.io/>
- [btrack docs + Ulicna et al. 2021](https://btrack.readthedocs.io/) — Bayesian belief matrix, hypothesis model (`P_FP`, `P_link`, `P_branch`, `P_term`); read the configuration page before tuning.
- [Insights on the NF-κB System Using Live Cell Imaging (Front. Immunol. 2022)](https://www.frontiersin.org/journals/immunology/articles/10.3389/fimmu.2022.886127/full) — what dynamics features matter and why population averages mislead.

## Common mistakes

- **Manual tracking past ~20 cells.** Infeasible and irreproducible. Use btrack or TrackMate from the start.
- **Reading `.czi`/`.nd2` with PIL or plain `tifffile`.** You silently lose pixel size, channel names, and time stamps. Use `bioio` (or `aicsimageio` on legacy code).
- **No flat-field / vignetting correction.** Edges of the field bias every downstream metric.
- **Ignoring photobleaching on multi-hour traces.** Use unstimulated control wells or fit a decay and divide; never compare raw intensities across time without it.
- **Whole-cell mean intensity for translocation reporters.** The biology *is* the nuclear/cytoplasmic ratio — segment nucleus and a cytoplasmic ring (or whole-cell minus nucleus) separately.
- **Writing derived TIFs into `data/raw/`.** Raw is immutable. Everything processed goes to `data/derived/` (see `coding-in-python`).

## Further reading

- [napari quick start](https://napari.org/stable/getting_started/quick_start.html) and [tutorials](https://napari.org/stable/tutorials/index.html)
- [OME-Zarr / NGFF spec](https://ngff.openmicroscopy.org/) — the format to migrate toward
- [Image Data Resource (IDR)](https://idr.openmicroscopy.org/) — public example datasets, often with ground-truth tracks
- [bioio docs](https://bioio-devs.github.io/bioio/) and the [aicsimageio → bioio migration notes](https://github.com/AllenCellModeling/aicsimageio)
- [TrackMate scripting](https://imagej.net/plugins/trackmate/scripting/scripting) for headless batch runs on a cluster
- [CellProfiler](https://cellprofiler.org/) and [ilastik](https://www.ilastik.org/documentation/) docs
