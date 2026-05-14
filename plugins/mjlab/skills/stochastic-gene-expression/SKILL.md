---
name: stochastic-gene-expression
description: Bursting models (telegraph / Beta-Poisson / NB) and Gillespie / CME simulation for Miller-Jensen lab single-cell expression heterogeneity (HIV latency, macrophage response). TRIGGER when fitting burst frequency / burst size from smFISH or scRNA-seq distributions, simulating gene-expression stochastics, or working with the telegraph model.
related:
  - coding-in-python
  - smfish
  - bio-stats
  - transcriptional-bursting
updated: 2026-05-14
---
# Stochastic gene expression

The mathematical / modeling counterpart to smFISH measurements. A promoter
flips between OFF and ON states (the **telegraph model**, Peccoud & Ycart
1995); transcription fires while ON, producing **bursts** parameterized by
burst frequency (k_on) and burst size (k_m / k_off). The steady-state mRNA
distribution is **Beta-Poisson**, well approximated by a **Negative Binomial**.
In the Miller-Jensen lab this underlies work on HIV proviral reactivation
(Tat-driven positive feedback, latency entry/exit) and macrophage cytokine
heterogeneity (TNF, IFN-beta). See `smfish` for the measurement side and
the planned `transcriptional-bursting` primer for the biology.

## Reach for

- **Python (primary; expect to write ~30-100 lines of custom likelihood code):**
  - `scipy.stats` (`nbinom`, `betabinom`) + `scipy.optimize.minimize` or
    `iminuit` — MLE for Negative Binomial / Beta-Poisson on per-cell counts
  - `emcee` or `pymc` — Bayesian posterior for (k_on, k_off, k_m); useful when
    parameters are weakly identified
  - `GillesPy2` (https://github.com/StochSS/GillesPy2) — Gillespie SSA /
    tau-leaping, SBML-compatible; the maintained successor to older StochPy
  - Hand-rolled **FSP (finite state projection)** (Munsky & Khammash 2006) —
    a few hundred lines of NumPy gives you the exact CME solution for one or
    two species; usually faster and cleaner than a moment-closure library
- **R (alternative):**
  - `BPSC` (https://github.com/nghiavtr/BPSC) — Beta-Poisson GLM for scRNA-seq
    DE; handles bimodality better than gamma-Poisson on ~90% of transcripts
- **Published pipeline:** `txburst` (https://github.com/sandberg-lab/txburst,
  Larsson et al. *Nature* 2019) — `txburstML.py`, `txburstPL.py`,
  `txburstTEST.py` give genome-scale burst inference from allele-resolved
  scRNA-seq. Read the scripts; they're short and a good template.
- **Most lab code is custom.** Don't pull in a heavyweight library when a
  30-line NB MLE on smFISH counts will do.

## Read first

- Peccoud & Ycart 1995 (*Theor. Popul. Biol.*) — the telegraph model.
  Paywalled; for a free modern derivation see
  https://www.biorxiv.org/content/10.1101/2020.01.05.895359v1.full (Ham,
  Schnoerr, Brackston & Stumpf, *Exactly solvable models of stochastic gene
  expression*; later in *J. Chem. Phys.* 2020).
- Larsson et al. 2019, *Nature* — https://www.nature.com/articles/s41586-018-0836-1 —
  genomic encoding of burst kinetics; promoters set burst size, enhancers
  set burst frequency. Pairs with the `txburst` code.
- Munsky & Khammash 2006, *J. Chem. Phys.* —
  https://pubs.aip.org/aip/jcp/article/124/4/044104/561868 — the FSP
  algorithm for the CME, with an accuracy certificate. The standard reference
  for "solve the master equation directly instead of simulating it."

## Common mistakes

- **Poisson when overdispersed.** smFISH and scRNA-seq counts are almost
  always overdispersed. Test (variance/mean, or a likelihood-ratio vs. NB)
  before defaulting to Poisson.
- **Ignoring cell cycle.** Gene-copy doubling in S/G2 inflates apparent burst
  size and adds a bimodal artifact. Gate on DAPI / cell-cycle stage, or
  include ploidy as a covariate.
- **Too few cells for a distributional fit.** Burst-parameter inference is
  weakly identified; expect unstable fits below ~200 cells per condition,
  and aim for ≥500 for confident (k_on, k_off, k_m) estimates.
- **Conflating intrinsic and extrinsic noise.** Single-channel smFISH cannot
  separate them (Elowitz et al. 2002). Use two-color reporters, dual-allele
  smFISH, or carefully matched paired conditions.
- **Calling a fine-grained Gillespie run a "CME solution."** SSA gives
  samples; FSP gives the distribution. For small state spaces and steady
  state, use FSP. For large or transient regimes, use SSA / tau-leaping.

## Further reading

- GillesPy2 paper, *Letters in Biomathematics* 2023 —
  https://pmc.ncbi.nlm.nih.gov/articles/PMC10470263/ — framework overview.
- `txburst` repository — https://github.com/sandberg-lab/txburst
- Elowitz, Levine, Siggia, Swain 2002, *Science* —
  https://www.science.org/doi/10.1126/science.1070919 — the two-color
  experiment defining intrinsic vs. extrinsic noise.
- Sanchez & Golding 2013, *Science* —
  https://www.science.org/doi/10.1126/science.1242975 — review of genetic
  and cellular determinants of noise; good conceptual map.
- `BPSC` — https://github.com/nghiavtr/BPSC — Beta-Poisson DE for scRNA-seq.
- `BurstGTM` — https://github.com/cellfate/BurstGTM — generalized telegraph
  model inference from snapshot data, if you need more than two promoter
  states.
