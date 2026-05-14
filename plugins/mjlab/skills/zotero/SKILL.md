---
name: zotero
description: Use the Zotero local HTTP API (and Zotero Web API where needed) to search the user's reference library, add references by DOI, export BibTeX or CSL-formatted bibliographies, and manage collections and tags from within an analysis or manuscript repository. TRIGGER when the user mentions Zotero, citations, references, BibTeX, `.bib` files, DOIs in the context of citing a paper, or a manuscript draft asking for "the right paper for this claim."
related:
  - using-git-and-github
  - starting-a-new-project
  - bio-data-hygiene
updated: 2026-05-14
---
# Zotero

Zotero 7+ ships a **local HTTP API** at `http://localhost:23119/api/`. When Zotero is running on the user's machine, the agent can search the library, fetch metadata, and export formatted bibliographies with no install, no auth, and no MCP server. This skill is the agent's playbook for using it.

## Cardinal rules

- **Never hallucinate a citation.** If the agent is going to say "as shown in (Smith 2023)," it must first verify the reference exists in the user's Zotero library or on Crossref. Inventing a plausible-looking DOI is a science integrity failure.
- **Probe before assuming.** Always check the local API responds (HTTP 200 on `/api/`) before issuing read or write requests. If you get 403 "Local API is not enabled," tell the user the exact setting to flip rather than guessing or retrying.
- **Local API is read-only today.** Writes go through the Web API (with a key) or the connector endpoints. See "Adding references" below.
- **Citekeys are not built-in.** Stable citekeys like `bridges2024ccc` require the **Better BibTeX** plugin. If the user wants citekey-driven manuscripts and BBT isn't installed, recommend installing it once.

## Enabling the local API

Probe:

```bash
curl -sS -o /dev/null -w '%{http_code}\n' http://localhost:23119/api/
```

- **200** — Zotero is running and the local API is enabled. Proceed.
- **403 "Local API is not enabled"** — Zotero is running but the user hasn't enabled the API. Tell them: **Settings → Advanced → check "Allow other applications on this computer to communicate with Zotero."**
- **Connection refused** — Zotero isn't running. Ask the user to start it.

## Base URL and the `users/0` shortcut

The local API has the same URL grammar as the Web API. Locally, **`users/0` means "the current local user library"** — the agent does not need to know the real numeric userID. Group libraries use `groups/<id>/…`.

Base for all read examples below: `http://localhost:23119/api/users/0`

## Searching

Title + creator + year search (the default):

```bash
curl -sS 'http://localhost:23119/api/users/0/items?q=miller-jensen&limit=10'
```

Everything-search (includes indexed full-text of PDFs):

```bash
curl -sS 'http://localhost:23119/api/users/0/items?q=NF-kB+bursting&qmode=everything&limit=20'
```

Filter by type and tag:

```bash
# only journal articles tagged 'macrophage' OR 'TAM', NOT preprints
curl -sS 'http://localhost:23119/api/users/0/items?itemType=journalArticle&tag=macrophage%20%7C%7C%20TAM&tag=-preprint'
```

Tag boolean syntax is non-obvious:

- `&tag=A&tag=B` → A **AND** B
- `&tag=A%20%7C%7C%20B` (`A || B` URL-encoded) → A **OR** B
- `&tag=-A` → **NOT** A

Sort and paginate:

```bash
curl -sS 'http://localhost:23119/api/users/0/items?sort=dateAdded&direction=desc&limit=25&start=0'
```

Sort keys: `dateAdded`, `dateModified`, `title`, `creator`, `itemType`, `date`, `publicationTitle`. Default `limit` is 25, max 100.

## Getting one item with formatted output

Pass `include=` to receive multiple representations in a single response:

```bash
curl -sS 'http://localhost:23119/api/users/0/items/MHCQTYP2?include=data,bib,citation&style=cell'
```

This returns the item's raw `data` plus a `bib` field (Cell-style HTML bibliography) and a `citation` field (inline citation).

## Exporting formatted bibliographies

The `format` query parameter switches the response type.

BibTeX for a whole collection:

```bash
curl -sS 'http://localhost:23119/api/users/0/collections/ABCD1234/items?format=bibtex&limit=100' -o refs.bib
```

BibLaTeX (preferred over BibTeX for modern manuscripts):

```bash
curl -sS '…/items?format=biblatex' -o refs.bib
```

CSL-formatted bibliography for a specific set of items, in a specific journal's style:

```bash
curl -sS 'http://localhost:23119/api/users/0/items?itemKey=KEY1,KEY2,KEY3&format=bib&style=cell&locale=en-US'
```

Common lab journal styles (use the exact CSL slug):

- `cell`, `nature`, `science`, `the-lancet`
- `the-journal-of-immunology`, `nature-immunology`, `elife`
- `chicago-author-date` for fallback / non-journal docs

A list of all available styles: `https://www.zotero.org/styles-files/styles.json`. If the user names a journal not in `styles.json`, search there before failing.

Other useful formats: `csljson` (machine-readable bibliography for downstream tools), `ris`, `csv`.

## Listing collections and tags

```bash
# top-level collections
curl -sS 'http://localhost:23119/api/users/0/collections/top'

# sub-collections of a collection
curl -sS 'http://localhost:23119/api/users/0/collections/ABCD1234/collections'

# items in a collection
curl -sS 'http://localhost:23119/api/users/0/collections/ABCD1234/items?limit=100'

# all tags (with counts via numItems)
curl -sS 'http://localhost:23119/api/users/0/tags?limit=200'
```

## Adding references (writes)

Local API is currently **read-only**. Three paths to add items, in order of agent preference:

**1. Connector endpoint (against the running desktop app, no auth).** Best for adding a single item from a URL or DOI. Goes into the user's library immediately and is visible in Zotero's UI.

```bash
# uses Zotero's built-in translators
curl -sS -X POST 'http://localhost:23119/connector/saveItems' \
  -H 'Content-Type: application/json' \
  -d '{"items":[{"itemType":"journalArticle","title":"…","DOI":"10.1038/s41586-024-…","creators":[{"creatorType":"author","firstName":"Jane","lastName":"Doe"}],"date":"2024"}]}'
```

**2. Zotero Web API.** Required for batch writes or scripted manuscript pipelines. Needs an API key and the numeric userID.

```bash
export ZOTERO_API_KEY=zXXXXXXXXXX  # from https://www.zotero.org/settings/keys
export ZOTERO_USER_ID=1234567

curl -sS -X POST "https://api.zotero.org/users/${ZOTERO_USER_ID}/items" \
  -H "Zotero-API-Key: $ZOTERO_API_KEY" \
  -H "Content-Type: application/json" \
  -H "Zotero-Write-Token: $(openssl rand -hex 16)" \
  -d '[{"itemType":"journalArticle","title":"…","creators":[{"creatorType":"author","firstName":"Jane","lastName":"Doe"}],"DOI":"10.1000/xyz","date":"2024"}]'
```

Store secrets in a gitignored `.env`, never in committed code. See [using-git-and-github](../using-git-and-github/SKILL.md).

**3. Translation-server** (optional, separate Node service on `:1969`). The only path that resolves a bare DOI/PMID/arXiv ID into full Zotero JSON without going through Zotero's own UI. Most labs don't run it; mention as an option, don't assume.

## Adding by DOI (the common case)

If the user says "add 10.1038/s41586-024-12345 to my library":

1. Check connector endpoint reachability.
2. POST the DOI to `/connector/saveItems` with `itemType: 'journalArticle'` and minimal fields; Zotero's translators fill in the rest from Crossref.
3. Confirm in the response that the item key was returned.
4. If the user wants it in a specific collection, PATCH the item's `collections` array via the Web API.

## Item types and key fields

The most common items in a biology lab repo:

- **journalArticle**: `title`, `creators[]` (each `{creatorType, firstName, lastName}`), `publicationTitle`, `volume`, `issue`, `pages`, `date`, `DOI`, `ISSN`, `URL`, `abstractNote`
- **preprint**: `title`, `creators[]`, `repository` (e.g. "bioRxiv"), `archiveID` (e.g. "2024.01.15.575912"), `date`, `DOI`, `URL`
- **book**: + `publisher`, `place`, `ISBN`, `numPages`
- **bookSection**: + `bookTitle`, `bookAuthor`, `pages`
- **thesis**: `thesisType`, `university`, `place`, `date`

Get a fresh template for any type: `GET /api/items/new?itemType=preprint`.

## Better BibTeX (optional)

If installed, BBT exposes JSON-RPC at `http://localhost:23119/better-bibtex/json-rpc`:

```bash
# get the stable citekey for an item
curl -sS -X POST http://localhost:23119/better-bibtex/json-rpc \
  -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","method":"item.citationkey","params":[["MHCQTYP2"]]}'
```

Probe: `POST` with `method: "api.ready"`. A `"No endpoint found"` response means BBT is not installed — fall back to core Zotero output (which still includes a BibTeX-flavored `id` field on `?format=bibtex` exports, just not BBT's stable format).

## Manuscript workflow

When the agent is editing a manuscript in a lab repo:

1. Cite by **citekey** (`@bridges2024ccc`) if BBT is installed, otherwise by **Zotero itemKey** (which is stable per-library but not human-readable).
2. Keep the canonical `.bib` at `manuscript/refs.bib`. Regenerate on demand:
   ```bash
   curl -sS 'http://localhost:23119/api/users/0/collections/ABCD1234/items?format=biblatex&limit=100' \
     > manuscript/refs.bib
   ```
3. Track `refs.bib` in git. The user's Zotero library is the source of truth; the `.bib` is a snapshot.
4. Before submitting, the agent verifies every `\cite{…}` in the manuscript resolves to an entry in `refs.bib`.

## Failure modes the agent watches for

- **Empty bibliography output**: `format=bib` or `format=bibtex` returns nothing → the queried items are attachments or notes, not reference items. Filter with `/items/top` or an explicit `itemKey=` list of parent items.
- **Tag URL encoding**: spaces and `||` in tag queries must be URL-encoded.
- **`Last-Modified-Version` conflicts on writes**: include `If-Unmodified-Since-Version: <n>` to avoid clobbering changes the user made in the UI.
- **Rate limits on Web API**: respect `Backoff: <s>` and `429 Retry-After: <s>` headers. The local API has no rate limit but be polite.
- **Group libraries**: `/api/users/0/…` only sees the user's personal library. For a lab group library that's been synced to the desktop, use `/api/groups/<groupID>/…`.

## Checklist

- [ ] Probed `localhost:23119/api/` for 200 before any request
- [ ] Used `users/0` (not a hard-coded numeric ID) for local reads
- [ ] Verified each cited DOI exists in Zotero or on Crossref before adding to a manuscript
- [ ] Wrote any API keys to a gitignored `.env`, never to a committed file
- [ ] Regenerated `manuscript/refs.bib` after adding new references and committed the result

## Further reading

- [Zotero Web API v3 basics](https://www.zotero.org/support/dev/web_api/v3/basics)
- [Zotero local HTTP server](https://www.zotero.org/support/dev/client_coding/connector_http_server)
- [Types and fields](https://www.zotero.org/support/dev/web_api/v3/types_and_fields)
- [Write requests + concurrency](https://www.zotero.org/support/dev/web_api/v3/write_requests)
- [Item schema (machine-readable)](https://api.zotero.org/schema)
- [CSL style index](https://www.zotero.org/styles-files/styles.json)
- [Better BibTeX JSON-RPC](https://retorque.re/zotero-better-bibtex/exporting/json-rpc/)
- [`pyzotero`](https://github.com/urschrei/pyzotero) — Python client if shell `curl` gets unwieldy
- Community MCP server: [`54yyyu/zotero-mcp`](https://github.com/54yyyu/zotero-mcp) — install if the user prefers MCP tools over shell calls
