#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "click>=8.1",
# ]
# ///
"""Populate the FTS5 search index from papers metadata and fulltext JSON files.

Run directly:  ./scripts/index_fts.py
Via justfile:  just run index_fts

Papers with fulltext JSON get full body indexed; others get title + abstract.
Incremental mode (default) deletes the old FTS row and re-inserts it per paper.
"""

import json
import logging
import os
import re
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
# Logging — all diagnostics to stderr so stdout stays clean
# ---------------------------------------------------------------------------

logging.basicConfig(
    stream=sys.stderr,
    level=logging.INFO,
    format="%(levelname)s: %(message)s",
)
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Text cleaning
# ---------------------------------------------------------------------------

JUNK_SECTIONS = [
    "references",
    "bibliography",
    "acknowledg",
    "funding",
    "author contributions",
    "competing interests",
    "conflict of interest",
    "disclosure",
    "data availability",
    "supplement",
    "appendix",
    "supporting information",
    "supplementary",
]

INLINE_BRACKET_CIT = re.compile(r"\[\s*\d+(?:\s*[-,;]\s*\d+)*\s*\]")
INLINE_PAREN_CIT = re.compile(r"\(\s*\d+(?:\s*[-,;]\s*\d+)*\s*\)")
EXCESS_WHITESPACE = re.compile(r"\s{3,}")

SECTION_CAP = 50_000
TOTAL_CAP = 300_000


def _is_junk_section(heading: str) -> bool:
    """Return True if the section heading matches a junk pattern."""
    lower = heading.lower()
    return any(junk in lower for junk in JUNK_SECTIONS)


def _clean_text(text: str) -> str:
    """Strip inline citations and collapse excessive whitespace."""
    text = INLINE_BRACKET_CIT.sub("", text)
    text = INLINE_PAREN_CIT.sub("", text)
    text = EXCESS_WHITESPACE.sub(" ", text)
    return text.strip()


def _build_full_text(data: dict) -> str:
    """Convert fulltext JSON into a cleaned, capped string with ## headers."""
    sections = data.get("sections") or []

    if not sections:
        # Flat body fallback
        body = data.get("body") or data.get("text") or ""
        return _clean_text(body)[:TOTAL_CAP]

    parts: list[str] = []
    total = 0

    for section in sections:
        heading = section.get("heading") or section.get("title") or ""
        text = section.get("text") or section.get("content") or ""

        if _is_junk_section(heading):
            continue

        text = _clean_text(text)[:SECTION_CAP]
        if not text:
            continue

        chunk = f"## {heading}\n{text}" if heading else text

        if total + len(chunk) > TOTAL_CAP:
            remaining = TOTAL_CAP - total
            if remaining > 200:
                parts.append(chunk[:remaining])
            break

        parts.append(chunk)
        total += len(chunk)

    return "\n\n".join(parts)


def _load_fulltext(pmid: str) -> str:
    """Load and clean fulltext JSON for a PMID; return empty string if missing."""
    json_path = FULLTEXT_DIR / f"{pmid}.json"
    if not json_path.exists():
        return ""
    try:
        data = json.loads(json_path.read_text(encoding="utf-8"))
        return _build_full_text(data)
    except Exception as exc:
        log.warning("Failed to load fulltext for %s: %s", pmid, exc)
        return ""


# ---------------------------------------------------------------------------
# FTS5 helpers
# ---------------------------------------------------------------------------


def _delete_fts_rows(conn: sqlite3.Connection, pmid: str) -> None:
    """Remove all FTS5 rows for this pmid by looking up rowids first."""
    rows = conn.execute(
        "SELECT rowid FROM papers_fts WHERE pmid = ?", (pmid,)
    ).fetchall()
    for (rowid,) in rows:
        conn.execute("DELETE FROM papers_fts WHERE rowid = ?", (rowid,))


def _insert_fts_row(conn: sqlite3.Connection, paper: dict, full_text: str) -> None:
    """Insert one paper row into FTS5."""
    conn.execute(
        "INSERT INTO papers_fts(pmid, title, abstract, full_text, authors, journal) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (
            paper["pmid"],
            paper["title"] or "",
            paper["abstract"] or "",
            full_text,
            paper["authors"] or "",
            paper["journal"] or "",
        ),
    )


# ---------------------------------------------------------------------------
# Indexing logic
# ---------------------------------------------------------------------------


def _index_papers(
    conn: sqlite3.Connection,
    *,
    rebuild: bool = False,
    fulltext_only: bool = False,
    limit: int | None = None,
) -> tuple[int, int]:
    """Index papers into FTS5.

    Returns (total_indexed, papers_with_fulltext).
    """
    if rebuild:
        log.info("Dropping and recreating FTS5 table for full rebuild…")
        conn.execute("DROP TABLE IF EXISTS papers_fts")
        conn.execute(
            """CREATE VIRTUAL TABLE papers_fts USING fts5(
                pmid UNINDEXED,
                title,
                abstract,
                full_text,
                authors,
                journal,
                tokenize='porter unicode61'
            )"""
        )

    sql = (
        "SELECT pmid, title, abstract, authors, journal "
        "FROM papers ORDER BY quality_score DESC"
    )
    if limit is not None:
        sql += f" LIMIT {limit}"

    rows = conn.execute(sql).fetchall()
    cols = ["pmid", "title", "abstract", "authors", "journal"]
    papers = [dict(zip(cols, r)) for r in rows]

    total = 0
    with_fulltext = 0

    for paper in papers:
        pmid = paper["pmid"]
        full_text = _load_fulltext(pmid)

        if fulltext_only and not full_text:
            continue

        if not rebuild:
            # Incremental: delete any existing entries for this pmid then re-insert
            _delete_fts_rows(conn, pmid)

        _insert_fts_row(conn, paper, full_text)

        if full_text:
            with_fulltext += 1
        total += 1

    return total, with_fulltext


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


@click.command()
@click.option(
    "--rebuild",
    is_flag=True,
    help="Clear the FTS5 index and reindex all papers from scratch.",
)
@click.option(
    "--fulltext-only",
    is_flag=True,
    help="Only index papers that have fulltext JSON files available.",
)
@click.option(
    "--stats",
    is_flag=True,
    help="Print index statistics and exit (no indexing).",
)
@click.option(
    "--limit",
    default=None,
    type=int,
    help="Maximum number of papers to index (for testing).",
)
def main(
    rebuild: bool,
    fulltext_only: bool,
    stats: bool,
    limit: int | None,
) -> None:
    """Populate the FTS5 search index from papers and fulltext JSON files."""
    if not DB_PATH.exists():
        click.echo(
            f"Error: database not found at {DB_PATH}. Run `just setup` first.",
            err=True,
        )
        sys.exit(1)

    with sqlite3.connect(DB_PATH) as conn:
        if stats:
            fts_count = conn.execute(
                "SELECT COUNT(*) FROM papers_fts"
            ).fetchone()[0]
            papers_count = conn.execute(
                "SELECT COUNT(*) FROM papers"
            ).fetchone()[0]
            fulltext_files = len(list(FULLTEXT_DIR.glob("*.json"))) if FULLTEXT_DIR.exists() else 0
            click.echo(f"Papers in database:   {papers_count}")
            click.echo(f"Papers indexed (FTS): {fts_count}")
            click.echo(f"Fulltext JSON files:  {fulltext_files}")
            return

        total, with_fulltext = _index_papers(
            conn,
            rebuild=rebuild,
            fulltext_only=fulltext_only,
            limit=limit,
        )

    abstract_only = total - with_fulltext
    mode = "rebuilt" if rebuild else "indexed"
    log.info(
        "%d papers %s — %d with fulltext, %d abstract only",
        total,
        mode,
        with_fulltext,
        abstract_only,
    )
    click.echo(
        f"✓  {total} papers indexed"
        f" — {with_fulltext} with fulltext, {abstract_only} abstract only"
    )


if __name__ == "__main__":
    main()
