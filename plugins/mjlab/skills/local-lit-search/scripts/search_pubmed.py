#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "biopython>=1.84",
#     "click>=8.1",
# ]
# ///
"""Search PubMed via E-utilities API and save results to SQLite.

Run directly:  ./scripts/search_pubmed.py "pancreatic cancer FOLFIRINOX" --max-results 10
Via justfile:  just run search_pubmed "pancreatic cancer" --max-results 10
"""

import json
import logging
import os
import re
import sqlite3
import sys
import time
import urllib.error
import uuid
from pathlib import Path
from typing import Any

import click
from Bio import Entrez

# Import shared quality scoring (sibling module)
sys.path.insert(0, str(Path(__file__).parent))
from quality import compute_quality_score  # noqa: E402

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

DATA_DIR = Path(os.environ.get("LIT_SEARCH_DATA_DIR", "data")).resolve()
DB_PATH = DATA_DIR / "lit-search.db"

# ---------------------------------------------------------------------------
# Logging — all diagnostics to stderr so --json stdout stays clean
# ---------------------------------------------------------------------------

logging.basicConfig(
    stream=sys.stderr,
    level=logging.INFO,
    format="%(levelname)s: %(message)s",
)
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Entrez setup
# ---------------------------------------------------------------------------

Entrez.email = "research-tool@example.com"
_api_key = os.environ.get("NCBI_API_KEY", "")
if _api_key:
    Entrez.api_key = _api_key

# Biopython writes DTD/XSD files to a local cache directory.  If the default
# path (~/.config/biopython/Bio/Entrez/DTDs) exists as a *file* rather than a
# directory, makedirs raises FileExistsError.  Redirect to a safe tmp dir.
_entrez_cache = Path(os.environ.get("BIOPYTHON_CACHE", "/tmp/biopython_entrez_cache"))
_entrez_cache.mkdir(parents=True, exist_ok=True)
Entrez.local_cache = str(_entrez_cache)

# ---------------------------------------------------------------------------
# Network helpers
# ---------------------------------------------------------------------------


def _entrez_call(fn: Any, *args: Any, **kwargs: Any) -> Any:
    """Call an Entrez function, retrying once on network/HTTP errors.

    Returns the raw handle — caller must still read it.
    """
    for attempt in range(2):
        try:
            return fn(*args, **kwargs)
        except (urllib.error.HTTPError, urllib.error.URLError, RuntimeError) as exc:
            if attempt == 0:
                log.warning("Entrez call failed (%s), retrying in 2s…", exc)
                time.sleep(2)
            else:
                raise


def _entrez_fetch_and_read(fn: Any, *args: Any, **kwargs: Any) -> Any:
    """Call an Entrez function and read the response, retrying once on failure.

    Wraps both the HTTP request and Entrez.read() in the retry loop so that
    transient failures during response download/XML parsing are also retried.
    """
    for attempt in range(2):
        try:
            handle = fn(*args, **kwargs)
            result = Entrez.read(handle)
            handle.close()
            return result
        except (urllib.error.HTTPError, urllib.error.URLError, RuntimeError) as exc:
            if attempt == 0:
                log.warning("Entrez call failed (%s), retrying in 2s…", exc)
                time.sleep(2)
            else:
                raise


# ---------------------------------------------------------------------------
# Query construction
# ---------------------------------------------------------------------------


def _build_query(
    query: str,
    pub_types: list[str],
    min_year: int | None,
) -> str:
    """Return the full PubMed query string."""
    parts = [query]
    if pub_types:
        pt_clause = " OR ".join(f'"{pt}"[pt]' for pt in pub_types)
        parts.append(f"({pt_clause})")
    if min_year is not None:
        parts.append(f'"{min_year}"[dp] : "3000"[dp]')
    return " AND ".join(parts)


# ---------------------------------------------------------------------------
# XML / Biopython record parsing
# ---------------------------------------------------------------------------


def _extract_abstract(article: dict) -> str:
    """Join structured abstract parts (with Labels) into a single string."""
    raw = article.get("Abstract", {}).get("AbstractText", [])
    if not raw:
        return ""
    chunks: list[str] = []
    for part in raw:
        text = str(part)
        label = getattr(part, "attributes", {}).get("Label", "")
        chunks.append(f"{label}: {text}" if label else text)
    return " ".join(chunks)


def _extract_year(pub_date: dict, article_dates: list[dict]) -> int | None:
    """Year fallback chain: PubDate.Year → MedlineDate regex → ArticleDate."""
    if "Year" in pub_date:
        try:
            return int(pub_date["Year"])
        except (ValueError, TypeError):
            pass
    if "MedlineDate" in pub_date:
        m = re.search(r"\d{4}", str(pub_date["MedlineDate"]))
        if m:
            return int(m.group())
    for ad in article_dates:
        if "Year" in ad:
            try:
                return int(ad["Year"])
            except (ValueError, TypeError):
                pass
    return None


def _extract_authors(author_list: list[dict]) -> list[str]:
    """Parse author dicts, handling CollectiveName entries."""
    authors: list[str] = []
    for author in author_list:
        if "CollectiveName" in author:
            authors.append(str(author["CollectiveName"]))
        else:
            last = str(author.get("LastName", ""))
            fore = str(author.get("ForeName", author.get("Initials", "")))
            name = f"{last} {fore}".strip()
            if name:
                authors.append(name)
    return authors


def _parse_record(medline_citation: dict, pubmed_data: dict) -> dict:
    """Parse one MedlineCitation + PubmedData dict into a flat paper dict."""
    article = medline_citation.get("Article", {})

    # Basic metadata
    title = str(article.get("ArticleTitle", "")).strip()
    abstract = _extract_abstract(article)
    journal = str(article.get("Journal", {}).get("Title", "")).strip()

    # Authors
    raw_authors = article.get("AuthorList", [])
    if isinstance(raw_authors, dict):
        raw_authors = list(raw_authors.values())[0] if raw_authors else []
    authors = _extract_authors(raw_authors)

    # Year
    journal_issue = article.get("Journal", {}).get("JournalIssue", {})
    pub_date = journal_issue.get("PubDate", {})
    article_dates = article.get("ArticleDate", [])
    if isinstance(article_dates, dict):
        article_dates = [article_dates]
    pub_year = _extract_year(pub_date, article_dates)

    # Publication types
    pt_list = article.get("PublicationTypeList", [])
    pub_types = [str(pt) for pt in pt_list]

    # IDs from PubmedData.ArticleIdList
    pmid = str(medline_citation.get("PMID", ""))
    doi = ""
    pmc_id = ""
    for aid in pubmed_data.get("ArticleIdList", []):
        id_type = getattr(aid, "attributes", {}).get("IdType", "")
        val = str(aid)
        if id_type == "pubmed" and not pmid:
            pmid = val
        elif id_type == "doi":
            doi = val
        elif id_type == "pmc":
            pmc_id = val

    # Computed quality fields
    is_open_access = 1 if pmc_id else 0
    pub_types_json = json.dumps(pub_types)
    quality_score = compute_quality_score(
        is_open_access=is_open_access,
        has_pmc=bool(pmc_id),
        has_abstract=bool(abstract),
        journal=journal,
        pub_types_json=pub_types_json,
        pub_year=pub_year,
    )

    return {
        "pmid": pmid,
        "doi": doi or None,
        "pmc_id": pmc_id or None,
        "title": title,
        "abstract": abstract or None,
        "authors": json.dumps(authors),
        "journal": journal or None,
        "pub_year": pub_year,
        "pub_types": pub_types_json,
        "is_open_access": is_open_access,
        "quality_score": quality_score,
    }


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------


def _save_query(
    conn: sqlite3.Connection,
    query_id: str,
    name: str,
    query_text: str,
    max_results: int,
) -> None:
    conn.execute(
        "INSERT OR REPLACE INTO queries (id, name, query, max_results) VALUES (?, ?, ?, ?)",
        (query_id, name, query_text, max_results),
    )


def _save_paper(
    conn: sqlite3.Connection,
    paper: dict,
    query_id: str,
) -> bool:
    """Insert paper; return True if new, False if duplicate (INSERT OR IGNORE)."""
    cur = conn.execute(
        """INSERT OR IGNORE INTO papers
           (pmid, doi, pmc_id, title, abstract, authors, journal, pub_year,
            pub_types, is_open_access, quality_score, query_id, source)
           VALUES (:pmid, :doi, :pmc_id, :title, :abstract, :authors, :journal,
                   :pub_year, :pub_types, :is_open_access, :quality_score,
                   :query_id, 'pubmed')""",
        {**paper, "query_id": query_id},
    )
    is_new: bool = cur.rowcount > 0
    if is_new:
        conn.execute(
            """INSERT INTO papers_fts(pmid, title, abstract, full_text, authors, journal)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                paper["pmid"],
                paper["title"],
                paper["abstract"] or "",
                "",  # full_text populated by a later script
                paper["authors"],
                paper["journal"] or "",
            ),
        )
    return is_new


# ---------------------------------------------------------------------------
# Core search
# ---------------------------------------------------------------------------


def search_pubmed(
    query: str,
    pub_types: list[str],
    min_year: int | None,
    max_results: int,
) -> list[dict]:
    """Run esearch + efetch; return list of parsed paper dicts."""
    full_query = _build_query(query, pub_types, min_year)
    log.info("PubMed query: %s", full_query)

    # esearch — use history server for large result sets
    search_results = _entrez_fetch_and_read(
        Entrez.esearch,
        db="pubmed",
        term=full_query,
        retmax=max_results,
        usehistory="y",
    )

    total_count = int(search_results.get("Count", 0))
    web_env = search_results.get("WebEnv", "")
    query_key = search_results.get("QueryKey", "")
    log.info("PubMed reports %d total matches; fetching up to %d", total_count, max_results)

    if total_count == 0 or not web_env:
        return []

    # efetch in batches of 200
    batch_size = 200
    to_fetch = min(total_count, max_results)
    papers: list[dict] = []

    for start in range(0, to_fetch, batch_size):
        retmax = min(batch_size, to_fetch - start)
        log.info("  efetch records %d–%d…", start + 1, start + retmax)
        try:
            records = _entrez_fetch_and_read(
                Entrez.efetch,
                db="pubmed",
                rettype="xml",
                retmode="xml",
                retstart=start,
                retmax=retmax,
                webenv=web_env,
                query_key=query_key,
            )
        except Exception as exc:
            log.warning("efetch batch (start=%d) failed: %s — skipping batch", start, exc)
            continue

        for record in records.get("PubmedArticle", []):
            try:
                medline = record["MedlineCitation"]
                pubmed_data = record.get("PubmedData", {})
                paper = _parse_record(medline, pubmed_data)
                if paper["pmid"]:
                    papers.append(paper)
            except Exception as exc:
                log.warning("Failed to parse record: %s", exc)

    return papers


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


@click.command()
@click.argument("query")
@click.option(
    "--max-results",
    default=200,
    show_default=True,
    help="Maximum number of papers to fetch (metadata only — cheap).",
)
@click.option(
    "--pub-types",
    default="",
    help="Comma-separated publication types, e.g. 'Practice Guideline,Systematic Review'.",
)
@click.option(
    "--min-year",
    default=None,
    type=int,
    help="Restrict results to papers published on or after this year.",
)
@click.option(
    "--query-id",
    default=None,
    help="Identifier for this query (auto-generated if omitted).",
)
@click.option(
    "--query-name",
    default=None,
    help="Human-readable label for this query.",
)
@click.option(
    "--json",
    "output_json",
    is_flag=True,
    help="Emit JSON to stdout (diagnostics go to stderr).",
)
def main(
    query: str,
    max_results: int,
    pub_types: str,
    min_year: int | None,
    query_id: str | None,
    query_name: str | None,
    output_json: bool,
) -> None:
    """Search PubMed and save results to the research database."""
    # Auto-generate query_id / query_name if not supplied
    if not query_id:
        slug = re.sub(r"[^a-z0-9]+", "_", query.lower())[:40].strip("_")
        query_id = f"{slug}_{uuid.uuid4().hex[:6]}"
    if not query_name:
        query_name = query[:80]

    pub_type_list = [pt.strip() for pt in pub_types.split(",") if pt.strip()]

    # Sanity-check DB existence early
    if not DB_PATH.exists():
        click.echo(
            f"Error: database not found at {DB_PATH}. Run `just setup` first.",
            err=True,
        )
        sys.exit(1)

    papers = search_pubmed(
        query=query,
        pub_types=pub_type_list,
        min_year=min_year,
        max_results=max_results,
    )

    new_count = 0
    dup_count = 0
    with sqlite3.connect(DB_PATH) as conn:
        _save_query(conn, query_id, query_name, query, max_results)
        for paper in papers:
            if _save_paper(conn, paper, query_id):
                new_count += 1
            else:
                dup_count += 1
        # conn.__exit__ commits automatically

    log.info(
        "Done — fetched: %d, new: %d, duplicates skipped: %d",
        len(papers),
        new_count,
        dup_count,
    )

    if output_json:
        json.dump(
            {
                "papers": papers,
                "total_found": len(papers),
                "new": new_count,
                "duplicates": dup_count,
            },
            sys.stdout,
            indent=2,
        )
        sys.stdout.write("\n")
    else:
        click.echo(
            f"✓  {new_count} new papers saved, {dup_count} duplicates skipped"
            f" (total fetched: {len(papers)})"
        )


if __name__ == "__main__":
    main()
