#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "click>=8.1",
#     "httpx>=0.27",
# ]
# ///
"""Enrich papers with citation data from Semantic Scholar.

Run directly:  ./scripts/enrich_citations.py enrich
               ./scripts/enrich_citations.py enrich --query-id "review_01" --limit 50
               ./scripts/enrich_citations.py expand --min-year 2020 --max-papers 500 --top-seeds 20
               ./scripts/enrich_citations.py stats
Via justfile:  just run enrich_citations enrich --limit 50
"""

import json
import logging
import os
import random
import sqlite3
import sys
import time
from pathlib import Path
from typing import Any

import click
import httpx

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

DATA_DIR = Path(os.environ.get("LIT_SEARCH_DATA_DIR", "data")).resolve()
DB_PATH = DATA_DIR / "lit-search.db"

# ---------------------------------------------------------------------------
# Logging — all diagnostics to stderr so stdout stays clean
# ---------------------------------------------------------------------------

logging.basicConfig(
    stream=sys.stderr,
    level=logging.INFO,
    format="%(levelname)s: %(message)s",
)
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Semantic Scholar API constants
# ---------------------------------------------------------------------------

S2_BASE = "https://api.semanticscholar.org/graph/v1"
S2_API_KEY = os.environ.get("SEMANTIC_SCHOLAR_API_KEY", "")

# Rate limits: 1 req/s without key, 10 req/s with key
_REQ_INTERVAL = 0.1 if S2_API_KEY else 1.0
_BATCH_SIZE = 500

_FIELDS_BATCH = "citationCount,influentialCitationCount,isOpenAccess,externalIds"
_FIELDS_CITATIONS = (
    "citationCount,influentialCitationCount,isOpenAccess,"
    "externalIds,title,abstract,authors,year,journal,corpusId"
)

# ---------------------------------------------------------------------------
# HTTP client
# ---------------------------------------------------------------------------


def _make_client() -> httpx.Client:
    headers: dict[str, str] = {"Accept": "application/json"}
    if S2_API_KEY:
        headers["x-api-key"] = S2_API_KEY
    return httpx.Client(headers=headers, timeout=30.0)


def _get_with_retry(
    client: httpx.Client,
    url: str,
    params: dict[str, Any] | None = None,
    max_retries: int = 5,
) -> dict | None:
    """GET with exponential backoff + jitter on 429; honor Retry-After."""
    for attempt in range(max_retries):
        try:
            resp = client.get(url, params=params)
            if resp.status_code == 200:
                return resp.json()
            if resp.status_code == 429:
                retry_after = resp.headers.get("Retry-After")
                sleep_time = float(retry_after) if retry_after else (2**attempt) + random.uniform(0, 1)
                log.warning(
                    "429 rate limit — sleeping %.1fs (attempt %d/%d)",
                    sleep_time,
                    attempt + 1,
                    max_retries,
                )
                time.sleep(sleep_time)
                continue
            if resp.status_code == 404:
                log.debug("404 for %s", url)
                return None
            log.warning("HTTP %d for GET %s", resp.status_code, url)
            if attempt < max_retries - 1:
                time.sleep(2**attempt)
        except (httpx.TimeoutException, httpx.NetworkError) as exc:
            log.warning("Network error (%s), retry %d/%d", exc, attempt + 1, max_retries)
            if attempt < max_retries - 1:
                time.sleep(2**attempt)
    return None


def _post_with_retry(
    client: httpx.Client,
    url: str,
    json_body: dict,
    params: dict[str, Any] | None = None,
    max_retries: int = 5,
) -> list | None:
    """POST with exponential backoff + jitter on 429; honor Retry-After."""
    for attempt in range(max_retries):
        try:
            resp = client.post(url, json=json_body, params=params)
            if resp.status_code == 200:
                return resp.json()
            if resp.status_code == 429:
                retry_after = resp.headers.get("Retry-After")
                sleep_time = float(retry_after) if retry_after else (2**attempt) + random.uniform(0, 1)
                log.warning(
                    "429 rate limit — sleeping %.1fs (attempt %d/%d)",
                    sleep_time,
                    attempt + 1,
                    max_retries,
                )
                time.sleep(sleep_time)
                continue
            log.warning("HTTP %d for POST %s", resp.status_code, url)
            if attempt < max_retries - 1:
                time.sleep(2**attempt)
        except (httpx.TimeoutException, httpx.NetworkError) as exc:
            log.warning("Network error (%s), retry %d/%d", exc, attempt + 1, max_retries)
            if attempt < max_retries - 1:
                time.sleep(2**attempt)
    return None


# ---------------------------------------------------------------------------
# Quality score — use shared module
# ---------------------------------------------------------------------------

sys.path.insert(0, str(Path(__file__).parent))
from quality import compute_quality_score  # noqa: E402


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------


def _check_db() -> None:
    """Exit with error if the database does not exist."""
    if not DB_PATH.exists():
        click.echo(
            f"Error: database not found at {DB_PATH}. Run `just setup` first.",
            err=True,
        )
        sys.exit(1)


def _get_papers_to_enrich(
    conn: sqlite3.Connection,
    query_id: str | None,
    limit: int | None,
) -> list[dict]:
    """Return papers not yet enriched by Semantic Scholar.

    We distinguish unenriched papers from genuinely-zero-citation papers
    using the `influential_citations` column as a sentinel:
      - Unenriched papers: influential_citations = 0 (the DEFAULT)
      - Enriched papers: influential_citations set to the S2 value, OR -1
        if S2 returned 0 for both citations and influential_citations.
    This avoids infinite re-enrichment without schema changes.
    """
    sql = """
        SELECT pmid, doi, pmc_id, abstract, journal, pub_types, pub_year
        FROM papers
        WHERE pmid IS NOT NULL
          AND influential_citations = 0
          AND citations = 0
    """
    params: list[Any] = []
    if query_id:
        sql += " AND query_id = ?"
        params.append(query_id)
    if limit:
        sql += " LIMIT ?"
        params.append(limit)
    rows = conn.execute(sql, params).fetchall()
    return [
        {"pmid": r[0], "doi": r[1], "pmc_id": r[2], "abstract": r[3],
         "journal": r[4], "pub_types": r[5], "pub_year": r[6]}
        for r in rows
    ]


def _update_paper_citations(
    conn: sqlite3.Connection,
    pmid: str,
    s2_data: dict,
    pmc_id: str | None,
    abstract: str | None,
    journal: str | None = None,
    pub_types_json: str | None = None,
    pub_year: int | None = None,
) -> None:
    """Overwrite citation fields and recompute quality score from scratch.

    When S2 returns 0 for both citations and influential_citations, we store
    influential_citations = -1 as a sentinel so the paper is not re-queried
    on the next `enrich` run (see _get_papers_to_enrich).
    """
    citations = s2_data.get("citationCount") or 0
    influential = s2_data.get("influentialCitationCount") or 0
    is_oa = 1 if s2_data.get("isOpenAccess") else 0

    # Sentinel: mark enriched-but-zero papers so they're not re-queried
    stored_influential = influential if (citations > 0 or influential > 0) else -1

    quality_score = compute_quality_score(
        citations=citations,
        influential_citations=influential,
        is_open_access=is_oa,
        has_pmc=bool(pmc_id),
        has_abstract=bool(abstract),
        journal=journal,
        pub_types_json=pub_types_json,
        pub_year=pub_year,
    )
    conn.execute(
        """UPDATE papers
           SET citations = ?,
               influential_citations = ?,
               is_open_access = ?,
               quality_score = ?
           WHERE pmid = ?""",
        (citations, stored_influential, is_oa, quality_score, pmid),
    )


# ---------------------------------------------------------------------------
# Enrich logic
# ---------------------------------------------------------------------------


def _enrich_papers(
    client: httpx.Client,
    papers: list[dict],
    conn: sqlite3.Connection,
) -> int:
    """Batch-enrich papers via POST /graph/v1/paper/batch. Returns count enriched."""
    enriched = 0
    pmids = [p["pmid"] for p in papers if p["pmid"]]
    pmc_map = {p["pmid"]: p["pmc_id"] for p in papers}
    abstract_map = {p["pmid"]: p["abstract"] for p in papers}
    journal_map = {p["pmid"]: p.get("journal") for p in papers}
    pub_types_map = {p["pmid"]: p.get("pub_types") for p in papers}
    pub_year_map = {p["pmid"]: p.get("pub_year") for p in papers}

    for i in range(0, len(pmids), _BATCH_SIZE):
        chunk = pmids[i : i + _BATCH_SIZE]
        # Map DB keys to Semantic Scholar identifiers:
        #   Real PMIDs → "PMID:12345678"
        #   Synthetic S2:{corpusId} keys → "CorpusId:{corpusId}"
        ids = []
        for pmid in chunk:
            if pmid.startswith("S2:"):
                ids.append(f"CorpusId:{pmid[3:]}")
            else:
                ids.append(f"PMID:{pmid}")

        log.info("Batch enriching %d papers (offset %d)…", len(chunk), i)

        result = _post_with_retry(
            client,
            f"{S2_BASE}/paper/batch",
            json_body={"ids": ids},
            params={"fields": _FIELDS_BATCH},
        )
        time.sleep(_REQ_INTERVAL)

        if result is None:
            log.warning("Batch API returned no data for chunk at offset %d", i)
            continue

        for idx, paper_data in enumerate(result):
            # Semantic Scholar returns null for unrecognized PMIDs — skip them
            if paper_data is None:
                continue
            pmid = chunk[idx]
            _update_paper_citations(
                conn,
                pmid,
                paper_data,
                pmc_id=pmc_map.get(pmid),
                abstract=abstract_map.get(pmid),
                journal=journal_map.get(pmid),
                pub_types_json=pub_types_map.get(pmid),
                pub_year=pub_year_map.get(pmid),
            )
            enriched += 1

    return enriched


# ---------------------------------------------------------------------------
# Expand logic
# ---------------------------------------------------------------------------


def _s2_id_for_seed(pmid: str, doi: str | None) -> str | None:
    """Convert a DB pmid to a Semantic Scholar paper identifier."""
    if pmid.startswith("S2:"):
        # Synthetic key — use CorpusId: prefix accepted by S2
        corpus_id = pmid[3:]
        return f"CorpusId:{corpus_id}"
    # Real PubMed ID
    return f"PMID:{pmid}"


def _insert_expansion_paper(
    conn: sqlite3.Connection,
    citing_paper: dict,
) -> bool:
    """Insert one paper discovered via forward citation expansion. Returns True if new."""
    external_ids = citing_paper.get("externalIds") or {}
    pmid = external_ids.get("PubMed") or external_ids.get("pubmed")
    doi = external_ids.get("DOI") or external_ids.get("doi")
    pmc_id = external_ids.get("PubMedCentral")
    corpus_id = citing_paper.get("corpusId")

    # Build primary key: real PMID preferred, else synthetic S2:{corpusId}
    if pmid:
        paper_key = str(pmid)
    elif corpus_id is not None:
        paper_key = f"S2:{corpus_id}"
    else:
        log.debug("Skipping expansion paper with no PMID or corpusId")
        return False

    title = citing_paper.get("title") or ""
    if not title:
        return False

    abstract = citing_paper.get("abstract")
    pub_year = citing_paper.get("year")
    authors_raw = citing_paper.get("authors") or []
    authors = json.dumps([a.get("name", "") for a in authors_raw if a.get("name")])
    journal_info = citing_paper.get("journal") or {}
    journal = journal_info.get("name") if isinstance(journal_info, dict) else None
    citations = citing_paper.get("citationCount") or 0
    influential = citing_paper.get("influentialCitationCount") or 0
    is_oa = 1 if citing_paper.get("isOpenAccess") else 0
    quality_score = compute_quality_score(
        citations=citations,
        influential_citations=influential,
        is_open_access=is_oa,
        has_pmc=bool(pmc_id),
        has_abstract=bool(abstract),
        journal=journal,
        pub_year=pub_year,
    )

    cur = conn.execute(
        """INSERT OR IGNORE INTO papers
               (pmid, doi, pmc_id, title, abstract, authors, journal, pub_year,
                pub_types, is_open_access, citations, influential_citations,
                quality_score, source)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            paper_key,
            doi,
            pmc_id,
            title,
            abstract,
            authors,
            journal,
            pub_year,
            json.dumps([]),
            is_oa,
            citations,
            influential,
            quality_score,
            "s2_expansion",
        ),
    )

    is_new = cur.rowcount > 0
    if is_new:
        conn.execute(
            """INSERT INTO papers_fts(pmid, title, abstract, full_text, authors, journal)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                paper_key,
                title,
                abstract or "",
                "",
                authors,
                journal or "",
            ),
        )
    return is_new


def _expand_seed(
    client: httpx.Client,
    conn: sqlite3.Connection,
    seed_pmid: str,
    seed_doi: str | None,
    min_year: int,
    max_papers: int,
    added_so_far: int,
) -> int:
    """Fetch forward citations for one seed; insert eligible papers. Returns count added."""
    s2_id = _s2_id_for_seed(seed_pmid, seed_doi)
    if not s2_id:
        log.warning("No S2 ID for seed %s — skipping", seed_pmid)
        return 0

    added = 0
    offset = 0
    page_limit = min(1000, max_papers - added_so_far - added + 10)  # ceiling for last page

    while added_so_far + added < max_papers:
        result = _get_with_retry(
            client,
            f"{S2_BASE}/paper/{s2_id}/citations",
            params={"fields": _FIELDS_CITATIONS, "offset": offset, "limit": page_limit},
        )
        time.sleep(_REQ_INTERVAL)

        if result is None:
            log.warning("Failed to fetch citations for seed %s at offset %d", seed_pmid, offset)
            break

        citing_entries = result.get("data") or []
        if not citing_entries:
            break

        for entry in citing_entries:
            if added_so_far + added >= max_papers:
                break
            citing_paper = entry.get("citingPaper") or {}
            # Year filter
            pub_year = citing_paper.get("year")
            if pub_year is not None and pub_year < min_year:
                continue
            if _insert_expansion_paper(conn, citing_paper):
                added += 1

        # Pagination: S2 returns `next` offset or omits it when exhausted
        next_offset = result.get("next")
        if next_offset is None:
            break
        offset = next_offset

    return added


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


@click.group()
def cli() -> None:
    """Enrich papers with Semantic Scholar citation data."""


@cli.command()
@click.option("--query-id", default=None, help="Enrich only papers from this query.")
@click.option("--limit", default=None, type=int, help="Limit to N papers (for testing).")
def enrich(query_id: str | None, limit: int | None) -> None:
    """Fetch citation counts from Semantic Scholar for papers in the database."""
    _check_db()

    with sqlite3.connect(DB_PATH) as conn:
        papers = _get_papers_to_enrich(conn, query_id, limit)

    if not papers:
        click.echo("No unenriched papers found — nothing to do.")
        return

    log.info("Enriching %d papers…", len(papers))

    with _make_client() as client, sqlite3.connect(DB_PATH) as conn:
        enriched = _enrich_papers(client, papers, conn)

    # Summary
    with sqlite3.connect(DB_PATH) as conn:
        total_enriched = conn.execute(
            "SELECT COUNT(*) FROM papers WHERE citations > 0"
        ).fetchone()[0]
        avg_row = conn.execute(
            "SELECT AVG(citations) FROM papers WHERE citations > 0"
        ).fetchone()
        avg_citations = avg_row[0] or 0.0
        top5 = conn.execute(
            "SELECT pmid, title, citations FROM papers ORDER BY citations DESC LIMIT 5"
        ).fetchall()

    click.echo(f"✓  Enriched {enriched} papers with citation data.")
    click.echo(f"   Total papers with citations: {total_enriched}")
    click.echo(f"   Average citations (enriched): {avg_citations:.1f}")
    if top5:
        click.echo("   Top 5 by citations:")
        for pmid, title, cites in top5:
            click.echo(f"     [{cites or 0:>5}] {pmid}: {(title or '')[:70]}")


@cli.command()
@click.option("--min-year", default=2020, show_default=True, help="Minimum publication year for citing papers.")
@click.option("--max-papers", default=500, show_default=True, help="Maximum new papers to add.")
@click.option("--top-seeds", default=20, show_default=True, help="Number of top-cited seed papers to traverse.")
def expand(min_year: int, max_papers: int, top_seeds: int) -> None:
    """Discover new papers via forward citation traversal from top-cited seeds."""
    _check_db()

    with sqlite3.connect(DB_PATH) as conn:
        seeds = conn.execute(
            """SELECT pmid, doi, citations
               FROM papers
               WHERE pmid IS NOT NULL
                 AND citations > 0
               ORDER BY citations DESC
               LIMIT ?""",
            (top_seeds,),
        ).fetchall()

    if not seeds:
        click.echo("No enriched seed papers found. Run `enrich` first.")
        return

    log.info(
        "Expanding from %d seeds (min_year=%d, max_papers=%d)…",
        len(seeds),
        min_year,
        max_papers,
    )

    added_total = 0
    with _make_client() as client, sqlite3.connect(DB_PATH) as conn:
        for seed_pmid, seed_doi, seed_citations in seeds:
            if added_total >= max_papers:
                break
            log.info(
                "Seed %s (citations=%d)…", seed_pmid, seed_citations or 0
            )
            added = _expand_seed(
                client,
                conn,
                seed_pmid,
                seed_doi,
                min_year=min_year,
                max_papers=max_papers,
                added_so_far=added_total,
            )
            added_total += added
            log.info("  → added %d papers from seed %s", added, seed_pmid)

    with sqlite3.connect(DB_PATH) as conn:
        total = conn.execute("SELECT COUNT(*) FROM papers").fetchone()[0]

    click.echo(f"✓  Forward expansion complete: added {added_total} new papers.")
    click.echo(f"   Total papers in database: {total}")


@cli.command()
def stats() -> None:
    """Show citation statistics for the research database."""
    _check_db()

    with sqlite3.connect(DB_PATH) as conn:
        total = conn.execute("SELECT COUNT(*) FROM papers").fetchone()[0]

        if total == 0:
            click.echo("0 papers in database.")
            return

        enriched_count = conn.execute(
            "SELECT COUNT(*) FROM papers WHERE citations > 0"
        ).fetchone()[0]
        unenriched_count = conn.execute(
            "SELECT COUNT(*) FROM papers WHERE citations IS NULL OR citations = 0"
        ).fetchone()[0]
        agg_row = conn.execute(
            "SELECT AVG(citations), MAX(citations), AVG(quality_score) FROM papers WHERE citations > 0"
        ).fetchone()
        avg_cites = agg_row[0] or 0.0
        max_cites = agg_row[1] or 0
        avg_quality = agg_row[2] or 0.0

        top10 = conn.execute(
            """SELECT pmid, title, citations, quality_score
               FROM papers
               ORDER BY citations DESC
               LIMIT 10"""
        ).fetchall()

        sources = conn.execute(
            "SELECT source, COUNT(*) FROM papers GROUP BY source ORDER BY COUNT(*) DESC"
        ).fetchall()

    click.echo("=== Citation Statistics ===")
    click.echo(f"Total papers in database: {total}")
    click.echo(f"  Enriched papers (citations > 0): {enriched_count}")
    click.echo(f"  Unenriched papers: {unenriched_count}")
    if enriched_count:
        click.echo(f"  Average citations: {avg_cites:.1f}")
        click.echo(f"  Max citations: {max_cites}")
        click.echo(f"  Average quality score: {avg_quality:.1f}")
    click.echo()
    if sources:
        click.echo("Source breakdown:")
        for src, count in sources:
            click.echo(f"  {src or 'unknown'}: {count} papers")
        click.echo()
    if top10:
        click.echo("Top papers by citations:")
        for pmid, title, cites, qscore in top10:
            click.echo(f"  [{cites or 0:>5}] q={qscore or 0:<4}  {pmid}: {(title or '')[:65]}")


if __name__ == "__main__":
    cli()
