"""Shared quality scoring for the research database.

Used by search_pubmed.py (initial score) and enrich_citations.py (enriched score).

Tuned for basic / translational biology research (Miller-Jensen-style lab work:
immunology, single-cell genomics, gene regulation, macrophage biology).
Clinical-medicine-only tiers (NEJM, JAMA family) are kept for translational
relevance but downweighted vs. the medical sibling repo.
"""

import re

# ---------------------------------------------------------------------------
# Journal tiers — approximate impact / readership bands
# Tier 1: the handful every cell biologist reads
# Tier 2: top broad-discipline + top subspecialty
# Tier 3: solid specialty + open-access flagships
# Unlisted journals get 0 (no bonus); citations still drive ranking
# ---------------------------------------------------------------------------

_TIER_1 = {
    "nature",
    "science",
    "cell",
    "nature medicine",
    "nature reviews molecular cell biology",
    "nature reviews immunology",
    "nature reviews cancer",
    "nature reviews genetics",
    "nature reviews microbiology",
    "nature reviews drug discovery",
    "the new england journal of medicine",
}

_TIER_2 = {
    # Cell Press flagships
    "immunity",
    "cancer cell",
    "cell host & microbe",
    "cell stem cell",
    "molecular cell",
    "developmental cell",
    "cell metabolism",
    "cell systems",
    "cell reports",
    "cell reports medicine",
    "cell reports methods",
    "trends in immunology",
    "trends in cell biology",
    "trends in genetics",
    "trends in molecular medicine",
    # Nature subfamily
    "nature immunology",
    "nature cell biology",
    "nature methods",
    "nature biotechnology",
    "nature cancer",
    "nature microbiology",
    "nature genetics",
    "nature communications",
    "nature chemical biology",
    "nature structural & molecular biology",
    # Other broad top-tier
    "elife",
    "embo journal",
    "the embo journal",
    "embo molecular medicine",
    "embo reports",
    "pnas",
    "proceedings of the national academy of sciences",
    "proceedings of the national academy of sciences of the united states of america",
    "genes & development",
    "current biology",
    # Immunology top
    "journal of experimental medicine",
    "the journal of experimental medicine",
    "science immunology",
    "science translational medicine",
    "science advances",
    # Translational
    "journal of clinical investigation",
    "the journal of clinical investigation",
    "blood",
    "nature reviews clinical oncology",
    "lancet",
    "the lancet",
}

_TIER_3 = {
    # Solid immunology & cell biology
    "journal of immunology",
    "the journal of immunology",
    "journal of cell biology",
    "the journal of cell biology",
    "molecular biology of the cell",
    "molecular and cellular biology",
    "mucosal immunology",
    "european journal of immunology",
    "frontiers in immunology",
    "frontiers in cell and developmental biology",
    "mbio",
    "plos biology",
    "plos pathogens",
    "plos genetics",
    "plos computational biology",
    "plos one",
    "bmc biology",
    "bmc genomics",
    # Genomics / methods
    "genome biology",
    "genome research",
    "nucleic acids research",
    "bioinformatics",
    "briefings in bioinformatics",
    # Cancer specialty
    "cancer research",
    "clinical cancer research",
    "cancer immunology research",
    "british journal of cancer",
    "oncogene",
    # Translational mid
    "jci insight",
    "cancer discovery",
    "journal of leukocyte biology",
    "blood advances",
}

# Points per tier
_TIER_POINTS = {1: 40, 2: 25, 3: 12}


def journal_tier_score(journal: str | None) -> int:
    """Return quality points based on journal name."""
    if not journal:
        return 0
    j = journal.strip().lower()
    # Also try without "the " prefix
    j_no_the = re.sub(r"^the\s+", "", j)
    for name in (j, j_no_the):
        if name in _TIER_1:
            return _TIER_POINTS[1]
        if name in _TIER_2:
            return _TIER_POINTS[2]
        if name in _TIER_3:
            return _TIER_POINTS[3]
    return 0


# ---------------------------------------------------------------------------
# Publication type weighting
# ---------------------------------------------------------------------------

# Patterns matched case-insensitively against pub_types JSON strings.
# Biology basic-research has different signal vs. clinical medicine:
# we weight meta-analyses / systematic reviews high (they synthesize a field),
# reviews moderately (community knows the author), and case reports at 0.
_PUB_TYPE_SCORES: list[tuple[str, int]] = [
    ("meta-analysis", 25),
    ("systematic review", 20),
    ("practice guideline", 15),
    ("guideline", 12),
    ("randomized controlled trial", 10),
    ("clinical trial, phase iii", 10),
    ("clinical trial, phase ii", 7),
    ("clinical trial", 5),
    ("review", 10),
    ("comparative study", 3),
    ("observational study", 2),
    ("multicenter study", 2),
    # Case reports get 0 (default)
]


def pub_type_score(pub_types_json: str | None) -> int:
    """Return quality points based on publication types. Takes best match."""
    if not pub_types_json:
        return 0
    pt_lower = pub_types_json.lower()
    for pattern, points in _PUB_TYPE_SCORES:
        if pattern in pt_lower:
            return points
    return 0


# ---------------------------------------------------------------------------
# Composite quality score
# ---------------------------------------------------------------------------


def _citations_per_year(citations: int, pub_year: int | None) -> float:
    """Normalize citations by paper age. Recent papers aren't penalized."""
    if not pub_year or pub_year < 1950:
        return float(min(citations, 500))
    from datetime import date
    current_year = date.today().year
    age = max(current_year - pub_year, 0)
    if age <= 1:
        # Paper is <1 year old — don't penalize for low citations.
        # Give it credit for whatever it has, plus a "too new to tell" bonus.
        return float(citations) * 5.0 + 10.0
    # Citations per year, scaled up so it's comparable to raw counts.
    # A paper getting 20 cites/year is excellent in basic biology too.
    return min(citations / age, 100.0) * 5.0


def compute_quality_score(
    *,
    citations: int = 0,
    influential_citations: int = 0,
    is_open_access: bool | int = False,
    has_pmc: bool | int = False,
    has_abstract: bool | int = False,
    journal: str | None = None,
    pub_types_json: str | None = None,
    pub_year: int | None = None,
) -> int:
    """Compute composite quality score.

    Components:
      - Citations/year (age-normalized): up to 500
      - Influential citations: influential * 5
      - Journal tier: 40 / 25 / 12 / 0
      - Publication type: up to 25 (meta-analysis), 0 (case report)
      - Open access: +10
      - Has PMC full text: +5
      - Has abstract: +5
    """
    score = _citations_per_year(max(citations, 0), pub_year)
    score += max(influential_citations, 0) * 5
    score += journal_tier_score(journal)
    score += pub_type_score(pub_types_json)
    score += 10 if is_open_access else 0
    score += 5 if has_pmc else 0
    score += 5 if has_abstract else 0
    return int(score)
