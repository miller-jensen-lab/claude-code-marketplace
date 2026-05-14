#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Bootstrap the research database and directory structure.

Run directly:  ./scripts/setup.py
Via justfile:  just setup
Via uv:        uv run scripts/setup.py

Idempotent — safe to run multiple times.
"""

import os
import sqlite3
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths — resolved relative to CWD by default so the DB lands in the user's
# project, not in the plugin install dir. Override with $LIT_SEARCH_DATA_DIR
# (e.g., for a lab-wide shared corpus).
# ---------------------------------------------------------------------------

DATA_DIR = Path(os.environ.get("LIT_SEARCH_DATA_DIR", "data")).resolve()
FULLTEXT_DIR = DATA_DIR / "fulltext"
DB_PATH = DATA_DIR / "lit-search.db"

# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS papers (
    pmid TEXT PRIMARY KEY,
    doi TEXT,
    pmc_id TEXT,
    title TEXT NOT NULL,
    abstract TEXT,
    authors TEXT,  -- JSON array of strings
    journal TEXT,
    pub_year INTEGER,
    pub_types TEXT,  -- JSON array of strings
    source TEXT DEFAULT 'pubmed',  -- pubmed, openalex, biorxiv, semanticscholar
    citations INTEGER DEFAULT 0,
    influential_citations INTEGER DEFAULT 0,
    is_open_access INTEGER DEFAULT 0,
    quality_score INTEGER DEFAULT 0,
    fulltext_status TEXT,  -- NULL, 'fetched', 'abstract_only', 'failed'
    fulltext_source TEXT,  -- 'pmc_xml', 'html', NULL
    fulltext_words INTEGER DEFAULT 0,
    query_id TEXT,  -- which query found this paper
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS queries (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    query TEXT NOT NULL,
    category TEXT,  -- 'mechanism', 'review', 'methods', 'recent', 'background'
    max_results INTEGER DEFAULT 200,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS research_context (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TEXT DEFAULT (datetime('now'))
);

-- FTS5 virtual table for full-text search (content-backed).
-- Stores its own copy of indexed text so snippet(), highlight(), and bm25()
-- all work correctly and return actual content.
-- Populated by index_fts.py; search_pubmed.py seeds title/abstract on insert.
CREATE VIRTUAL TABLE IF NOT EXISTS papers_fts USING fts5(
    pmid UNINDEXED,
    title,
    abstract,
    full_text,
    authors,
    journal,
    tokenize='porter unicode61'
);
"""


# ---------------------------------------------------------------------------
# FTS5 smoke test
# ---------------------------------------------------------------------------

def _smoke_test_fts5(conn: sqlite3.Connection) -> None:
    """Verify FTS5 is functional using SAVEPOINT so no data is left behind."""
    conn.execute("SAVEPOINT fts_test")
    try:
        conn.execute(
            "INSERT INTO papers_fts(pmid, title, abstract, full_text, authors, journal) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                "SMOKE_TEST_001",
                "TNF-induced NF-kB dynamics in single macrophages",
                "Live-cell imaging reveals heterogeneous NF-kB translocation kinetics.",
                "Full text discussing single-cell NF-kB signaling in macrophages.",
                "Smith J, Doe A",
                "Cell",
            ),
        )
        count = conn.execute(
            "SELECT count(*) FROM papers_fts WHERE papers_fts MATCH 'NF-kB'"
        ).fetchone()[0]
        if count < 1:
            raise RuntimeError("FTS5 smoke test failed: search returned no results")
    finally:
        # Always roll back — we never want this sentinel row in the DB.
        conn.execute("ROLLBACK TO fts_test")
        conn.execute("RELEASE fts_test")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def setup() -> None:
    """Create directories, apply schema, verify FTS5."""
    # 1. Directories
    FULLTEXT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"✓  Directories ready: {DATA_DIR}/")

    # 2. Database + schema
    with sqlite3.connect(DB_PATH) as conn:
        conn.executescript(SCHEMA_SQL)

        # Count tables as a quick schema sanity check
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type IN ('table', 'shadow') "
            "AND name NOT LIKE 'sqlite_%' ORDER BY name"
        ).fetchall()
        table_names = [t[0] for t in tables]
        print(f"✓  Schema applied — tables: {', '.join(table_names)}")

        # 3. FTS5 smoke test
        _smoke_test_fts5(conn)
        print("✓  FTS5 search verified (porter + unicode61 tokenizer)")

    print()
    print("Setup complete. Next steps:")
    print("  1. Copy .env.example → .env and fill in API keys (optional)")
    print("  2. Run `just run search_pubmed '<query>'` to find papers")
    print(f"  3. Database: {DB_PATH}")


if __name__ == "__main__":
    try:
        setup()
    except Exception as exc:
        print(f"✗  Setup failed: {exc}", file=sys.stderr)
        sys.exit(1)
