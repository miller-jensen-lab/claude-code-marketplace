#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "biopython>=1.84",
#     "httpx>=0.27",
#     "trafilatura>=2.0",
#     "lxml>=5.0",
#     "readability-lxml>=0.8",
#     "lxml-html-clean>=0.4",
#     "click>=8.1",
# ]
# ///
"""Fetch full text for papers in the research database.

Three-tier strategy, tried in order:
  1. PMC XML   — Biopython Entrez efetch → JATS XML parsed with lxml
  2. Unpaywall — OA URL lookup → curl-impersonate → trafilatura
  3. DOI page  — curl-impersonate on doi.org/{doi} → trafilatura

Papers that fail all tiers are marked abstract_only.

Run directly:  ./scripts/fetch_fulltext.py --limit 20
Via justfile:  just run fetch_fulltext --limit 20
"""

import glob
import json
import logging
import os
import random
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import click
import httpx
from Bio import Entrez
from lxml import etree

try:
    import trafilatura

    HAS_TRAFILATURA = True
except ImportError:
    HAS_TRAFILATURA = False

try:
    from readability import Document as ReadabilityDoc

    HAS_READABILITY = True
except ImportError:
    HAS_READABILITY = False

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

DATA_DIR = Path(os.environ.get("LIT_SEARCH_DATA_DIR", "data")).resolve()
FULLTEXT_DIR = DATA_DIR / "fulltext"
DB_PATH = DATA_DIR / "lit-search.db"

# ---------------------------------------------------------------------------
# Download safeguards — protect a laptop-class machine against pathological
# responses (5 GB PDFs, mis-extracted 600k-word text, runaway corpus growth).
# Override via env vars if you really know what you're doing.
# ---------------------------------------------------------------------------

MAX_RESPONSE_BYTES = int(os.environ.get("LIT_SEARCH_MAX_BYTES", 50 * 1024 * 1024))
MAX_FULLTEXT_WORDS = int(os.environ.get("LIT_SEARCH_MAX_WORDS", 50_000))
RUN_WARN_BYTES = int(os.environ.get("LIT_SEARCH_RUN_WARN_BYTES", 2 * 1024 * 1024 * 1024))

# Thread-safe accumulator for total bytes downloaded this run.
_bytes_lock = threading.Lock()
_run_bytes_total = 0
_run_warned = False


def _account_bytes(n: int) -> None:
    """Add to the run-total and warn once when crossing RUN_WARN_BYTES."""
    global _run_bytes_total, _run_warned
    with _bytes_lock:
        _run_bytes_total += n
        if not _run_warned and _run_bytes_total > RUN_WARN_BYTES:
            log.warning(
                "Downloaded %.1f GB this run — consider interrupting if this is unexpected.",
                _run_bytes_total / 1024 / 1024 / 1024,
            )
            _run_warned = True


def _truncate_to_word_limit(text: str, limit: int = MAX_FULLTEXT_WORDS) -> str:
    """Cap a long text at `limit` words (roughly — splits on whitespace)."""
    if not text:
        return text
    words = text.split()
    if len(words) <= limit:
        return text
    log.info("Truncating extracted text: %d → %d words", len(words), limit)
    return " ".join(words[:limit]) + "\n\n[TRUNCATED — original was longer than limit]"

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
# Entrez setup (mirrors search_pubmed.py)
# ---------------------------------------------------------------------------

Entrez.email = "research-tool@example.com"
_api_key = os.environ.get("NCBI_API_KEY", "")
if _api_key:
    Entrez.api_key = _api_key

_entrez_cache = Path(os.environ.get("BIOPYTHON_CACHE", "/tmp/biopython_entrez_cache"))
_entrez_cache.mkdir(parents=True, exist_ok=True)
Entrez.local_cache = str(_entrez_cache)

# ---------------------------------------------------------------------------
# curl-impersonate detection
# ---------------------------------------------------------------------------

_CURL_CANDIDATES = [
    "curl_chrome124",
    "curl_chrome123",
    "curl_chrome116",
    "curl_chrome110",
    "curl_chrome101",
    "curl_chrome99",
    "curl-impersonate-chrome",
]


def _find_curl_impersonate() -> str | None:
    """Return path to any curl_chrome* binary, or None if unavailable."""
    for name in _CURL_CANDIDATES:
        path = shutil.which(name)
        if path:
            return path
    # Scan PATH directories for any curl_chrome* glob match
    for d in os.environ.get("PATH", "").split(os.pathsep):
        try:
            matches = glob.glob(os.path.join(d, "curl_chrome*"))
            if matches:
                return matches[0]
        except Exception:
            pass
    return None


CURL_BIN: str | None = _find_curl_impersonate()

# ---------------------------------------------------------------------------
# Rate limiting — per-domain, thread-safe
# ---------------------------------------------------------------------------

_rl_global = threading.Lock()
_rl_domain_locks: dict[str, threading.Lock] = {}
_rl_last_access: dict[str, float] = {}

_RATE_DELAYS: dict[str, float] = {
    "eutils.ncbi.nlm.nih.gov": 0.34,  # 3 req/s without key
    "api.unpaywall.org": 1.0,
}
_RATE_DEFAULT = 2.0  # per-domain for publisher sites


def _get_domain_lock(domain: str) -> threading.Lock:
    with _rl_global:
        if domain not in _rl_domain_locks:
            _rl_domain_locks[domain] = threading.Lock()
        return _rl_domain_locks[domain]


def rate_wait(domain: str) -> None:
    """Block the calling thread until it's safe to hit `domain`."""
    delay = _RATE_DELAYS.get(domain, _RATE_DEFAULT)
    lock = _get_domain_lock(domain)
    with lock:
        now = time.time()
        last = _rl_last_access.get(domain, 0.0)
        wait = delay - (now - last)
        if wait > 0:
            time.sleep(wait)
        _rl_last_access[domain] = time.time()


def _domain_of(url: str) -> str:
    try:
        return urlparse(url).netloc or url
    except Exception:
        return url


# ---------------------------------------------------------------------------
# Content quality guards
# ---------------------------------------------------------------------------

_BLOCK_PHRASES = [
    "just a moment",
    "verifying you are human",
    "cookies disabled",
    "access denied",
    "purchase pdf",
    "sign in to continue",
    "please enable cookies",
    "cloudflare",
    "enable javascript",
    "403 forbidden",
]


def _is_blocked(text: str) -> bool:
    lower = text.lower()
    return any(phrase in lower for phrase in _BLOCK_PHRASES)


def _is_pdf(data: bytes) -> bool:
    return data[:4] == b"%PDF"


def _word_count(text: str) -> int:
    return len(text.split()) if text else 0


def _strip_inline_citations(text: str) -> str:
    """Remove citation markers like [1,2,3] or (1-5)."""
    text = re.sub(r"\[\s*\d+(?:[,;\s]+\d+)*\s*\]", "", text)
    text = re.sub(r"\(\s*\d+(?:[-–]\d+)?\s*\)", "", text)
    return text


# ---------------------------------------------------------------------------
# JATS XML parsing helpers
# ---------------------------------------------------------------------------


def _local_tag(elem: etree._Element) -> str:  # noqa: SLF001
    """Return the local name of an lxml element (strips namespace URI)."""
    tag = elem.tag
    if isinstance(tag, str) and "}" in tag:
        return tag.split("}", 1)[1].lower()
    return str(tag).lower() if isinstance(tag, str) else ""


def _text_of(elem: etree._Element) -> str:  # noqa: SLF001
    """Recursively extract all text content from an lxml element."""
    parts: list[str] = []
    if elem.text:
        stripped = elem.text.strip()
        if stripped:
            parts.append(stripped)
    for child in elem:
        child_text = _text_of(child)
        if child_text:
            parts.append(child_text)
        if child.tail:
            stripped = child.tail.strip()
            if stripped:
                parts.append(stripped)
    return " ".join(parts)


def _xpath(elem: etree._Element, expr: str) -> list:  # noqa: SLF001
    """Run an XPath expression, returning [] on error."""
    try:
        return elem.xpath(expr)
    except Exception:
        return []


def _parse_jats_xml(xml_bytes: bytes) -> dict | None:
    """Parse PMC JATS XML bytes into structured content dict.

    Returns dict with title, abstract, sections, tables, figures, word_count.
    Returns None on parse failure or empty body.
    """
    if not xml_bytes or len(xml_bytes) < 200:
        return None

    parser = etree.XMLParser(
        recover=True,
        load_dtd=False,
        no_network=True,
        resolve_entities=False,
    )
    try:
        root = etree.fromstring(xml_bytes, parser=parser)
    except Exception as exc:
        log.warning("XML parse error: %s", exc)
        return None

    # Locate <article> — may be root or wrapped in <pmc-articleset>
    local = _local_tag(root)
    if local == "article":
        article = root
    else:
        candidates = _xpath(root, ".//*[local-name()='article']")
        if not candidates:
            log.warning("No <article> element found in PMC XML")
            return None
        article = candidates[0]

    # --- Title ---
    title = ""
    for t in _xpath(article, ".//*[local-name()='article-title']"):
        title = _text_of(t).strip()
        if title:
            break

    # --- Abstract ---
    abstract = ""
    for a in _xpath(article, ".//*[local-name()='abstract']"):
        abstract = _text_of(a).strip()
        if abstract:
            break

    # --- Body sections (recursive — includes nested <sec> elements) ---
    sections: list[dict] = []
    bodies = _xpath(article, ".//*[local-name()='body']")

    def _extract_section(sec_elem: etree._Element, depth: int = 0) -> None:
        """Recursively extract section content, including nested <sec> elements."""
        sec_title = "Section"
        para_parts: list[str] = []
        for child in sec_elem:
            lt = _local_tag(child)
            if lt == "title":
                sec_title = _text_of(child).strip() or "Section"
            elif lt == "sec":
                # Recurse into nested sections
                _extract_section(child, depth + 1)
            else:
                # Paragraphs, lists, tables, etc.
                t = _text_of(child).strip()
                if t:
                    para_parts.append(t)
        sec_text = " ".join(para_parts)
        if sec_text and len(sec_text) > 30:
            sections.append(
                {
                    "name": sec_title,
                    "text": _strip_inline_citations(sec_text),
                }
            )

    for body in bodies[:1]:
        direct_secs = _xpath(body, "*[local-name()='sec']")
        for sec in direct_secs:
            _extract_section(sec)
        # If no structured sections, fall back to full body text
        if not sections:
            body_text = _text_of(body).strip()
            if body_text and len(body_text) > 100:
                sections = [
                    {
                        "name": "Full Text",
                        "text": _strip_inline_citations(body_text),
                    }
                ]

    # --- Tables ---
    tables: list[dict] = []
    for tw in _xpath(article, ".//*[local-name()='table-wrap']"):
        caption = ""
        for c in _xpath(tw, ".//*[local-name()='caption']") or _xpath(tw, ".//*[local-name()='title']"):
            caption = _text_of(c).strip()
            if caption:
                break
        tables.append({"caption": caption})

    # --- Figures ---
    figures: list[dict] = []
    for fig in _xpath(article, ".//*[local-name()='fig']"):
        label = ""
        caption = ""
        for child in fig:
            lt = _local_tag(child)
            if lt == "label":
                label = _text_of(child).strip()
            elif lt == "caption":
                caption = _text_of(child).strip()
        if label or caption:
            figures.append({"label": label, "caption": caption})

    full_text = " ".join(s["text"] for s in sections)
    if not full_text:
        full_text = abstract

    # Cap absurdly long extractions (bad parses, multi-paper PDFs, etc.)
    wc_pre = _word_count(full_text)
    if wc_pre > MAX_FULLTEXT_WORDS:
        full_text = _truncate_to_word_limit(full_text)
        # Also truncate per-section text proportionally — keep the structure
        # but stop any one section from blowing past the limit.
        for s in sections:
            if _word_count(s.get("text", "")) > MAX_FULLTEXT_WORDS:
                s["text"] = _truncate_to_word_limit(s["text"])

    wc = _word_count(full_text)
    return {
        "title": title,
        "abstract": abstract,
        "sections": sections,
        "tables": tables,
        "figures": figures,
        "word_count": wc,
    }


# ---------------------------------------------------------------------------
# Tier 1 — PMC XML via Biopython Entrez
# ---------------------------------------------------------------------------


def _strip_pmc_prefix(pmc_id: str) -> str:
    """Return numeric part of a PMC ID ('PMC1234567' → '1234567')."""
    return re.sub(r"^[Pp][Mm][Cc]", "", pmc_id).strip()


def fetch_pmc_xml(pmid: str, pmc_id: str) -> dict | None:
    """Fetch PMC full-text XML and return parsed content dict, or None."""
    numeric_id = _strip_pmc_prefix(pmc_id)
    domain = "eutils.ncbi.nlm.nih.gov"
    log.info("PMC XML: PMID=%s PMC=%s", pmid, pmc_id)
    raw = None
    for attempt in range(3):
        rate_wait(domain)
        try:
            handle = Entrez.efetch(
                db="pmc",
                id=numeric_id,
                rettype="xml",
                retmode="xml",
            )
            raw = handle.read()
            handle.close()
            break
        except urllib.error.HTTPError as exc:
            if exc.code in (429, 500, 502, 503) and attempt < 2:
                sleep_t = (2 ** attempt) + random.uniform(0, 1)
                log.warning("PMC %d for PMID=%s — retrying in %.1fs", exc.code, pmid, sleep_t)
                time.sleep(sleep_t)
            else:
                log.warning("PMC efetch failed for PMID=%s: %s", pmid, exc)
                return None
        except Exception as exc:
            log.warning("PMC efetch failed for PMID=%s: %s", pmid, exc)
            return None

    if isinstance(raw, str):
        raw = raw.encode("utf-8")
    if not raw or len(raw) < 200:
        log.warning("PMC returned empty response for PMID=%s", pmid)
        return None
    if len(raw) > MAX_RESPONSE_BYTES:
        log.warning(
            "PMC XML %d bytes > limit (%d) — skipping PMID=%s",
            len(raw),
            MAX_RESPONSE_BYTES,
            pmid,
        )
        return None
    _account_bytes(len(raw))

    parsed = _parse_jats_xml(raw)
    if not parsed:
        log.warning("JATS parse failed for PMID=%s", pmid)
        return None
    if parsed["word_count"] < 100:
        log.warning("PMC XML too short (%d words) for PMID=%s — skipping", parsed["word_count"], pmid)
        return None

    return {
        "pmid": pmid,
        "source": "pmc_xml",
        **parsed,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }


# ---------------------------------------------------------------------------
# Tier 2 — Unpaywall OA URL lookup
# ---------------------------------------------------------------------------


def fetch_unpaywall_url(doi: str) -> str | None:
    """Return the best OA URL from Unpaywall, or None."""
    domain = "api.unpaywall.org"
    url = f"https://api.unpaywall.org/v2/{doi}?email=research-tool@example.com"
    resp = None
    for attempt in range(3):
        rate_wait(domain)
        try:
            with httpx.Client(timeout=15, follow_redirects=True) as client:
                resp = client.get(url)
            if resp.status_code in (429, 500, 502, 503) and attempt < 2:
                sleep_t = (2 ** attempt) + random.uniform(0, 1)
                log.warning("Unpaywall %d for doi=%s — retrying in %.1fs", resp.status_code, doi, sleep_t)
                time.sleep(sleep_t)
                continue
            break
        except (httpx.TimeoutException, httpx.NetworkError) as exc:
            if attempt < 2:
                log.warning("Unpaywall network error for doi=%s: %s — retrying", doi, exc)
                time.sleep(2 ** attempt)
            else:
                log.warning("Unpaywall failed for doi=%s: %s", doi, exc)
                return None
    if resp is None or resp.status_code != 200:
        log.debug("Unpaywall %s for doi=%s", resp.status_code if resp else "no response", doi)
        return None
    try:
        data = resp.json()
        best = data.get("best_oa_location") or {}
        oa_url = best.get("url_for_pdf") or best.get("url")
        if oa_url:
            log.info("Unpaywall OA URL for doi=%s: %s", doi, oa_url)
        return oa_url
    except Exception as exc:
        log.warning("Unpaywall failed for doi=%s: %s", doi, exc)
        return None


# ---------------------------------------------------------------------------
# Tier 2/3 — HTML via curl-impersonate + trafilatura
# ---------------------------------------------------------------------------


def fetch_html_curl(url: str, pmid: str) -> str | None:
    """Fetch URL with curl-impersonate and extract body text.

    Returns extracted text (>= 2000 words) or None.
    """
    if not CURL_BIN:
        return None

    domain = _domain_of(url)
    rate_wait(domain)
    log.info("curl-impersonate: %s", url)

    with tempfile.NamedTemporaryFile(suffix=f"_{pmid}.html", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        result = subprocess.run(
            [
                CURL_BIN,
                "-s",
                "-L",
                "--max-time", "30",
                "--max-filesize", str(MAX_RESPONSE_BYTES),
                "-o", tmp_path,
                url,
            ],
            capture_output=True,
            timeout=45,
        )
        if result.returncode != 0:
            # curl exit 63 = max-filesize exceeded
            if result.returncode == 63:
                log.warning(
                    "Response > %d bytes — skipping %s",
                    MAX_RESPONSE_BYTES,
                    url,
                )
            else:
                log.debug("curl rc=%d for %s", result.returncode, url)
            return None

        # Double-check on-disk size before reading into memory
        size = Path(tmp_path).stat().st_size if Path(tmp_path).exists() else 0
        if size > MAX_RESPONSE_BYTES:
            log.warning("Downloaded %d bytes > limit — skipping %s", size, url)
            return None
        _account_bytes(size)

        raw = Path(tmp_path).read_bytes()
        if not raw:
            return None
        if _is_pdf(raw):
            log.info("PDF response — skipping %s", url)
            return None

        html = raw.decode("utf-8", errors="replace")
        if _is_blocked(html):
            log.info("Challenge/paywall page for %s", url)
            return None

        # Extract text: trafilatura → readability fallback → regex strip
        text: str | None = None
        if HAS_TRAFILATURA:
            text = trafilatura.extract(html, include_tables=False, favor_recall=True)
        if not text and HAS_READABILITY:
            doc = ReadabilityDoc(html)
            clean = doc.summary()
            text = re.sub(r"<[^>]+>", " ", clean)
            text = re.sub(r"\s+", " ", text).strip()
        if not text:
            text = re.sub(r"<[^>]+>", " ", html)
            text = re.sub(r"\s+", " ", text).strip()

        wc = _word_count(text or "")
        if wc < 2000:
            log.info("Too few words (%d) from %s — skipping", wc, url)
            return None
        if wc > MAX_FULLTEXT_WORDS:
            text = _truncate_to_word_limit(text)

        return text

    except subprocess.TimeoutExpired:
        log.warning("curl timeout for %s", url)
        return None
    except Exception as exc:
        log.warning("HTML fetch error for %s: %s", url, exc)
        return None
    finally:
        try:
            os.unlink(tmp_path)
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Per-paper fetch orchestrator
# ---------------------------------------------------------------------------


def process_paper(row: dict, dry_run: bool = False) -> dict:
    """Try all fetch tiers for one paper; return result dict.

    Result keys: pmid, status ('fetched'|'abstract_only'), source, data.
    """
    pmid = row["pmid"]
    pmc_id = (row.get("pmc_id") or "").strip()
    doi = (row.get("doi") or "").strip()
    title = row.get("title") or ""

    result: dict = {
        "pmid": pmid,
        "status": "abstract_only",
        "source": None,
        "data": None,
    }

    if dry_run:
        tiers: list[str] = []
        if pmc_id:
            tiers.append("pmc_xml")
        if doi:
            tiers.append("unpaywall")
            if CURL_BIN:
                tiers.append("doi_html")
        log.info("DRY-RUN PMID=%s — would try: %s", pmid, tiers or ["none"])
        # Report as potentially fetchable if any tier is available
        if tiers:
            result["status"] = "fetchable"
        return result

    # --- Tier 1: PMC XML ---
    if pmc_id:
        data = fetch_pmc_xml(pmid, pmc_id)
        if data and data.get("word_count", 0) >= 100:
            result.update(status="fetched", source="pmc_xml", data=data)
            return result

    # --- Tier 2: Unpaywall OA URL → curl-impersonate ---
    if doi and CURL_BIN:
        oa_url = fetch_unpaywall_url(doi)
        if oa_url:
            text = fetch_html_curl(oa_url, pmid)
            if text:
                wc = _word_count(text)
                data = {
                    "pmid": pmid,
                    "source": "unpaywall_html",
                    "title": title,
                    "abstract": "",
                    "sections": [{"name": "Full Text", "text": _strip_inline_citations(text)}],
                    "tables": [],
                    "figures": [],
                    "word_count": wc,
                    "fetched_at": datetime.now(timezone.utc).isoformat(),
                }
                result.update(status="fetched", source="html", data=data)
                return result

    # --- Tier 3: DOI landing page → curl-impersonate ---
    if doi and CURL_BIN:
        doi_url = f"https://doi.org/{doi}"
        text = fetch_html_curl(doi_url, pmid)
        if text:
            wc = _word_count(text)
            data = {
                "pmid": pmid,
                "source": "html",
                "title": title,
                "abstract": "",
                "sections": [{"name": "Full Text", "text": _strip_inline_citations(text)}],
                "tables": [],
                "figures": [],
                "word_count": wc,
                "fetched_at": datetime.now(timezone.utc).isoformat(),
            }
            result.update(status="fetched", source="html", data=data)
            return result

    log.info("All tiers failed for PMID=%s — abstract_only", pmid)
    return result


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------


def _update_paper(
    conn: sqlite3.Connection,
    pmid: str,
    status: str,
    source: str | None,
    word_count: int,
) -> None:
    conn.execute(
        """UPDATE papers
           SET fulltext_status = ?,
               fulltext_source = ?,
               fulltext_words  = ?
           WHERE pmid = ?""",
        (status, source, word_count, pmid),
    )


# ---------------------------------------------------------------------------
# Stats display
# ---------------------------------------------------------------------------


def _print_stats() -> None:
    """Print full-text fetch statistics to stdout."""
    if not DB_PATH.exists():
        click.echo("Error: database not found. Run `just setup` first.")
        return
    with sqlite3.connect(DB_PATH) as conn:
        total = conn.execute("SELECT COUNT(*) FROM papers").fetchone()[0]
        fetched = conn.execute(
            "SELECT COUNT(*) FROM papers WHERE fulltext_status = 'fetched'"
        ).fetchone()[0]
        abstract_only = conn.execute(
            "SELECT COUNT(*) FROM papers WHERE fulltext_status = 'abstract_only'"
        ).fetchone()[0]
        pending = total - fetched - abstract_only
        by_source = conn.execute(
            """SELECT fulltext_source, COUNT(*)
               FROM papers
               WHERE fulltext_status = 'fetched'
               GROUP BY fulltext_source"""
        ).fetchall()

    click.echo("Full-text fetch statistics:")
    click.echo(f"  total papers:   {total}")
    click.echo(f"  fetched:        {fetched}")
    click.echo(f"  abstract-only:  {abstract_only}")
    click.echo(f"  pending:        {pending}")
    if by_source:
        click.echo("  by source:")
        for src, cnt in by_source:
            click.echo(f"    {src or 'unknown'}: {cnt}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


@click.command()
@click.option(
    "--limit",
    default=50,
    show_default=True,
    help="Max papers to process (highest quality_score first).",
)
@click.option("--pmid", default=None, help="Process a single specific PMID.")
@click.option("--stats", is_flag=True, help="Show fetch statistics and exit.")
@click.option(
    "--dry-run",
    is_flag=True,
    help="Show what would be fetched without writing anything.",
)
def main(limit: int, pmid: str | None, stats: bool, dry_run: bool) -> None:
    """Fetch full text for papers in the research database."""
    if not DB_PATH.exists():
        click.echo(
            f"Error: database not found at {DB_PATH}. Run `just setup` first.",
            err=True,
        )
        sys.exit(1)

    if stats:
        _print_stats()
        return

    FULLTEXT_DIR.mkdir(parents=True, exist_ok=True)

    # Load candidate papers
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        if pmid:
            rows = conn.execute(
                "SELECT pmid, doi, pmc_id, title FROM papers WHERE pmid = ?",
                (pmid,),
            ).fetchall()
        else:
            rows = conn.execute(
                """SELECT pmid, doi, pmc_id, title
                   FROM papers
                   WHERE fulltext_status IS NULL
                   ORDER BY quality_score DESC
                   LIMIT ?""",
                (limit,),
            ).fetchall()

    papers = [dict(r) for r in rows]
    log.info("Loaded %d paper(s) from DB", len(papers))

    if not CURL_BIN:
        log.info(
            "curl-impersonate not found — HTML tiers disabled; PMC XML + Unpaywall only"
        )

    # Idempotency: skip papers whose JSON already exists
    to_fetch: list[dict] = []
    for p in papers:
        json_path = FULLTEXT_DIR / f"{p['pmid']}.json"
        if json_path.exists():
            log.info("Skipping PMID=%s — already fetched", p["pmid"])
        else:
            to_fetch.append(p)

    if not to_fetch:
        log.info("Nothing new to fetch — all papers already processed.")
        return

    mode = "DRY-RUN" if dry_run else "live"
    log.info("Fetching %d paper(s) [%s, workers=4]", len(to_fetch), mode)

    # Concurrent fetch — workers return results, DB/file writes on main thread
    results: list[dict] = []
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = {pool.submit(process_paper, p, dry_run): p for p in to_fetch}
        for future in as_completed(futures):
            p = futures[future]
            try:
                res = future.result()
                results.append(res)
            except Exception as exc:
                log.warning("Worker error for PMID=%s: %s", p["pmid"], exc)
                results.append(
                    {
                        "pmid": p["pmid"],
                        "status": "abstract_only",
                        "source": None,
                        "data": None,
                    }
                )

    # Dry-run: report only, no writes
    if dry_run:
        would_fetch = sum(1 for r in results if r["status"] == "fetchable")
        log.info(
            "DRY-RUN complete — would attempt %d/%d papers (with available tiers)",
            would_fetch,
            len(results),
        )
        return

    # Main-thread writes: JSON files + DB updates
    fetched_n = 0
    abstract_only_n = 0
    with sqlite3.connect(DB_PATH) as conn:
        for res in results:
            pmid_val = res["pmid"]
            status = res["status"]
            source = res.get("source")
            data = res.get("data")

            if status == "fetched" and data:
                json_path = FULLTEXT_DIR / f"{pmid_val}.json"
                json_path.write_text(
                    json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
                )
                wc = data.get("word_count", 0)
                _update_paper(conn, pmid_val, "fetched", source, wc)
                fetched_n += 1
                log.info(
                    "Saved PMID=%s  words=%d  source=%s", pmid_val, wc, source
                )
            else:
                _update_paper(conn, pmid_val, "abstract_only", None, 0)
                abstract_only_n += 1

    log.info(
        "Done — fetched=%d  abstract_only=%d  total=%d",
        fetched_n,
        abstract_only_n,
        fetched_n + abstract_only_n,
    )


if __name__ == "__main__":
    main()
