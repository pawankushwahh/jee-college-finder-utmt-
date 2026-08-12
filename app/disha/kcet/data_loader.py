"""Data loading for the KCET engine.

Loads ``kcet_2025.csv`` (KCET 2025 round-1 closing ranks — the same file this
module has always used; ``kcet_2025_round1_cutoffs_cleaned.csv`` from
https://github.com/Rakshita-0206/Dataset_Of_Different_Colleges was checked
against it byte-for-byte after normalising line endings and is identical) and
builds one ``KcetProgram`` per row, with:

  * branch tags from ``classify_kcet_branch`` (states.py),
  * a per-category quality percentile, used both to order results within a
    bucket and as the closest thing this dataset has to a "brand" signal —
    there is no authoritative tier list of Karnataka engineering colleges to
    hard-code the way JEE's IIT/NIT tiers are public knowledge, so competitive
    demand (this row's cutoff relative to every other row in the same
    seat_category) stands in for it, same reasoning as COMEDK's quality score.
"""

from __future__ import annotations

import csv
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set

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
    closing_rank: int
    tags: Set[str] = field(default_factory=frozenset)
    quality_score: float = 0.0  # 0-10, higher = more competitive (lower cutoff)


def _safe_int(val: str) -> Optional[int]:
    if val is None:
        return None
    v = val.strip().replace(",", "")
    if not v:
        return None
    try:
        return int(float(v))
    except ValueError:
        return None


def _load_raw_rows() -> List[dict]:
    csv_path = settings.resolved_csv_path
    if not csv_path.exists():
        logger.error("KCET data file not found: %s", csv_path)
        return []

    rows: List[dict] = []
    seen: Set[tuple] = set()
    with open(csv_path, mode="r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            institute = (row.get("college_name") or "").strip()
            college_code = (row.get("college_code") or "").strip()
            program = (row.get("course_name") or "").strip()
            seat_category = (row.get("category") or "").strip().upper()
            closing = _safe_int(row.get("closing_rank"))

            if not institute or not program or not seat_category or closing is None:
                continue

            # The source has ~50 exact-duplicate (college_code, course, category)
            # rows; keep only the first so a program is never double-counted or
            # double-shown.
            key = (college_code, program, seat_category)
            if key in seen:
                continue
            seen.add(key)

            rows.append(
                {
                    "institute": institute,
                    "college_code": college_code or institute,
                    "program": program,
                    "seat_category": seat_category,
                    "closing_rank": closing,
                }
            )
    return rows


def _compute_quality_scores(rows: List[dict]) -> Dict[int, float]:
    """Percentile-based quality score per row, computed within its own
    seat_category (a GM cutoff and an STK cutoff are not on the same scale,
    so ranking across categories would be meaningless).

    quality_score = 10 * (1 - percentile), so the single lowest closing rank
    in a category scores near 10 and the highest scores near 0.
    """
    by_category: Dict[str, List[int]] = {}
    for idx, row in enumerate(rows):
        by_category.setdefault(row["seat_category"], []).append(idx)

    scores: Dict[int, float] = {}
    for cat, idxs in by_category.items():
        ordered = sorted(idxs, key=lambda i: rows[i]["closing_rank"])
        n = len(ordered)
        for rank_pos, idx in enumerate(ordered):
            # rank_pos 0 (lowest/most competitive closing rank) -> percentile 0
            percentile = rank_pos / max(1, n - 1) if n > 1 else 0.0
            scores[idx] = round(10.0 * (1.0 - percentile), 2)
    return scores


def _build_programs() -> List[KcetProgram]:
    rows = _load_raw_rows()
    quality = _compute_quality_scores(rows)
    programs: List[KcetProgram] = []
    for idx, row in enumerate(rows):
        programs.append(
            KcetProgram(
                institute=row["institute"],
                college_code=row["college_code"],
                program=row["program"],
                seat_category=row["seat_category"],
                seat_category_label=describe_category(row["seat_category"]),
                closing_rank=row["closing_rank"],
                tags=frozenset(classify_kcet_branch(row["program"])),
                quality_score=quality.get(idx, 5.0),
            )
        )
    return programs


_cached_programs: Optional[List[KcetProgram]] = None


def load_programs() -> List[KcetProgram]:
    global _cached_programs
    if _cached_programs is None:
        _cached_programs = _build_programs()
    return _cached_programs


def get_seat_categories() -> List[str]:
    return sorted({p.seat_category for p in load_programs()})


def get_institute_count() -> int:
    return len({p.institute for p in load_programs()})
