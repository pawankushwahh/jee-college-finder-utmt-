"""Data loader for COMEDK 2025 cutoffs.

Mirrors ``app/disha/data_loader.py`` in responsibilities: read the CSV, clean
programme names, derive institute tiers and brand scores from the data itself,
and expose a cached accessor that the recommender and stats_loader consume.

Key design choices (see § 4.12 of the spec):
  - Read only ``Closing_R1``; no dead ``range(1, 7)`` loop.
  - Validate ranks and log counts of skipped rows instead of silent ``continue``.
  - Warn if ``Opening_R1 != Closing_R1`` in a future dataset.
  - Derive the quota list from the data, not hard-coded.
  - Split the ``(4 Years, Bachelor of Technology)`` suffix into ``branch`` +
    ``degree``, keeping the original ``program`` string intact for compat.
  - Compute institute tiers from median GM cutoff (§ 4.4).
"""

from __future__ import annotations

import csv
import logging
import re
import statistics
from collections import defaultdict
from typing import Dict, List, Optional

from .config import settings
from .states import classify_branch

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# PDF line-wrap repairs (§ 2)
# ---------------------------------------------------------------------------
_NAME_REPAIRS: Dict[str, str] = {
    "Bio- technology": "Bio-Technology",
    "Computer & Communi-cation Engineering": "Computer & Communication Engineering",
    "Electronics & Telecommunicati on Engineering": "Electronics & Telecommunication Engineering",
}

# Bengaluru metro detection keywords (parallel to JEE's METRO_CITIES)
_BENGALURU_KEYWORDS = (
    "bengaluru", "bangalore", "bengaluru rural",
)


def _safe_float(val: Optional[str]) -> Optional[float]:
    if not val or not val.strip():
        return None
    try:
        return float(val.strip())
    except ValueError:
        return None


def _repair_program_name(name: str) -> str:
    """Fix known PDF line-wrap artefacts in programme names."""
    for bad, good in _NAME_REPAIRS.items():
        name = name.replace(bad, good)
    return name


_DEGREE_PATTERN = re.compile(r"\s*\((\d+ Years?,\s*.+?)\)\s*$")


def _split_branch_degree(program: str) -> tuple[str, str]:
    """Split "Civil Engineering (4 Years, Bachelor of Technology)" into
    ``("Civil Engineering", "4 Years, Bachelor of Technology")``.

    Returns ``(program, "")`` if the suffix is absent.
    """
    m = _DEGREE_PATTERN.search(program)
    if m:
        branch = program[:m.start()].strip()
        degree = m.group(1).strip()
        return branch, degree
    return program, ""


def _is_metro(institute: str) -> bool:
    """Flag institutes in the Bengaluru cluster (parallel to JEE's METRO_CITIES)."""
    inst_lower = institute.lower()
    return any(kw in inst_lower for kw in _BENGALURU_KEYWORDS)


# ---------------------------------------------------------------------------
# Institute tiering (§ 4.4)
# ---------------------------------------------------------------------------
# Derive from median GM cutoff.  Lower median → more competitive → higher tier.
#
#  Percentile  | brand_score | tier
#  top 5 %     |  1.00       | elite
#  to 20 %     |  0.88       | top
#  to 50 %     |  0.78       | strong
#  to 80 %     |  0.68       | mid
#  rest        |  0.55       | emerging
#
# Percentile is rank-based: position (n-1-i)/(n-1) * 100 so the institute
# with the lowest median cutoff gets 100 % and the highest gets 0 %.

_TIER_TABLE = [
    (95, 1.00, "elite"),
    (80, 0.88, "top"),
    (50, 0.78, "strong"),
    (20, 0.68, "mid"),
    (0,  0.55, "emerging"),
]


def _compute_tiers(programs: List[dict]) -> Dict[str, tuple[float, str]]:
    """Return ``{institute: (brand_score, tier)}`` derived from median GM cutoff."""
    inst_cutoffs: Dict[str, List[float]] = defaultdict(list)
    for p in programs:
        if p["quota"] == "GM":
            inst_cutoffs[p["institute"]].append(p["cutoff_rank"])

    # Sort institutes by median GM cutoff (ascending = most competitive first)
    medians = {inst: statistics.median(cuts) for inst, cuts in inst_cutoffs.items()}
    sorted_insts = sorted(medians.keys(), key=lambda i: medians[i])
    n = len(sorted_insts)

    result: Dict[str, tuple[float, str]] = {}
    for i, inst in enumerate(sorted_insts):
        pctile = (n - 1 - i) / max(1, n - 1) * 100
        for threshold, score, tier in _TIER_TABLE:
            if pctile >= threshold:
                result[inst] = (score, tier)
                break
    return result


# ---------------------------------------------------------------------------
# Programme competitiveness percentile
# ---------------------------------------------------------------------------
# The institute tier above has only five distinct values, which is too coarse to
# order a shortlist: at rank 60,000 every "elite" row outranked every "top" row,
# so a good college's weakest branch was shown above a strong college's CSE.
#
# A programme's own cutoff is the sharpest demand signal a single-cutoff dataset
# gives us — a programme closing at 692 is in far higher demand than one closing
# at 111,800.  This converts the cutoff into a percentile *within its own quota*
# (GM cutoffs are not comparable to KKR cutoffs, so the pools are ranked
# separately):
#
#     1.0 → lowest cutoff in the quota  (most competitive / most in demand)
#     0.0 → highest cutoff in the quota (least competitive)
#
# Ties share a percentile, so two programmes closing at the same rank are never
# ordered arbitrarily against each other by this key.
def _compute_competitiveness(programs: List[dict]) -> None:
    """Attach a ``competitiveness`` percentile in [0, 1] to each programme.

    Computed per quota.  Mutates ``programs`` in place.
    """
    by_quota: Dict[str, List[dict]] = defaultdict(list)
    for p in programs:
        by_quota[p["quota"]].append(p)

    for rows in by_quota.values():
        distinct = sorted({r["cutoff_rank"] for r in rows})
        denom = max(1, len(distinct) - 1)
        position = {c: i for i, c in enumerate(distinct)}
        for r in rows:
            r["competitiveness"] = 1.0 - (position[r["cutoff_rank"]] / denom)


# ---------------------------------------------------------------------------
# KKR gap computation (§ 4.8)
# ---------------------------------------------------------------------------
def _compute_kkr_gaps(programs: List[dict]) -> Dict[tuple[str, str], float]:
    """Return ``{(institute, branch): kkr_cutoff - gm_cutoff}`` for every pair
    present in both GM and KKR."""
    gm: Dict[tuple[str, str], float] = {}
    kkr: Dict[tuple[str, str], float] = {}
    for p in programs:
        key = (p["institute"], p["branch"])
        if p["quota"] == "GM":
            gm[key] = p["cutoff_rank"]
        elif p["quota"] == "KKR":
            kkr[key] = p["cutoff_rank"]
    gaps: Dict[tuple[str, str], float] = {}
    for key in gm.keys() & kkr.keys():
        gaps[key] = kkr[key] - gm[key]
    return gaps


# ---------------------------------------------------------------------------
# Main load function
# ---------------------------------------------------------------------------
def load_comedk_programs() -> List[dict]:
    """Load COMEDK 2025 cutoff data from CSV.

    Each dict has keys: ``institute``, ``program``, ``branch``, ``degree``,
    ``branch_family``, ``quota``, ``cutoff_rank``, ``competitiveness``,
    ``brand_score``, ``brand_tier``, ``is_metro``, ``kkr_gap``.
    """
    csv_path = settings.resolved_csv_path
    if not csv_path.exists():
        logger.error("COMEDK data file not found: %s", csv_path)
        return []

    raw_programs: List[dict] = []
    skipped = 0
    opening_mismatch_count = 0

    with open(csv_path, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row_num, row in enumerate(reader, start=2):  # header is row 1
            institute = row.get("Institute", "").strip()
            raw_program = row.get("Academic Program Name", "").strip()
            quota = row.get("Quota", "").strip()

            if not institute or not raw_program or not quota:
                skipped += 1
                logger.debug("Row %d: missing institute/program/quota, skipping", row_num)
                continue

            closing = _safe_float(row.get("Closing_R1"))
            if closing is None or closing <= 0:
                skipped += 1
                logger.debug("Row %d: invalid Closing_R1=%r, skipping", row_num, row.get("Closing_R1"))
                continue

            # Warn if Opening_R1 differs from Closing_R1 (the model assumes
            # they are equal in COMEDK 2025; a future dataset might differ).
            opening = _safe_float(row.get("Opening_R1"))
            if opening is not None and opening != closing:
                opening_mismatch_count += 1

            # Repair known PDF artefacts in programme name
            program = _repair_program_name(raw_program)

            # Split "Civil Engineering (4 Years, Bachelor of Technology)"
            branch, degree = _split_branch_degree(program)
            branch_family = classify_branch(program)

            raw_programs.append({
                "institute": institute,
                "program": program,         # original (repaired) full string — compat
                "branch": branch,           # short name without degree suffix
                "degree": degree,
                "branch_family": branch_family,
                "quota": quota,
                "cutoff_rank": closing,
            })

    if skipped:
        logger.warning("COMEDK loader: skipped %d malformed rows", skipped)
    if opening_mismatch_count:
        logger.warning(
            "COMEDK loader: %d rows have Opening_R1 != Closing_R1.  "
            "The model assumes they are equal.  If this dataset has diverged, "
            "the recommender's single-point cutoff assumption may need review.",
            opening_mismatch_count,
        )
    logger.info("COMEDK loader: loaded %d programmes from %s", len(raw_programs), csv_path.name)

    # ── Derive institute tiers from the data ─────────────────────────────
    tiers = _compute_tiers(raw_programs)

    # ── Compute KKR gaps ─────────────────────────────────────────────────
    kkr_gaps = _compute_kkr_gaps(raw_programs)

    # ── Per-quota competitiveness percentile (ordering signal) ───────────
    _compute_competitiveness(raw_programs)

    # ── Enrich each programme dict ───────────────────────────────────────
    for p in raw_programs:
        brand_score, brand_tier = tiers.get(p["institute"], (0.55, "emerging"))
        p["brand_score"] = brand_score
        p["brand_tier"] = brand_tier
        p["is_metro"] = _is_metro(p["institute"])
        p["kkr_gap"] = kkr_gaps.get((p["institute"], p["branch"]))

    return raw_programs


# ---------------------------------------------------------------------------
# Cached accessor (consumed by recommender + stats_loader)
# ---------------------------------------------------------------------------
_cached_programs: Optional[List[dict]] = None
_cached_quotas: Optional[List[str]] = None


def get_programs() -> List[dict]:
    """Cached accessor for COMEDK programmes."""
    global _cached_programs
    if _cached_programs is None:
        _cached_programs = load_comedk_programs()
    return _cached_programs


def get_quotas() -> List[str]:
    """Unique quotas derived from the loaded data (not hard-coded)."""
    global _cached_quotas
    if _cached_quotas is None:
        _cached_quotas = sorted({p["quota"] for p in get_programs()})
    return _cached_quotas
