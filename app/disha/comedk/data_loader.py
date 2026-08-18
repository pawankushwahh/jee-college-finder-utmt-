"""Data loader for COMEDK 2025 cutoffs.

Loads ``comedk_2025_all_rounds.csv`` — the mock round, all four counselling
rounds and the pre-counselling seat matrix, compiled from the six official PDFs
by ``scripts/build_comedk_dataset.py``.  See ``docs/DATA_PIPELINE.md`` for where
the source documents come from and how to rebuild this file next year.

This replaced ``comedk_2025.csv``, which held a single ``Closing_R1`` column
per programme.  That file did not survive being checked against the official
documents:

  * its ``Opening_R1`` was a verbatim copy of ``Closing_R1`` on all 637 rows,
    so the opening rank it appeared to publish was not data;
  * 48% of its closing ranks appear nowhere in any of the five official cut-off
    PDFs for the matching college and quota, and the values that *do* match are
    spread across rounds 1-4 and the mock, so it was not a snapshot of any one
    round;
  * it covered 101 of 150 colleges and 46 of 69 courses.

The values here are parsed from the PDFs and reconcile to COMEDK's own printed
seat total (26,827 = 22,813 GM + 4,014 KKR).

Structure mirrors ``app/disha/kcet/data_loader.py``: one record per (college,
course, category) carrying **every** round's cut-off, with ``resolve_rank``
(shared, in ``app/disha/core/rounds.py``) picking the single number the
recommender compares a rank against.  Nothing is collapsed at read time, so
choosing a round stays a code-level decision rather than something baked into
the dataset.  Round selection, CSV number parsing, the competitiveness
percentile and the per-strategy cache are all shared with KCET.

What stays COMEDK-specific is what COMEDK's own record requires: the mock round
(published, but allotted no seat, so never selectable as a cut-off), vacant rows
that never filled in any round, the KKR-vs-GM gap, and institute tiers.

Key design choices retained from the previous loader:
  - Validate ranks and log counts of skipped rows instead of silent ``continue``.
  - Derive the quota list from the data, not hard-coded.
  - Compute institute tiers from median GM cutoff (§ 4.4).
"""

from __future__ import annotations

import csv
import logging
import statistics
from collections import defaultdict
from typing import Dict, List, Optional

from ..core import scoring
# Round selection is exam-agnostic and lives in core; the `STRATEGY_*` names are
# re-exported so this module keeps the vocabulary its config.py documents.
from ..core.rounds import (  # noqa: F401  (re-exported for callers)
    STRATEGY_FIRST,
    STRATEGY_LAST,
    STRATEGY_MAX,
    StrategyCache,
    parse_int,
    parse_number,
    ranks_by_round,
    resolve_rank as _resolve_rank,
    round_columns,
)
from .config import settings
from .states import classify_branch

logger = logging.getLogger(__name__)


# Bengaluru metro detection keywords (parallel to JEE's METRO_CITIES)
_BENGALURU_KEYWORDS = (
    "bengaluru", "bangalore", "bengaluru rural",
)


def _is_metro(institute: str) -> bool:
    """Flag institutes in the Bengaluru cluster (parallel to JEE's METRO_CITIES)."""
    inst_lower = institute.lower()
    return any(kw in inst_lower for kw in _BENGALURU_KEYWORDS)


# ---------------------------------------------------------------------------
# The mock round
# ---------------------------------------------------------------------------
# ``core.rounds.ROUND_COLUMN`` matches ``closing_rank_r<N>`` and therefore does
# not match this column, which is exactly the intent: the mock round is a
# simulation published before counselling opened and allotted no seat, so it
# must never be selectable as "the" cut-off.  It stays in the dataset as a
# demand signal and is exposed separately as ``mock_rank``.
_MOCK_COLUMN = "closing_rank_mock"

# COMEDK-specific caveat on round selection, because the rounds are not
# category-symmetric: GM ran in rounds 1, 3 and 4 while KKR ran only in rounds 1
# and 2.  So a GM ``max`` is taken over three rounds and a KKR ``max`` over two.
# That is the published record, not an artefact — but it does mean GM and KKR
# cut-offs in this view come from different round sets, and anything comparing
# the two (see ``_compute_kkr_gaps``) is comparing across that boundary.  KCET's
# asymmetry is negligible by comparison — 47 of its 48 category codes publish
# all three rounds (only 1KH stops after round 2) — which is why its bucketing
# can read a range across the rounds and COMEDK's cannot.


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
# A programme's own cutoff is the sharpest demand signal this dataset gives us.
# This converts the cutoff into a percentile *within its own quota* (GM cutoffs
# are not comparable to KKR cutoffs, so the pools are ranked separately):
#
#     1.0 → lowest cutoff in the quota  (most competitive / most in demand)
#     0.0 → highest cutoff in the quota (least competitive)
#
# Ties share a percentile (``TIES_DENSE``), so two programmes closing at the same
# rank are never ordered arbitrarily against each other by this key.  KCET makes
# the opposite choice for its own reasons — see its ``_compute_quality_scores``.
def _compute_competitiveness(programs: List[dict]) -> None:
    """Attach a ``competitiveness`` percentile in [0, 1] to each programme.

    Computed per quota.  Mutates ``programs`` in place.
    """
    scores = scoring.competitiveness_by_group(
        programs,
        group_of=lambda p: p["quota"],
        value_of=lambda p: p["cutoff_rank"],
        ties=scoring.TIES_DENSE,
    )
    for program, score in zip(programs, scores):
        program["competitiveness"] = score


# ---------------------------------------------------------------------------
# KKR gap computation (§ 4.8)
# ---------------------------------------------------------------------------
def _compute_kkr_gaps(programs: List[dict]) -> Dict[tuple[str, str], float]:
    """Return ``{(institute, branch): kkr_cutoff - gm_cutoff}`` for every pair
    present in both GM and KKR.

    Both sides are whichever rank the active strategy selected, so under the
    default ``max`` this compares a GM maximum over rounds 1/3/4 against a KKR
    maximum over rounds 1/2 — see ``_resolve_rank``.  Keyed by (institute,
    branch) with one row per quota after resolution, so there is no round-order
    overwrite: each key is written exactly once per quota.
    """
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
def load_comedk_programs(round_strategy: object = None) -> List[dict]:
    """Load COMEDK 2025 cutoff data from the all-rounds CSV.

    Each dict has keys: ``institute``, ``college_code``, ``program``,
    ``branch``, ``degree``, ``course_code``, ``branch_family``, ``quota``,
    ``cutoff_rank``, ``cutoff_by_round``, ``mock_rank``, ``total_seats``,
    ``category_seats``, ``tuition_fee``, ``other_fee``, ``total_fee``,
    ``competitiveness``, ``brand_score``, ``brand_tier``, ``is_metro``,
    ``kkr_gap``.
    """
    strategy = round_strategy if round_strategy is not None else settings.round_strategy

    csv_path = settings.resolved_csv_path
    if not csv_path.exists():
        logger.error("COMEDK data file not found: %s", csv_path)
        return []

    raw_programs: List[dict] = []
    skipped = 0
    vacant = 0
    absent_in_round = 0

    with open(csv_path, mode="r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        columns = round_columns(reader.fieldnames)
        if not columns:
            logger.error(
                "COMEDK data file has no closing_rank_r<N> columns: %s", csv_path
            )
            return []

        for row_num, row in enumerate(reader, start=2):  # header is row 1
            institute = (row.get("college_name") or "").strip()
            program = (row.get("course_name") or "").strip()
            quota = (row.get("category") or "").strip().upper()

            if not institute or not program or not quota:
                skipped += 1
                logger.debug("Row %d: missing college/course/category, skipping", row_num)
                continue

            # Non-positive ranks are dropped as well as blanks: a COMEDK row can
            # carry a 0 where the source document printed no allotment, and a
            # "cut-off of 0" would otherwise read as the most competitive
            # programme in the dataset.  A COMEDK data rule, so it stays here
            # rather than in the shared reader.
            by_round = {
                round_no: rank
                for round_no, rank in ranks_by_round(row, columns).items()
                if rank > 0
            }

            if not by_round:
                # Seats existed and never filled in any round.  Carried in the
                # CSV as a vacancy signal, but there is no cut-off here to
                # compare a rank against, so it cannot be recommended.
                vacant += 1
                continue

            cutoff = _resolve_rank(by_round, strategy)
            if cutoff is None:
                # Only reachable for an int strategy: this programme published
                # no cut-off in the requested round.  Not malformed — it simply
                # did not allot then, so it drops out of that round's view.
                absent_in_round += 1
                continue

            raw_programs.append({
                "institute": institute,
                "college_code": (row.get("college_code") or "").strip(),
                "program": program,      # full course name — compat key
                "branch": program,       # COMEDK course names carry no degree suffix
                "degree": "",
                "course_code": (row.get("course_code") or "").strip(),
                "branch_family": classify_branch(program),
                "quota": quota,
                "cutoff_rank": cutoff,
                "cutoff_by_round": tuple(sorted(by_round.items())),
                "mock_rank": parse_number(row.get(_MOCK_COLUMN)),
                "total_seats": parse_int(row.get("total_seats")),
                "category_seats": parse_int(row.get("category_seats")),
                "tuition_fee": parse_int(row.get("tuition_fee")),
                "other_fee": parse_int(row.get("other_fee")),
                "total_fee": parse_int(row.get("total_fee")),
            })

    if skipped:
        logger.warning("COMEDK loader: skipped %d malformed rows", skipped)
    if absent_in_round:
        logger.info(
            "COMEDK loader: %d programmes published no cut-off in round %s and "
            "are excluded from that view",
            absent_in_round, strategy,
        )
    if vacant:
        logger.info(
            "COMEDK loader: %d (college, course, category) rows had seats but no "
            "cut-off in any round — vacant throughout counselling, not recommendable",
            vacant,
        )
    logger.info(
        "COMEDK loader: loaded %d programmes from %s (round strategy: %s)",
        len(raw_programs), csv_path.name, strategy,
    )

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
# Cached accessors (consumed by recommender + stats_loader)
# ---------------------------------------------------------------------------
# One built view per strategy — see ``core.rounds.StrategyCache``.
_programs = StrategyCache(load_comedk_programs, lambda: settings.round_strategy)
_cached_quotas: Optional[List[str]] = None


def get_programs(round_strategy: object = None) -> List[dict]:
    """Cached accessor for COMEDK programmes.

    Defaults to ``settings.round_strategy``.  Pass ``"last"``, ``"first"``, or
    an ``int`` round number to get that view instead — e.g. ``get_programs(1)``
    answers "what would round 1 alone have said?".  Every programme carries its
    full round-wise history in ``cutoff_by_round`` regardless of strategy.
    """
    return _programs.get(round_strategy)


def get_quotas() -> List[str]:
    """Unique quotas derived from the loaded data (not hard-coded)."""
    global _cached_quotas
    if _cached_quotas is None:
        _cached_quotas = sorted({p["quota"] for p in get_programs()})
    return _cached_quotas


def get_available_rounds() -> List[int]:
    """Every round number present in the dataset, ascending."""
    rounds: set = set()
    for program in get_programs():
        rounds.update(number for number, _ in program["cutoff_by_round"])
    return sorted(rounds)
