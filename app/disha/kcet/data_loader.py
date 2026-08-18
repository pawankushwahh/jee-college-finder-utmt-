"""Data loading for the KCET engine.

Loads ``kcet_2025_all_rounds.csv`` — all three KEA rounds, both seat pools,
compiled from the official cut-off PDFs by ``scripts/build_kcet_dataset.py``.
See ``docs/DATA_PIPELINE.md`` for where the source documents come from and how
to rebuild this file next year.

This replaced ``kcet_2025.csv``, which held round 1 and the Rest-of-Karnataka
pool only, and whose ``course_name`` column was corrupted by an extraction that
did not rejoin course names wrapped across physical lines in the PDF. The rank
*values* in that file were correct — all 4,543 ``(college, category)`` rank
multisets matched the re-parse exactly — so this change adds data and fixes
names without restating any rank the engine previously served for round 1.

One ``KcetProgram`` is built per (college, course, category), with:

  * branch tags from ``classify_kcet_branch`` (states.py),
  * a per-category quality percentile, used both to order results within a
    bucket and as the closest thing this dataset has to a "brand" signal —
    there is no authoritative tier list of Karnataka engineering colleges to
    hard-code the way JEE's IIT/NIT tiers are public knowledge, so competitive
    demand (this row's cutoff relative to every other row in the same
    seat_category) stands in for it, same reasoning as COMEDK's quality score.

Round selection, CSV number parsing, the percentile itself and the per-strategy
cache are shared with COMEDK via ``app/disha/core/``. What stays KCET-specific
is what KEA's counselling rules require: the observed round range that drives
bucketing, the upward band imputation for the 26% of programmes that published
only one round, and the 371(j) seat-pool category codes.
"""

from __future__ import annotations

import csv
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

from ..core import scoring
# Round selection is exam-agnostic and lives in core; re-exported here because
# `STRATEGY_*` names this module's callers (and tests) already import from it.
from ..core.rounds import (  # noqa: F401  (re-exported for callers)
    DEFAULT_ROUND_STRATEGY,
    STRATEGY_FIRST,
    STRATEGY_LAST,
    STRATEGY_MAX,
    StrategyCache,
    ranks_by_round,
    resolve_rank as _resolve_rank,
    round_columns,
)
from .config import settings
from .states import classify_kcet_branch, describe_category

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class KcetProgram:
    institute: str
    college_code: str
    program: str
    seat_category: str
    seat_category_label: str
    # Float, not int: KEA publishes fractional cut-offs (76553.5, 15223.875).
    # The previous loader coerced these with int(float(v)), silently truncating
    # 2,366 of them.
    closing_rank: float
    # Every round this programme published a cut-off for, as ((round, rank), …)
    # ascending by round. `closing_rank` above is whichever of these the active
    # strategy selected.
    #
    # Kept rather than discarded so a round-specific view — "what would round 1
    # alone have said?" — is a pure in-memory question. A tuple, not a dict, so
    # the frozen dataclass stays hashable.
    closing_rank_by_round: Tuple[Tuple[int, float], ...] = ()
    # The range of ranks actually admitted across the rounds — the tough end
    # (earliest round, 99.3% of the time) and the loose end (latest, 98.0%).
    # These drive bucketing; see config.use_observed_range.
    rank_low: float = 0.0
    rank_high: float = 0.0
    # True when the programme published only one round, so rank_high is an
    # estimate rather than an observation. 26% of programmes, but very unevenly
    # spread: 4% of GM rows against 54-62% of some 371(j) categories.
    band_imputed: bool = False
    tags: Set[str] = field(default_factory=frozenset)
    quality_score: float = 0.0  # 0-10, higher = more competitive (lower cutoff)

    @property
    def band_width(self) -> float:
        return max(0.0, self.rank_high - self.rank_low)

    def rank_in_round(self, round_no: int) -> Optional[float]:
        """This programme's published cut-off in one round, or None if it did
        not allot a seat that round."""
        for number, rank in self.closing_rank_by_round:
            if number == round_no:
                return rank
        return None

    @property
    def rounds(self) -> Tuple[int, ...]:
        return tuple(number for number, _ in self.closing_rank_by_round)


def _load_raw_rows() -> List[dict]:
    """Read the CSV into one record per (college, course, category), keeping
    **every** round's cut-off.

    The file is one row per programme with a column per round
    (``closing_rank_r1``, ``closing_rank_r2``, …); a blank cell means the
    programme allotted no seat that round, so KEA published no cut-off for it.

    Nothing is collapsed here — the complete published record is carried into
    memory so that choosing a round stays a code-level decision rather than
    something baked into the dataset. ``_resolve_rank`` is where a single number
    gets picked.

    Seat pools need no special handling: the 371(j) codes are disjoint from the
    Rest-of-Karnataka codes (``GMH`` vs ``GM``), so they never collide in this
    key and a category code identifies its own pool.
    """
    csv_path = settings.resolved_csv_path
    if not csv_path.exists():
        logger.error("KCET data file not found: %s", csv_path)
        return []

    rows: List[dict] = []
    skipped = 0
    with open(csv_path, mode="r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        columns = round_columns(reader.fieldnames)
        if not columns:
            logger.error(
                "KCET data file has no closing_rank_r<N> columns: %s", csv_path
            )
            return []

        for row in reader:
            institute = (row.get("college_name") or "").strip()
            college_code = (row.get("college_code") or "").strip()
            program = (row.get("course_name") or "").strip()
            seat_category = (row.get("category") or "").strip().upper()

            by_round = ranks_by_round(row, columns)

            if not institute or not program or not seat_category or not by_round:
                skipped += 1
                continue

            rows.append(
                {
                    "institute": institute,
                    "college_code": college_code or institute,
                    "program": program,
                    "seat_category": seat_category,
                    "by_round": by_round,
                }
            )

    if skipped:
        logger.warning("KCET loader skipped %d unusable rows", skipped)
    return rows


def _compute_quality_scores(rows: List[dict]) -> List[float]:
    """Quality score per row, on a 0-10 scale, aligned to ``rows``.

    KCET has no brand signal to blend in — there is no authoritative tier list
    of Karnataka colleges the way JEE's IIT/NIT tiers are public knowledge — so
    competitive demand carries the whole score on its own. COMEDK blends the
    same percentile 70/30 with a data-derived institute tier; that is the
    exam-specific half of the decision and it lives in COMEDK's loader.

    Grouped by ``seat_category``: a GM cutoff and an STK cutoff are not on the
    same scale, so ranking across categories would be meaningless.

    Ordinal ties, unlike COMEDK's dense ones. A single KCET category holds
    thousands of rows, so sharing a percentile between equal cut-offs would
    compress the scale where the data is densest.
    """
    return [
        round(10.0 * score, 2)
        for score in scoring.competitiveness_by_group(
            rows,
            group_of=lambda row: row["seat_category"],
            value_of=lambda row: row["closing_rank"],
            ties=scoring.TIES_ORDINAL,
        )
    ]


def _impute_high(low: float) -> float:
    """Estimate the loose end for a programme that published only one round.

    The known value is the *tight* end (95% of such rows publish only round 1),
    so the band extends upward from it by the median widening measured on
    multi-round programmes in the same bracket. See
    ``settings.band_imputation_ratios`` for why this is an estimate rather than
    a measurement.
    """
    for upper, ratio in settings.band_imputation_ratios:
        if low < upper:
            return low * (1.0 + ratio)
    return low


def _observed_range(by_round: Dict[int, float]) -> Tuple[float, float, bool]:
    """(tough end, loose end, imputed?) for one programme."""
    values = list(by_round.values())
    low, high = min(values), max(values)
    if len(by_round) > 1 and high > low:
        return low, high, False
    return low, _impute_high(low), True


def _build_programs(strategy: object) -> List[KcetProgram]:
    resolved: List[dict] = []
    for row in _load_raw_rows():
        rank = _resolve_rank(row["by_round"], strategy)
        if rank is None:
            # Only reachable for an int strategy: this programme published no
            # cut-off in the requested round.
            continue
        low, high, imputed = _observed_range(row["by_round"])
        resolved.append(
            {**row, "closing_rank": rank, "rank_low": low,
             "rank_high": high, "band_imputed": imputed}
        )

    # Recomputed against whichever ranks this strategy selected — the score is a
    # percentile within a category, so it is only meaningful relative to the
    # same set of numbers the recommender is comparing against.
    quality = _compute_quality_scores(resolved)

    programs: List[KcetProgram] = []
    for idx, row in enumerate(resolved):
        programs.append(
            KcetProgram(
                institute=row["institute"],
                college_code=row["college_code"],
                program=row["program"],
                seat_category=row["seat_category"],
                seat_category_label=describe_category(row["seat_category"]),
                closing_rank=row["closing_rank"],
                closing_rank_by_round=tuple(sorted(row["by_round"].items())),
                rank_low=row["rank_low"],
                rank_high=row["rank_high"],
                band_imputed=row["band_imputed"],
                tags=frozenset(classify_kcet_branch(row["program"])),
                quality_score=quality[idx],
            )
        )
    return programs


# One built view per strategy — see ``core.rounds.StrategyCache``.
_programs = StrategyCache(_build_programs, lambda: settings.round_strategy)


def load_programs(round_strategy: object = None) -> List[KcetProgram]:
    """Programmes with one cut-off each, selected by ``round_strategy``.

    Defaults to ``settings.round_strategy`` (``"max"``). Pass ``"last"``,
    ``"first"``, or an ``int`` round number to get that view instead — e.g.
    ``load_programs(1)`` answers "what would round 1 alone have said?".
    Every programme carries its full round-wise history in
    ``closing_rank_by_round`` regardless of which strategy built it.
    """
    return _programs.get(round_strategy)


def get_available_rounds() -> List[int]:
    """Every round number present in the dataset, ascending."""
    rounds: Set[int] = set()
    for program in load_programs():
        rounds.update(program.rounds)
    return sorted(rounds)


def get_seat_categories() -> List[str]:
    return sorted({p.seat_category for p in load_programs()})


def get_institute_count() -> int:
    return len({p.institute for p in load_programs()})
