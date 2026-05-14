---
name: cell-cell-communication
description: Infer ligand-receptor signaling between cell types from scRNA-seq (and spatial) data. TRIGGER when the user mentions CellChat, CellPhoneDB, LIANA, NicheNet, Squidpy, "ligand-receptor", "cell-cell communication", "CCC", "intercellular signaling", "macrophage-T-cell crosstalk", "M1/M2 signaling", or has annotated single-cell data and wants to know which cell types are talking to which.
related:
  - coding-in-r
  - coding-in-python
  - bio-stats
  - plotting
updated: 2026-05-14
---
# Cell-cell communication

Inferring which cell types signal to which from scRNA-seq expression of ligands and receptors. In the Miller-Jensen lab this is the natural follow-up after clustering and annotation of macrophage scRNA-seq: M1 vs. M2 crosstalk, macrophage-T-cell axis in HIV-infected vs. bystander conditions, cytokine-driven niche effects, and stimulation-vs-control differential communication. The output is a ranked list of L-R pairs plus per-pathway "signaling probability" between cell-type pairs — useful for hypothesis generation, NOT a mechanistic claim.

## Reach for

R has the stronger ecosystem here. Use Python only if the upstream stack (Scanpy/AnnData) is already Python or if you need spatial.

- **R (primary):**
  - `LIANA` (saezlab) — multi-method consensus wrapper; **start here**. Aggregates CellChat, CellPhoneDB, SingleCellSignalR, NATMI, Connectome, logFC and gives a rank-aggregated result. Single-method bias is the dominant failure mode; consensus mitigates it.
  - `CellChat` v2 (`jinworks/CellChat`, Jin et al. 2024 Nat Protoc) — best single method when you need pathway-level aggregation, signaling-role analysis (sender/receiver/mediator/influencer), and per-condition comparison plots. The figures are publication-ready.
  - `nichenetr` (saeyslab) — different question: given a downstream DE signature in a receiver cell, which upstream ligands explain it? Use *alongside* LIANA/CellChat, not instead of.
- **Python (alternative):**
  - `liana-py` — Python port of LIANA; same consensus logic, AnnData-native. Use if Scanpy is already your stack.
  - `CellPhoneDB` v5 (Troulé et al. 2025 Nat Protoc) — human-only LR DB; v5 adds non-peptide ligands and the CellSign TF-activity module. Fine, but prefer liana-py for breadth.
  - `Squidpy` — required when you have spatial coordinates (Visium, MERFISH, Xenium). Don't use vanilla CellChat/LIANA for spatial; use `LIANA+` or Squidpy's neighborhood-aware tests.

## Read first

- [LIANA+ (Dimitrov et al., Nat Cell Biol 2024)](https://www.nature.com/articles/s41556-024-01469-w) — current state of the art; explains why consensus + why spatial needs different inference.
- [CellChat v2 protocol (Jin et al., Nat Protoc 2024)](https://www.nature.com/articles/s41596-024-01045-4) — the canonical walkthrough; read the "comparison analysis of multiple datasets" section before doing M1/M2 or stim/ctrl contrasts.
- [Dimitrov et al., Nat Commun 2022 — method comparison](https://www.nature.com/articles/s41467-022-30755-0) — the benchmark that motivated LIANA; shows methods disagree substantially.

## Common mistakes

- **Running one method and trusting it.** Methods disagree on >50% of top hits. Always use LIANA consensus, or run >=2 methods and report overlap.
- **Pooling conditions then inferring once.** For infected-vs-bystander or stim-vs-ctrl, run inference *per condition* and then use `CellChat::compareInteractions` / `liana`'s differential modes. Pooling hides the biology you care about.
- **Treating the L-R database as ground truth.** CellChatDB, OmniPath, CellPhoneDB are curated and incomplete; novel/non-canonical interactions will be missed. Cross-check top hits against literature before claims.
- **Comparing raw communication scores across datasets/batches.** Scores depend on library size, cluster size, and dropout. Use rank- or quantile-based comparison, or restrict to within-dataset contrasts.
- **Skipping QC and annotation sanity checks.** Garbage clusters in -> garbage signaling out. The cell-type labels are the single biggest determinant of the result.

## Further reading

- [LIANA R docs / vignettes](https://saezlab.github.io/liana/) and [liana-py docs](https://liana-py.readthedocs.io/)
- [CellChat GitHub (jinworks fork is current)](https://github.com/jinworks/CellChat)
- [CellPhoneDB v5 (Nat Protoc 2025)](https://www.nature.com/articles/s41596-024-01137-1)
- [NicheNet / nichenetr GitHub](https://github.com/saeyslab/nichenetr) — for ligand-activity prediction from a receiver-cell DE signature
- [LIANA + Tensor-cell2cell (Cell Rep Methods 2024)](https://www.cell.com/cell-reports-methods/fulltext/S2667-2375(24)00089-4) — multi-sample / multi-condition decomposition; useful for time-course or donor panels
- [Advances and challenges in CCC inference (Brief Bioinform 2025)](https://academic.oup.com/bib/article/26/3/bbaf280/8169297) — current review of the field
- See also [coding-in-r](../coding-in-r/SKILL.md), [coding-in-python](../coding-in-python/SKILL.md), [bio-stats](../bio-stats/SKILL.md), [plotting](../plotting/SKILL.md).
