"""COMEDK recommendation logic — Hybrid Scale-Adaptive Thresholds.

COMEDK provides only a *single* cutoff rank per college/branch/category (the
closing rank of the last admitted student).  This module classifies every
program into a confidence tier relative to the student's rank using dynamic
thresholds that scale with the rank while enforcing minimum floors so that
the buckets remain meaningful at every rank level.

Terminology (lower rank = better performance):
  C = cutoff rank (closing rank — last student admitted)
  R = student's rank

Tier definitions:
  Dream (Reach)  — Student is *not yet eligible* (R > C), but the gap is
                    within a realistic year-over-year fluctuation margin.
                    Condition: C < R  AND  R − C ≤ dream_margin
                    dream_margin = max(1500, 0.15 × R)

  Target         — Student is eligible (R ≤ C) and the cutoff is close to
                    their rank, so admission is probable but not guaranteed.
                    Condition: R ≤ C ≤ R + target_margin
                    target_margin = max(2000, 0.20 × R)

  Safe           — Student's rank is comfortably better than the cutoff.
                    Condition: C > R + target_margin  (up to the safe ceiling)

Exclusion rules (prevents noise):
  Too competitive : C < R − dream_margin   → excluded
  Too easy        : C > R + safe_ceiling    → excluded
                    safe_ceiling = max(15000, 0.50 × R)

Pagination: Safe can be large, so it is paginated by page/page_size.
Target and Dream are always returned in full (they're naturally small).
"""

from typing import List, Optional
from .schemas import ComedkRecommendRequest, ComedkRecommendResponse, ComedkProgramNode
from .data_loader import get_programs


# ── Hybrid Scale-Adaptive Thresholds ──────────────────────────────────────────
#
# Each threshold is computed as:  max(FLOOR, FRACTION × student_rank)
#
# This guarantees:
#   • At top ranks (e.g. 1,000)  the floors kick in, giving a wide enough
#     window so real options aren't pruned.
#   • At mid/high ranks (e.g. 50,000) the percentage scales naturally.

_DREAM_FLOOR     = 1500    # min rank-gap to qualify as Dream
_DREAM_FRACTION  = 0.15    # 15% of student rank

_TARGET_FLOOR    = 2000    # min rank-gap for the Target ceiling
_TARGET_FRACTION = 0.20    # 20% of student rank

_SAFE_CEIL_FLOOR    = 15000  # min ceiling above rank before exclusion
_SAFE_CEIL_FRACTION = 0.50   # 50% of student rank


def _dream_margin(rank: int) -> float:
    """Maximum gap (R − C) to still classify as Dream."""
    return max(_DREAM_FLOOR, _DREAM_FRACTION * rank)


def _target_margin(rank: int) -> float:
    """Maximum gap (C − R) to still classify as Target."""
    return max(_TARGET_FLOOR, _TARGET_FRACTION * rank)


def _safe_ceiling(rank: int) -> float:
    """Maximum cutoff value before a college is excluded as too easy."""
    return rank + max(_SAFE_CEIL_FLOOR, _SAFE_CEIL_FRACTION * rank)


def _categorize(rank: int, cutoff: float) -> Optional[str]:
    """Classify a single college into Dream / Target / Safe, or exclude.

    Parameters
    ----------
    rank : int
        The student's COMEDK rank (lower is better).
    cutoff : float
        The college's closing cutoff rank (last admitted student).

    Returns
    -------
    str or None
        ``"Reach"`` (Dream), ``"Target"``, ``"Safe"``, or ``None`` (excluded).
    """
    dm = _dream_margin(rank)
    tm = _target_margin(rank)
    sc = _safe_ceiling(rank)

    # ── Exclusion: too competitive (cutoff far below rank) ────────────────────
    if cutoff < rank - dm:
        return None

    # ── Exclusion: too easy (cutoff far above rank) ───────────────────────────
    if cutoff > sc:
        return None

    # ── Dream / Reach: student not yet eligible but within fluctuation range ──
    if cutoff < rank:
        return "Reach"

    # ── Target: student eligible, cutoff close to rank ────────────────────────
    if cutoff <= rank + tm:
        return "Target"

    # ── Safe: student's rank comfortably better than cutoff ───────────────────
    return "Safe"


# ── Goal matching ─────────────────────────────────────────────────────────────

def _matches_goal(prog: dict, goal: str) -> bool:
    """Return True if the program is relevant to the student's career goal."""
    if goal in ("undecided", "mba"):
        return True

    prog_name = prog["program"].lower()
    keywords = {
        "coding":      ["computer", "artificial", "data", "information",
                        "software", "machine learning", "electronics"],
        "research":    ["biotech", "biotechnology", "aerospace", "science", "research"],
        "core":        ["mechanical", "civil", "electrical", "chemical",
                        "aeronautical", "industrial", "production"],
        "pure_science": ["physics", "chemistry", "mathematics", "math"],
    }
    return any(kw in prog_name for kw in keywords.get(goal, []))


# ── Main recommendation entry point ──────────────────────────────────────────

def recommend(req: ComedkRecommendRequest) -> ComedkRecommendResponse:
    """Generate Safe / Target / Dream recommendations for a COMEDK student."""
    programs = get_programs()

    safe:   List[ComedkProgramNode] = []
    target: List[ComedkProgramNode] = []
    reach:  List[ComedkProgramNode] = []

    for prog in programs:
        if prog["quota"] != req.quota:
            continue

        if not _matches_goal(prog, req.goal):
            continue

        bucket = _categorize(req.rank, prog["cutoff_rank"])
        if bucket is None:
            continue

        node = ComedkProgramNode(
            institute=prog["institute"],
            program=prog["program"],
            quota=prog["quota"],
            cutoff_rank=prog["cutoff_rank"],
            bucket=bucket,
            tags=[],
        )
        if bucket == "Safe":
            safe.append(node)
        elif bucket == "Target":
            target.append(node)
        else:
            reach.append(node)

    # Sort each bucket by proximity to student's rank (closest first)
    _by_proximity = lambda x: abs(x.cutoff_rank - req.rank)
    safe.sort(key=_by_proximity)
    target.sort(key=_by_proximity)
    reach.sort(key=_by_proximity)

    total_safe   = len(safe)
    total_target = len(target)
    total_reach  = len(reach)

    # ── Bucket filter ─────────────────────────────────────────────────────────
    if req.bucket == "safe":
        target, reach = [], []
    elif req.bucket == "target":
        safe, reach = [], []
    elif req.bucket in ("reach", "dream"):
        safe, target = [], []

    # ── Pagination ────────────────────────────────────────────────────────────
    # Target and Dream are always returned in full (they're naturally small).
    # Safe can be large — paginate it independently.
    start_idx = (req.page - 1) * req.page_size
    end_idx   = start_idx + req.page_size

    page_safe   = safe[start_idx:end_idx]
    page_target = target          # always full
    page_reach  = reach           # always full
    has_next    = end_idx < len(safe)

    return ComedkRecommendResponse(
        safe=page_safe,
        target=page_target,
        reach=page_reach,
        total_safe=total_safe,
        total_target=total_target,
        total_reach=total_reach,
        has_next=has_next,
    )
