---
name: literature-search
description: Search the scientific literature for the Miller-Jensen lab using public REST APIs (PubMed/OpenAlex/Crossref/Europe PMC/bioRxiv/Semantic Scholar/arXiv/Unpaywall) and optionally Ai2 Asta. TRIGGER when the user asks to find papers on a topic, do a quick literature lookup, locate a DOI or PMID, get the latest preprints, or ground a claim in real published work. For a reproducible local corpus snapshot, see [local-lit-search](../local-lit-search/SKILL.md).
related:
  - local-lit-search
  - zotero
  - using-git-and-github
  - bio-data-hygiene
updated: 2026-05-14
---
# Literature search

Live-oracle mode for the Miller-Jensen lab: ask public APIs (or Asta) for fresh results. For a reproducible local SQLite FTS5 corpus that pins answers across sessions — e.g., for a manuscript intro or paper-replication repo — use the sibling skill [local-lit-search](../local-lit-search/SKILL.md).

## Cardinal rules

- **Never invent a citation.** A plausible-looking DOI or PMID that you have not verified is a science integrity failure. Resolve every cited identifier against a public API before quoting it.
- **Public APIs are polite-by-email.** Crossref, OpenAlex, and Unpaywall all promote you to a faster "polite pool" if you include a `mailto=user@example.com` query param or User-Agent. Do this; rate-limited 429s waste real time.
- **PubMed wants an NCBI API key** if you're going to make >3 requests/sec. Store it in a gitignored `.env` (`NCBI_API_KEY=…`) and pass to the shipped scripts as needed.
- **Agentic services hallucinate.** Asta and similar synthesizers occasionally return real-looking citations that don't exist or that don't support the claim. Verify every Asta-returned identifier against PubMed/Crossref before relying on it.
- **Prefer REST over installing more MCP servers.** The agent calls REST with `curl` or `httpx`; MCP is a convenience layer the lab member shouldn't have to install unless they ask.

## Public REST APIs — copy-paste examples

All free, no key needed (except where noted). Include your email in `mailto=` when offered.

### PubMed (NCBI E-utilities)

```bash
# search → returns PMIDs
curl -sS 'https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db=pubmed&term=TLR4+macrophage+single+cell&retmode=json&retmax=20'

# fetch metadata for a PMID
curl -sS 'https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi?db=pubmed&id=38000001,38000002&retmode=json'

# fetch full abstract (XML, slower)
curl -sS 'https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=pubmed&id=38000001&retmode=xml&rettype=abstract'
```

For >3 req/s, add `&api_key=$NCBI_API_KEY`. PubMed-specific filters: `[ti]` (title), `[au]` (author), `[pt]` (pub type), `[mh]` (MeSH), `[dp]` (date), `2020:2026[dp]` (date range).

### OpenAlex

Free, no key. Best general-purpose academic graph (~250M works).

```bash
# search papers
curl -sS 'https://api.openalex.org/works?search=NF-kB+bursting+single+cell&per-page=25&mailto=user@example.com'

# get one work by DOI
curl -sS 'https://api.openalex.org/works/doi:10.1038/s41586-024-12345'

# authors and their works
curl -sS 'https://api.openalex.org/authors?search=Miller-Jensen+Kathryn&mailto=user@example.com'

# citations of a work (incoming) — use the openalex ID
curl -sS 'https://api.openalex.org/works?filter=cites:W2741809807&per-page=25&mailto=user@example.com'
```

### Crossref

Free; metadata for almost all DOIs.

```bash
# search by query
curl -sS 'https://api.crossref.org/works?query=TNF+bursting+macrophage&rows=25&mailto=user@example.com'

# resolve a DOI to metadata
curl -sS 'https://api.crossref.org/works/10.1038/s41586-024-12345'
```

### Europe PMC

Search PubMed + PMC full-text with one call; returns abstracts and OA PDF URLs.

```bash
curl -sS 'https://www.ebi.ac.uk/europepmc/webservices/rest/search?query=macrophage+polarization+single-cell&format=json&resultType=core&pageSize=25'
```

### bioRxiv / medRxiv

Preprints. No search endpoint — you fetch by DOI or by date range, then filter client-side.

```bash
# get metadata for one preprint
curl -sS 'https://api.biorxiv.org/details/biorxiv/10.1101/2024.01.15.575912'

# recent papers in a date window
curl -sS 'https://api.biorxiv.org/details/biorxiv/2026-04-01/2026-05-01/0'
```

For substantive search of preprints, **use Europe PMC** above with `&src=PPR` filter, or OpenAlex with `&filter=type:preprint`.

### Semantic Scholar

Free with rate limits; request a key at <https://www.semanticscholar.org/product/api> for higher throughput.

```bash
# search
curl -sS 'https://api.semanticscholar.org/graph/v1/paper/search?query=transcriptional+bursting&limit=20&fields=title,authors,year,citationCount,influentialCitationCount,abstract,externalIds'

# get one paper + its references and citing papers
curl -sS 'https://api.semanticscholar.org/graph/v1/paper/DOI:10.1038/s41586-024-12345?fields=title,abstract,references,citations,influentialCitationCount'
```

The `influentialCitationCount` field is unique to Semantic Scholar — it flags citations that contextually matter, not just every mention.

### arXiv

```bash
# Atom-XML response
curl -sS 'http://export.arxiv.org/api/query?search_query=all:single-cell+RNA-seq+macrophage&start=0&max_results=20'
```

### Unpaywall — OA PDF discovery

Free with email. Resolves a DOI to an open-access PDF URL if one exists.

```bash
curl -sS "https://api.unpaywall.org/v2/10.1038/s41586-024-12345?email=user@example.com"
```

Use this when the user wants a paper they don't have institutional access to. The response's `best_oa_location.url_for_pdf` is what you fetch.

## Ai2 Asta — agentic synthesis (optional)

Asta is the Allen Institute's free agentic literature service over 200M+ papers. It plans multi-step searches, follows citations, and returns synthesized answers with grounded citations.

Two integration paths. The agent should **default to the REST API**. On first use of Asta in a session, ask the user once: *"Asta also ships an MCP server — would you like to install it for richer tool integration, or keep using the REST API?"* Honor whatever they say and don't re-ask.

**REST**:

```bash
# Scientific Corpus Tool — hybrid (sparse + dense) full-text search
curl -sS -X POST 'https://api.allenai.org/v1/asta/search' \
  -H 'Content-Type: application/json' \
  -d '{"query":"TNF transcriptional bursting macrophage","retrieval":"hybrid","limit":20}'
```

(Endpoint subject to change — see <https://allenai.org/asta/resources/mcp> for current shapes.)

**MCP** (if user opted in):

```bash
# install the MCP server (one-time)
uv tool install asta-mcp
# then add to claude code's MCP config — see https://allenai.org/asta/resources/mcp
```

After install, Asta's tools (`asta_search`, `asta_synthesize`, etc.) appear natively in the agent's tool list. Use them like any other tool.

**Verification rule**: Asta's returned citations are *usually* real but sometimes fabricated or mis-attributed. Before quoting an Asta-returned PMID/DOI in a manuscript or analysis, resolve it via Crossref or PubMed (`esummary.fcgi?db=pubmed&id=…`) and confirm title + authors match.

## When to use which API

| Situation | Endpoint |
|---|---|
| "What's the latest on X?" exploratory | Asta, or PubMed `esearch.fcgi?sort=date` |
| Single citation lookup ("get the DOI for Bridges 2024 macrophage paper") | Crossref or OpenAlex |
| Find an OA PDF for a known DOI | Unpaywall |
| "Who has cited this paper?" | Semantic Scholar or OpenAlex `cites:` filter |
| "What does this paper actually say?" | Europe PMC full-text endpoint |
| Daily preprint surveillance | bioRxiv API, polled |
| Reproducible literature snapshot for a manuscript or paper-replication repo | Switch to [local-lit-search](../local-lit-search/SKILL.md) |

## Checklist

- [ ] Polite-pool email included on Crossref / OpenAlex / Unpaywall calls
- [ ] No PMID/DOI quoted in user output without verification against a public API
- [ ] `.env` with NCBI / Semantic Scholar keys is gitignored
- [ ] Asta-returned citations sanity-checked against PubMed/Crossref before quoting

## Further reading

- [PubMed E-utilities](https://www.ncbi.nlm.nih.gov/books/NBK25500/)
- [OpenAlex API docs](https://docs.openalex.org/)
- [Crossref REST API](https://api.crossref.org/swagger-ui/index.html)
- [Europe PMC web services](https://europepmc.org/RestfulWebService)
- [bioRxiv API](https://api.biorxiv.org/)
- [Semantic Scholar API](https://api.semanticscholar.org/api-docs/)
- [arXiv API user manual](https://info.arxiv.org/help/api/user-manual.html)
- [Unpaywall API](https://unpaywall.org/products/api)
- [Ai2 Asta](https://allenai.org/asta) · [Asta MCP](https://allenai.org/asta/resources/mcp)
- [FutureHouse PaperQA2 (open-source)](https://github.com/Future-House/paper-qa) — if the user wants a local agentic Q&A instead of Asta
