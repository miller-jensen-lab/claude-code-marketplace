---
name: bio-data-hygiene
description: Sample sheets as source of truth, file naming, donor anonymization, GEO/SRA submission prep for Miller-Jensen lab projects. TRIGGER when starting a new dataset, preparing a submission, designing a sample sheet, naming raw data files, or auditing metadata.
related:
  - tabular-data
  - using-git-and-github
  - starting-a-new-project
  - reproducible-envs
updated: 2026-05-14
---
# Bio data hygiene

A versioned sample sheet, predictable file names, and opaque donor codes are cheap up front and uncrackable to retrofit. Six months from now, you (or whoever inherits the project) should be able to tell what every file is from its name alone, and reproduce the analysis from a single CSV plus the code. This skill is the boring discipline that makes everything else — `tabular-data`, the analysis skills, GEO submission — actually work.

## Reach for

- **Sample sheets as version-controlled CSV/TSV.** Plain text in git, one row per sample, controlled vocabulary in every categorical column. Not Excel-only. Not a Google Sheet that gets silently edited. Validate at load time (see [tabular-data](../tabular-data/SKILL.md)).
- **`ffq`** — find FASTQs across SRA/ENA/GEO/DDBJ from any accession. https://github.com/pachterlab/ffq
- **`nf-core/fetchngs`** — Nextflow pipeline to fetch and standardize public data; outputs a clean sample sheet. https://nf-co.re/fetchngs
- **`sra-tools` / `fastq-dl`** — direct SRA pulls when you don't need the orchestration.
- **MIAME / MINSEQE** — community metadata standards. GEO enforces them. https://www.ncbi.nlm.nih.gov/geo/info/MIAME.html
- **GEO submission**: NCBI's metadata spreadsheet + raw + processed + (for arrays) SOFT. Allow ~2-4 weeks for curator review. https://www.ncbi.nlm.nih.gov/geo/info/submission.html
- **ENA / SRA submission**: Webin (interactive or REST/CLI), or NCBI's SRA portal. https://ena-docs.readthedocs.io/en/latest/submit/general-guide.html

## Read first

- [GEO submission overview (NCBI)](https://www.ncbi.nlm.nih.gov/geo/info/submission.html) — what to upload, in what shape, and why curators reject submissions.
- [Ziemann et al. 2021, "Gene name errors: lessons not learned"](https://journals.plos.org/ploscompbiol/article?id=10.1371/journal.pcbi.1008984) — 30% of recent papers with Excel gene lists still ship corrupted symbols. Read this once; never round-trip a gene list through Excel again.
- [nf-core/fetchngs docs](https://nf-co.re/fetchngs) — concrete example of the shape a clean sample sheet should take when fetched from public data.

## Common mistakes

- **Free-text condition columns.** "Untreated", "untreated", "UT", "control" all in one column means every downstream `group_by` is wrong. Pick a controlled vocabulary, document it in the sample sheet header or a `README`, and validate on load.
- **Identifiable donor IDs.** Initials, MRNs, dates of birth — never. Use opaque codes (`D01`, `D02`, ...); keep the mapping in a single file listed in `.gitignore` (and not in cloud-synced folders that get shared by accident). IRB-relevant.
- **Donor confounded with batch.** Process donors in a randomized order across days/lanes/chips, not D01-on-Monday, D02-on-Tuesday. Otherwise "donor effect" and "batch effect" are the same variable and you cannot separate them.
- **Excel mangling gene names** (`SEPT2`, `MARCH1`, `DEC1` → dates; some Ensembl IDs → floats). See [tabular-data](../tabular-data/SKILL.md). Never open a gene list in Excel without setting column types to Text first — better, do not open it in Excel at all.
- **Renaming raw files after analysis starts.** The pipeline that consumed the old names breaks silently or, worse, picks up the wrong file. Lock names at deposit; track changes via the sample sheet, not by `mv`.
- **Sample sheet only in a Google Sheet.** It is now the single point of failure and the cause of every reproducibility ticket. Commit a CSV; if collaborators must edit in a sheet, export to CSV on a schedule and diff it in git.
- **Raw data only on one laptop.** Raw FASTQ / FCS / TIFF lives in at least two places, one of them not in the building. See [starting-a-new-project](../starting-a-new-project/SKILL.md) for lab storage conventions.

## Naming convention

Adopt `${YYYY-MM-DD}_${donor}_${condition}_${rep}.${ext}` — e.g. `2026-03-14_D04_LPS-4h_rep2.fastq.gz`. Rules:

- Lowercase or consistent case; underscores between fields; hyphens within fields.
- No spaces, parens, quotes, slashes, or unicode. Shell-glob and `grep`-friendly.
- ISO-8601 dates sort lexicographically.
- Same field order across every file in the project. The sample sheet's `sample_id` column should equal the stem.

## Submission prep checklist

- [ ] Sample sheet (CSV) matches files on disk; checksums (`md5sum`) recorded.
- [ ] Controlled-vocabulary columns validated; no free text in categoricals.
- [ ] Donor codes opaque; mapping file is **not** in the submission bundle.
- [ ] Raw + processed both prepared; processed files describe their pipeline (versions, params).
- [ ] MIAME/MINSEQE fields filled (protocols, instrument, library prep, alignment).
- [ ] README in the submission bundle pointing to the public code repo and commit hash.

## Further reading

- [MIAME and MINSEQE guidelines (GEO)](https://www.ncbi.nlm.nih.gov/geo/info/MIAME.html)
- [FGED Society: MINSEQE](https://www.fged.org/projects/minseqe/) — the source standard.
- [ENA general submission guide](https://ena-docs.readthedocs.io/en/latest/submit/general-guide.html)
- [SRA Submission Portal (NCBI)](https://submit.ncbi.nlm.nih.gov/subs/sra/)
- [FAIR Guiding Principles (Wilkinson et al. 2016)](https://www.nature.com/articles/sdata201618) — the F/A/I/R checklist your data should satisfy.
- [nf-core/fetchngs](https://nf-co.re/fetchngs) — what a well-shaped public-data fetch looks like.
- [Ziemann et al. 2021, gene name errors (PLOS Comp Bio)](https://journals.plos.org/ploscompbiol/article?id=10.1371/journal.pcbi.1008984)
