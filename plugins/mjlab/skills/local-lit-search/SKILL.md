---
name: local-lit-search
description: Build and query a local SQLite FTS5 corpus of the scientific literature for a Miller-Jensen lab project — interview-driven PubMed pulls, Semantic Scholar citation enrichment, PMC full-text fetch with download safeguards, and grounded `[PMID:…]` citations. TRIGGER when the user asks to build a literature corpus, write a manuscript intro that needs stable citations, do a paper-replication lit review, or get reproducible answers across sessions on a specific research question. For ad-hoc / single-query lookups, prefer [literature-search](../literature-search/SKILL.md).
related:
  - literature-search
  - zotero
  - using-git-and-github
  - bio-data-hygiene
  - starting-a-new-project
updated: 2026-05-14
---
# Local literature search

This skill builds and queries a **local, reproducible SQLite FTS5 corpus** of papers for a single research question. Use it when the answer needs to stay the same six months from now — manuscript introductions, paper-replication repos, an ongoing topic the user wants to revisit without re-pulling fresh data each time.

For ad-hoc lookups (single DOI, "what's the latest on X today?"), use [literature-search](../literature-search/SKILL.md) instead — calling public REST APIs directly is faster and lighter than spinning up a corpus.

## Cardinal rules

- **Cite every factual claim inline as `[PMID:12345678]`.** No exceptions. If a fact isn't in the corpus, say so honestly and expand the corpus rather than filling from training data.
- **Search before answering.** Run at least 3 different FTS5 queries (synonyms, angles, alternate spellings) per question. Then read the top 3–5 hits' full text before drafting a synthesis.
- **The corpus is a snapshot, not the world.** If the user asks about something the corpus doesn't cover, say so and offer to expand with targeted new queries — don't pretend the corpus is exhaustive.
- **Polite-pool email** on all PubMed/Semantic Scholar/Unpaywall traffic. NCBI promotes you to 10 req/s with an `NCBI_API_KEY`; without one you're capped at 3 req/s and rate-limit 429s waste real time.

## Where the corpus lives

The scripts resolve their data directory in this order:

1. `$LIT_SEARCH_DATA_DIR` env var (set this for a shared lab-wide corpus, e.g. `~/Documents/mjlab-lit/`)
2. `./data/` relative to the directory you run them from (the default; one corpus per project)

Layout:

```
<project>/
├── data/
│   ├── lit-search.db         # SQLite + FTS5 index
│   └── fulltext/<PMID>.json  # structured full-text per paper
└── .env                       # NCBI_API_KEY, SEMANTIC_SCHOLAR_KEY (gitignored)
```

Add `data/lit-search.db` and `data/fulltext/` to `.gitignore` unless the project is a paper-replication repo and the user wants to commit the snapshot. See [using-git-and-github](../using-git-and-github/SKILL.md).

## Tooling

The shipped scripts use **`uv`** with PEP 723 inline metadata — no `pip install`, no venv. The user just needs `uv` and `just` on PATH (both `brew install`).

All scripts live in the plugin install dir. Invoke via `just` from the project root, which the shipped `justfile` makes ergonomic:

```bash
# from project root, one-time copy of the thin justfile entry point
cp "$CLAUDE_PLUGIN_ROOT/skills/local-lit-search/justfile" .
just setup   # creates data/lit-search.db + data/fulltext/
```

Or invoke scripts directly without a justfile (e.g., on a shared workstation where you don't want to vendor anything):

```bash
uv run "$CLAUDE_PLUGIN_ROOT/skills/local-lit-search/scripts/setup.py"
uv run "$CLAUDE_PLUGIN_ROOT/skills/local-lit-search/scripts/search_pubmed.py" "TNF NF-kB single-cell" --max-results 100
```

If `$CLAUDE_PLUGIN_ROOT` isn't exported, the path is `~/.claude/plugins/marketplaces/miller-jensen-lab/claude-code-marketplace/plugins/mjlab/skills/local-lit-search/`.

## Download safeguards

`fetch_fulltext.py` ships with hard caps to protect a laptop:

- **Per-response size**: 50 MB (`LIT_SEARCH_MAX_BYTES`). Curl uses `--max-filesize` to abort cleanly; PMC XML responses are size-checked post-read.
- **Per-paper text length**: 50,000 words (`LIT_SEARCH_MAX_WORDS`). Trafilatura/JATS extractions get truncated above this — protects against bad parses or multi-paper PDFs that confuse extractors.
- **Run-total warning** at 2 GB downloaded (`LIT_SEARCH_RUN_WARN_BYTES`). Logged loudly but not enforced; the user decides whether to interrupt.
- **Per-domain rate limits** on `eutils.ncbi.nlm.nih.gov`, `api.unpaywall.org`, and publisher sites (2s default).
- **`--limit N`** flag on `fetch_fulltext` caps papers per invocation; default 50.

Override the byte/word caps via env vars only if you really know what you're doing.

## Workflow

### 1. Interview the user about the research topic

Save to `data/context.json` for future sessions:

```json
{
  "topic": "TNF-induced NF-kB dynamics in macrophages",
  "purpose": "manuscript intro for Bridges et al. 2026",
  "key_questions": [
    "How is burst size vs. frequency dissected in macrophage TNF signaling?",
    "What single-cell methods have been used?"
  ],
  "exclusions": ["plant biology", "in silico only without validation"]
}
```

The agent reads this at the start of each session and tailors queries accordingly.

### 2. Bulk PubMed queries

Cast a wide net — metadata is free and fast:

```bash
# mechanism / direct topic
just run search_pubmed "TNF AND NF-kB AND single-cell" \
  --query-id mechanism_01 --query-name "TNF NF-kB single-cell" --max-results 200

# reviews
just run search_pubmed "macrophage polarization review" \
  --pub-types "Review,Systematic Review" \
  --query-id review_01 --query-name "Macrophage polarization reviews" --max-results 100

# methods
just run search_pubmed "single-cell NF-kB live-cell imaging" \
  --query-id methods_01 --query-name "Single-cell NF-kB methods" --max-results 100

# recent advances (last 3 years)
just run search_pubmed "transcriptional bursting macrophage" \
  --min-year 2023 \
  --query-id recent_01 --query-name "Recent bursting work" --max-results 100
```

Aim for 4–6 queries that hit the topic from different angles (mechanism, reviews, methods, recent, specific drugs/markers). Each `--query-id` tags the source query for later filtering.

### 3. Enrich with citations from Semantic Scholar

```bash
just run enrich_citations enrich
# optional: pull cite-neighbors of top-cited papers (citation-graph expansion)
just run enrich_citations expand --min-year 2020 --max-papers 100
```

This adds `citations`, `influentialCitationCount`, and `is_open_access` to each paper; `expand` follows citation trails from your top-cited results to find related work the keyword searches missed.

### 4. Fetch full text for the top-scored papers

Quality-score-ranked (journal tier × pub type × age-normalized citations) so the budget goes to the most-important papers:

```bash
just run fetch_fulltext --limit 100
```

Order of attempts per paper: PMC XML (OA, structured JATS) → Unpaywall OA URL → publisher HTML via `curl-impersonate` + trafilatura. Falls back to abstract-only if everything fails. `--dry-run` to preview, `--stats` to check what's been fetched.

### 5. Build the FTS5 index

```bash
just run index_fts
```

Idempotent. Re-run after every batch of new fetches.

### 6. Query the corpus

```bash
# FTS5 query
just run search "burst size single cell" --limit 10

# corpus stats
just run search --overview

# full text of one PMID
just run search --get 12345678

# get JSON for piping
just run search "TLR4 macrophage" --json | jq '.[].pmid'
```

FTS5 syntax: `AND` (default), `OR`, `NOT`, `"phrase search"`, `prefix*`, `title:term` (column-scoped).

Or write direct SQL:

```bash
sqlite3 data/lit-search.db "SELECT pmid, title, pub_year, citations \
  FROM papers WHERE pub_year >= 2022 ORDER BY quality_score DESC LIMIT 20;"
```

## Answering a question from the corpus

Every medical-style question through this skill follows the same pipeline:

1. **Decompose** the question into 3–5 searchable sub-topics.
2. **Search** with at least 3 different FTS5 queries (synonyms, alt angles).
3. **Read** the top 3–5 hits' full text via `just run search --get <PMID>`.
4. **Synthesize** an answer grounded only in what you read.
5. **Cite** every factual claim inline as `[PMID:12345678]`.
6. **Caveat** what the corpus doesn't cover and offer to expand.

### Response format

```
**[Question restated]**

Based on N papers in the corpus:

[Synthesis paragraph 1, with inline [PMID:…] citations]

[Synthesis paragraph 2…]

**Key papers:**
| PMID | Authors | Title (Year) | Relevance |
|---|---|---|---|
| [PMID:12345678] | Author et al. | "Title" (Year) | One-line summary |

**Limitations:** [what the corpus doesn't cover; biases]
```

## Expanding the corpus

If a question has insufficient evidence, say so honestly, then:

```bash
just run search_pubmed "<new targeted query>" \
  --query-id expand_01 --query-name "Description" --max-results 200
just run enrich_citations enrich --query-id expand_01
just run fetch_fulltext --limit 50
just run index_fts
```

Tell the user: "I've expanded the corpus with N new papers about [topic]. Let me search again."

## Failure modes the agent watches for

- **NCBI 429 rate-limit**: pause and back off; ensure `NCBI_API_KEY` is set if doing >3 req/s.
- **Empty PMC fetches**: paper may not be in PMC even if `pmc_id` is set; falls through to Unpaywall/HTML tier.
- **Trafilatura returning <2000 words**: usually a paywall page or a stub; script already skips these.
- **Truncated full text**: any paper with `[TRUNCATED — original was longer than limit]` was cut at 50k words. Note this in the synthesis if it matters.
- **Quality scores all zero**: enrichment didn't run; user should `just run enrich_citations enrich` before ranking.

## Checklist

- [ ] `data/lit-search.db` and `data/fulltext/` are in `.gitignore` (unless paper-replication archival)
- [ ] `data/context.json` reflects the actual research question
- [ ] `.env` with `NCBI_API_KEY` / `SEMANTIC_SCHOLAR_KEY` is gitignored
- [ ] At least 3 distinct FTS5 queries run before answering
- [ ] Every factual claim cited inline as `[PMID:…]`
- [ ] Limitations section explicitly names what the corpus doesn't cover

## Further reading

- [SQLite FTS5 docs](https://www.sqlite.org/fts5.html)
- [PubMed E-utilities](https://www.ncbi.nlm.nih.gov/books/NBK25500/) — request an API key at <https://www.ncbi.nlm.nih.gov/account/>
- [Semantic Scholar API](https://api.semanticscholar.org/api-docs/)
- [Unpaywall API](https://unpaywall.org/products/api)
- [trafilatura](https://trafilatura.readthedocs.io/) — HTML body extraction
- [`curl-impersonate`](https://github.com/lwthiker/curl-impersonate) — optional, for paywalled HTML; install via `brew install macports/macports/curl-impersonate`
- Source pattern this is adapted from: `kljensen/medical-issue-ai-discussion` (medical-research variant; this skill is the biology-tuned fork)
