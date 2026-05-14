#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "click>=8.1",
# ]
# ///
"""Search the local research literature database.

Run directly:  ./scripts/search.py "NF-kB macrophage"
Via justfile:  just run search "NF-kB macrophage"

FTS5 syntax is fully supported: AND, OR, NOT, "phrase search", prefix*, column:term.
BM25 ranking is used (lower/more-negative score = better match).
"""

import json
import logging
import os
import sqlite3
import sys
from pathlib import Path

import click

# ---------------------------------------------------------------------------
# Paths — CWD-based, override with $LIT_SEARCH_DATA_DIR
# ---------------------------------------------------------------------------

DATA_DIR = Path(os.environ.get("LIT_SEARCH_DATA_DIR", "data")).resolve()
DB_PATH = DATA_DIR / "lit-search.db"
FULLTEXT_DIR = DATA_DIR / "fulltext"

# ---------------------------------------------------------------------------
# Logging — diagnostics to stderr, structured output to stdout
# ---------------------------------------------------------------------------

logging.basicConfig(
    stream=sys.stderr,
    level=logging.INFO,
    format="%(levelname)s: %(message)s",
)
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# FTS5 column indices (must match schema in setup.py)
#   0=pmid (UNINDEXED), 1=title, 2=abstract, 3=full_text, 4=authors, 5=journal
# ---------------------------------------------------------------------------

_COL_TITLE = 1
_COL_ABSTRACT = 2
_COL_FULLTEXT = 3

# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------


def _open_db() -> sqlite3.Connection:
    """Open the database or exit with a helpful message."""
    if not DB_PATH.exists():
        click.echo(
            f"Error: database not found at {DB_PATH}. Run `just setup` first.",
            err=True,
        )
        sys.exit(1)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# ---------------------------------------------------------------------------
# SQL
# ---------------------------------------------------------------------------

# Core search: FTS5 MATCH + BM25 ranking joined to papers metadata.
# BM25 returns negative values; ORDER BY bm25(papers_fts) ASC → best match first.
# NOTE: FTS5 auxiliary functions (bm25, snippet) must use the real table name,
#       not an alias — SQLite will otherwise report "no such column".
_SEARCH_SQL = """
SELECT
    p.pmid,
    p.title,
    p.journal,
    p.pub_year,
    p.citations,
    p.quality_score,
    p.fulltext_status,
    p.fulltext_source,
    p.doi,
    snippet(papers_fts, {col_title}, '**', '**', '...', 20) AS title_snippet,
    snippet(papers_fts, {col_abstract}, '**', '**', '...', 20) AS abstract_snippet,
    snippet(papers_fts, {col_fulltext}, '**', '**', '...', 20) AS fulltext_snippet,
    bm25(papers_fts) AS rank
FROM papers_fts
JOIN papers p ON p.pmid = papers_fts.pmid
WHERE papers_fts MATCH ?
    AND (? IS NULL OR p.pub_year >= ?)
    AND (? IS NULL OR p.citations >= ?)
ORDER BY bm25(papers_fts)
LIMIT ?
""".format(
    col_title=_COL_TITLE,
    col_abstract=_COL_ABSTRACT,
    col_fulltext=_COL_FULLTEXT,
)

# Within-paper variant: restrict to a single pmid (UNINDEXED but still filterable).
_SEARCH_WITHIN_SQL = """
SELECT
    p.pmid,
    p.title,
    p.journal,
    p.pub_year,
    p.citations,
    p.quality_score,
    p.fulltext_status,
    p.fulltext_source,
    p.doi,
    snippet(papers_fts, {col_title}, '**', '**', '...', 20) AS title_snippet,
    snippet(papers_fts, {col_abstract}, '**', '**', '...', 20) AS abstract_snippet,
    snippet(papers_fts, {col_fulltext}, '**', '**', '...', 20) AS fulltext_snippet,
    bm25(papers_fts) AS rank
FROM papers_fts
JOIN papers p ON p.pmid = papers_fts.pmid
WHERE papers_fts MATCH ?
    AND papers_fts.pmid = ?
ORDER BY bm25(papers_fts)
LIMIT ?
""".format(
    col_title=_COL_TITLE,
    col_abstract=_COL_ABSTRACT,
    col_fulltext=_COL_FULLTEXT,
)

# Count total matching rows (for display; no LIMIT).
_COUNT_SQL = """
SELECT COUNT(*)
FROM papers_fts
JOIN papers p ON p.pmid = papers_fts.pmid
WHERE papers_fts MATCH ?
    AND (? IS NULL OR p.pub_year >= ?)
    AND (? IS NULL OR p.citations >= ?)
"""


# ---------------------------------------------------------------------------
# Search logic
# ---------------------------------------------------------------------------


def _run_search(
    conn: sqlite3.Connection,
    query: str,
    *,
    min_year: int | None = None,
    min_citations: int | None = None,
    limit: int = 20,
    within: str | None = None,
) -> tuple[list[sqlite3.Row], int]:
    """Execute FTS5 search and return (rows, total_matching)."""
    if within:
        rows = conn.execute(
            _SEARCH_WITHIN_SQL,
            (query, within, limit),
        ).fetchall()
        total = len(rows)
    else:
        rows = conn.execute(
            _SEARCH_SQL,
            (query, min_year, min_year, min_citations, min_citations, limit),
        ).fetchall()
        # Get accurate total (may be larger than limit).
        total = conn.execute(
            _COUNT_SQL,
            (query, min_year, min_year, min_citations, min_citations),
        ).fetchone()[0]
    return rows, total


def _best_snippet(row: sqlite3.Row) -> str:
    """Pick the most informative snippet from fulltext > abstract > title."""
    for key in ("fulltext_snippet", "abstract_snippet", "title_snippet"):
        val = row[key] or ""
        if "**" in val:
            return val
    # Fallback to any non-empty snippet.
    for key in ("fulltext_snippet", "abstract_snippet", "title_snippet"):
        val = row[key] or ""
        if val.strip():
            return val
    return "(no snippet)"


# ---------------------------------------------------------------------------
# Output formatters
# ---------------------------------------------------------------------------


def _human_output(
    rows: list[sqlite3.Row],
    query: str,
    limit: int,
    total: int,
) -> str:
    lines: list[str] = []
    lines.append(f"Found {total} results for: {query}\n")

    for i, row in enumerate(rows, 1):
        pmid = row["pmid"]
        title = row["title"] or "(no title)"
        journal = row["journal"] or "Unknown journal"
        year = row["pub_year"] or "?"
        citations = row["citations"] or 0
        score = row["quality_score"] or 0
        source = row["fulltext_source"] or row["fulltext_status"] or "abstract"
        snippet = _best_snippet(row)

        lines.append(f"{i}. [PMID:{pmid}] {title}")
        lines.append(
            f"   {journal} ({year}) | Citations: {citations}"
            f" | Score: {score} | Source: {source}"
        )
        lines.append(f"   {snippet}")
        lines.append("")

    if total > limit:
        lines.append(
            f"({total} total — showing top {limit}. Use --limit N for more.)"
        )

    return "\n".join(lines)


def _json_output(rows: list[sqlite3.Row], query: str, total: int) -> dict:
    results = []
    for row in rows:
        snippet = _best_snippet(row)
        results.append(
            {
                "pmid": row["pmid"],
                "title": row["title"],
                "journal": row["journal"],
                "pub_year": row["pub_year"],
                "citations": row["citations"],
                "quality_score": row["quality_score"],
                "has_fulltext": row["fulltext_status"] == "fetched",
                "fulltext_source": row["fulltext_source"],
                "snippet": snippet,
                "rank": row["rank"],
            }
        )
    return {
        "query": query,
        "total_hits": total,
        "results": results,
    }


# ---------------------------------------------------------------------------
# --get command
# ---------------------------------------------------------------------------


def _cmd_get(conn: sqlite3.Connection, pmid: str, as_json: bool) -> None:
    """Print all metadata and available full text for one paper."""
    row = conn.execute("SELECT * FROM papers WHERE pmid = ?", (pmid,)).fetchone()
    if row is None:
        msg = f"No paper found with PMID: {pmid}"
        if as_json:
            click.echo(json.dumps({"error": msg}))
        else:
            click.echo(msg)
        sys.exit(1)

    paper = dict(row)

    # Attempt to load fulltext JSON.
    json_path = FULLTEXT_DIR / f"{pmid}.json"
    fulltext_data: dict | None = None
    if json_path.exists():
        try:
            fulltext_data = json.loads(json_path.read_text(encoding="utf-8"))
        except Exception as exc:
            log.warning("Failed to load fulltext for %s: %s", pmid, exc)

    if as_json:
        out = {**paper, "fulltext_data": fulltext_data}
        click.echo(json.dumps(out, indent=2, default=str))
        return

    # Human-readable output.
    title = paper.get("title", "(no title)")
    click.echo(f"[PMID:{pmid}] {title}")
    click.echo(f"title:           {title}")
    click.echo(f"Journal:         {paper.get('journal', 'Unknown')}")
    click.echo(f"Year:            {paper.get('pub_year', '?')}")
    click.echo(f"Authors:         {paper.get('authors', '')}")
    click.echo(f"Citations:       {paper.get('citations', 0)}")
    click.echo(f"Quality Score:   {paper.get('quality_score', 0)}")
    click.echo(f"Fulltext Status: {paper.get('fulltext_status', 'none')}")
    doi = paper.get("doi", "")
    if doi:
        click.echo(f"DOI:             https://doi.org/{doi}")
    pmc = paper.get("pmc_id", "")
    if pmc:
        click.echo(f"PMC:             https://www.ncbi.nlm.nih.gov/pmc/articles/{pmc}/")

    click.echo()
    click.echo("Abstract:")
    click.echo(paper.get("abstract") or "(no abstract)")

    if fulltext_data:
        click.echo()
        click.echo("Full Text: (loaded from JSON)")
        sections = fulltext_data.get("sections", [])
        if sections:
            for sec in sections[:5]:
                heading = sec.get("heading") or sec.get("title") or ""
                text = (sec.get("text") or sec.get("content") or "")[:600]
                if heading:
                    click.echo(f"\n## {heading}")
                click.echo(text)
        else:
            body = (
                fulltext_data.get("body") or fulltext_data.get("text") or ""
            )[:1500]
            click.echo(body)


# ---------------------------------------------------------------------------
# --overview command
# ---------------------------------------------------------------------------


def _cmd_overview(conn: sqlite3.Connection, as_json: bool) -> None:
    """Print corpus-wide statistics."""
    total = conn.execute("SELECT COUNT(*) FROM papers").fetchone()[0]
    with_fulltext = conn.execute(
        "SELECT COUNT(*) FROM papers WHERE fulltext_status = 'fetched'"
    ).fetchone()[0]
    abstract_only = conn.execute(
        "SELECT COUNT(*) FROM papers WHERE fulltext_status = 'abstract_only'"
    ).fetchone()[0]
    fts_count = conn.execute("SELECT COUNT(*) FROM papers_fts").fetchone()[0]

    top_journals = conn.execute(
        """SELECT journal, COUNT(*) AS n
           FROM papers WHERE journal IS NOT NULL
           GROUP BY journal ORDER BY n DESC LIMIT 10"""
    ).fetchall()

    year_dist = conn.execute(
        """SELECT pub_year, COUNT(*) AS n
           FROM papers WHERE pub_year IS NOT NULL
           GROUP BY pub_year ORDER BY pub_year DESC LIMIT 15"""
    ).fetchall()

    top_cited = conn.execute(
        """SELECT pmid, title, journal, pub_year, citations
           FROM papers ORDER BY citations DESC LIMIT 10"""
    ).fetchall()

    if as_json:
        data = {
            "total_papers": total,
            "with_fulltext": with_fulltext,
            "abstract_only": abstract_only,
            "fts_indexed": fts_count,
            "top_journals": [
                {"journal": r[0], "count": r[1]} for r in top_journals
            ],
            "year_distribution": [
                {"year": r[0], "count": r[1]} for r in year_dist
            ],
            "top_cited": [
                {
                    "pmid": r[0],
                    "title": r[1],
                    "journal": r[2],
                    "year": r[3],
                    "citations": r[4],
                }
                for r in top_cited
            ],
        }
        click.echo(json.dumps(data, indent=2))
        return

    click.echo("=== Corpus Overview ===")
    click.echo(f"Total papers:   {total}")
    click.echo(f"With full text: {with_fulltext}")
    click.echo(f"Abstract only:  {abstract_only}")
    click.echo(f"FTS5 indexed:   {fts_count}")
    click.echo()
    click.echo("Top Journals:")
    for r in top_journals:
        click.echo(f"  {r[0]}: {r[1]}")
    click.echo()
    click.echo("Year Distribution (recent first):")
    for r in year_dist:
        click.echo(f"  {r[0]}: {r[1]}")
    click.echo()
    click.echo("Top 10 by Citations:")
    for i, r in enumerate(top_cited, 1):
        click.echo(f"  {i}. [PMID:{r[0]}] {r[1]}")
        click.echo(f"     {r[2]} ({r[3]}) | Citations: {r[4]}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


@click.command()
@click.argument("query", required=False)
@click.option(
    "--json",
    "as_json",
    is_flag=True,
    help="Output as JSON (diagnostics go to stderr).",
)
@click.option(
    "--limit",
    default=20,
    show_default=True,
    type=int,
    help="Maximum number of results to return.",
)
@click.option(
    "--min-year",
    default=None,
    type=int,
    metavar="YEAR",
    help="Only include papers published in YEAR or later.",
)
@click.option(
    "--min-citations",
    default=None,
    type=int,
    metavar="N",
    help="Only include papers with at least N citations.",
)
@click.option(
    "--get",
    "get_pmid",
    default=None,
    metavar="PMID",
    help="Load and display full metadata + text for one paper.",
)
@click.option(
    "--within",
    default=None,
    metavar="PMID",
    help="Restrict search to a single paper's indexed text.",
)
@click.option(
    "--overview",
    is_flag=True,
    help="Show corpus statistics and exit.",
)
def main(
    query: str | None,
    as_json: bool,
    limit: int,
    min_year: int | None,
    min_citations: int | None,
    get_pmid: str | None,
    within: str | None,
    overview: bool,
) -> None:
    """Search the local research literature database.

    QUERY is an FTS5 search string.  Supports AND/OR/NOT, "phrase search",
    prefix*, and column filters like title:macrophage.

    Examples:

    \b
      ./scripts/search.py "NF-kB macrophage"
      ./scripts/search.py '"single cell" macrophage' --min-year 2020
      ./scripts/search.py "TLR4 signaling" --limit 30 --json
      ./scripts/search.py --get 34567890
      ./scripts/search.py "hepcidin" --within 34567890
      ./scripts/search.py --overview
    """
    conn = _open_db()

    if overview:
        _cmd_overview(conn, as_json)
        return

    if get_pmid:
        _cmd_get(conn, get_pmid, as_json)
        return

    if not query:
        click.echo(
            "Error: QUERY argument is required (or use --get / --overview).",
            err=True,
        )
        sys.exit(1)

    try:
        rows, total = _run_search(
            conn,
            query,
            min_year=min_year,
            min_citations=min_citations,
            limit=limit,
            within=within,
        )
    except sqlite3.OperationalError as exc:
        click.echo(f"Search error: {exc}", err=True)
        sys.exit(1)

    if total == 0:
        if as_json:
            click.echo(json.dumps({"query": query, "total_hits": 0, "results": []}))
        else:
            click.echo(f"No results found for: {query}")
        return

    if as_json:
        click.echo(json.dumps(_json_output(rows, query, total), indent=2))
    else:
        click.echo(_human_output(rows, query, limit, total))


if __name__ == "__main__":
    main()
