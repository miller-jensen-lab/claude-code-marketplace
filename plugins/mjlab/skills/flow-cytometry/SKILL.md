---
name: flow-cytometry
description: Flow cytometry analysis for Miller-Jensen lab macrophage panels and ICS — reading .fcs, reproducible gating, transforms, compensation, and FlowJo round-trip. TRIGGER when working with .fcs files, FlowJo .wsp workspaces, gating, compensation, flowCore/FlowKit, or marker panels.
related:
  - coding-in-r
  - coding-in-python
  - bio-stats
  - plotting
updated: 2026-05-14
---
# Flow cytometry

The lab runs macrophage surface-marker panels and intracellular cytokine staining (ICS) on conventional fluorescence cytometers, plus the occasional spectral run. Most students gate in FlowJo by clicking, never export the gating strategy, and end up with analyses that no one (including future-you) can reproduce. This skill points you at the scripted-gating ecosystem so figures survive review and revisions.

## Reach for

- **R (primary — the cytoverse is more mature for reproducible pipelines):**
  - `flowCore` — read `.fcs`, core data structures
  - `flowWorkspace` + `CytoML` — import and round-trip FlowJo `.wsp`
  - `ggcyto` — ggplot2-based publication plots with cytometry-aware axes/gates
  - `openCyto` — automated, template-driven hierarchical gating
  - `CytoExploreR` — interactive scripted gating that saves the gates as code
- **Python (use if your downstream pipeline is already Python):**
  - `FlowKit` — modern, BD-backed, GatingML 2.0, partial FlowJo `.wsp` round-trip
  - `cytoflow` — full quantitative pipeline, opinionated about experiment design
  - `FlowCytometryTools` — older, still works for quick reads

## Read first

- [flowCore vignette (Bioconductor)](https://bioconductor.org/packages/release/bioc/vignettes/flowCore/inst/doc/HowTo-flowCore.pdf) — minimum viable `.fcs` -> compensated -> transformed pipeline
- [openCyto introduction](https://www.bioconductor.org/packages/release/bioc/vignettes/openCyto/inst/doc/openCytoVignette.html) — CSV gating-template approach that survives peer review
- [FlowKit paper, Front. Immunol. 2021](https://www.frontiersin.org/journals/immunology/articles/10.3389/fimmu.2021.768541/full) — design intent and round-tripping with FlowJo from Python

## Common mistakes

- **Linear axes on fluorescence channels.** Use `flowCore::estimateLogicle` (biexponential) or arcsinh. Cofactor matters: conventional flow ~150, mass cytometry ~5. Spectral unmixed data behaves like flow.
- **Compensating after transforming.** Compensation is a linear operation on linear-scale data. Apply spillover first, then transform.
- **Gates only in FlowJo (clicks, no export).** Either export the `.wsp` and load via `flowWorkspace::open_flowjo_xml` so the gates are versionable, or define gates with `openCyto`/`CytoExploreR` so they live in code. Click-trail gates do not reproduce.
- **Hand-curated gate coordinates baked into the script.** Use a `gatingTemplate` (openCyto) or data-driven gate functions (`mindensity`, `flowClust.2d`). Hard-coded thresholds break on the next experiment.
- **UMAP / FlowSOM on raw fluorescence.** Compensate, transform, then per-marker scale (z-score or 0-1) before embedding — otherwise the brightest channel dominates.
- **Reusing one compensation matrix across days/cytometers.** Compensation is instrument- and panel-day-specific. Acquire single-stain controls per experiment.

## Further reading

- [Bioconductor cytoverse landing page](https://bioconductor.org/packages/release/bioc/html/flowWorkspace.html) — flowWorkspace + GatingSet objects
- [ggcyto top features vignette](https://www.bioconductor.org/packages/devel/bioc/vignettes/ggcyto/inst/doc/Top_features_of_ggcyto.html)
- [CytoExploreR docs](https://dillonhammill.github.io/CytoExploreR/) — interactive gate drawing that emits code
- [FlowKit docs](https://flowkit.readthedocs.io/en/latest/) and [GitHub](https://github.com/whitews/FlowKit)
- [CyTOF / high-dim workflow (Bioconductor)](https://www.bioconductor.org/packages/release/workflows/vignettes/cytofWorkflow/inst/doc/cytofWorkflow.html) — relevant for any high-parameter spectral panel
- [OpenCyto paper, PLOS Comp Biol 2014](https://journals.plos.org/ploscompbiol/article?id=10.1371/journal.pcbi.1003806) — the reproducibility argument in full
