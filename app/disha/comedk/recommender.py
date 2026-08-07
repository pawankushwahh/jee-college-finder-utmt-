"""COMEDK recommendation logic.

Classification is proximity-based — what matters to a student is how close
their rank is to the cutoff, NOT just whether they'd mathematically get in:

  Dream : cutoff is below rank but within stretch  → rank*0.70 <= cutoff < rank*0.85
  Target: cutoff is close to rank (either side)    → rank*0.85 <= cutoff <= rank*1.15
  Safe  : student rank is clearly better           → rank*1.15 < cutoff <= rank*1.50

Colleges whose cutoff is outside [rank*0.70, rank*1.50] are excluded entirely —
they are either impossibly competitive or so easy they add no useful signal.

Pagination: Safe can be large, so it is paginated by page/page_size.
Target and Dream are always returned in full (they're naturally small).
"""

from typing import List, Optional, Tuple
from .schemas import ComedkRecommendRequest, ComedkRecommendResponse, ComedkProgramNode
from .data_loader import get_programs

# ── Thresholds ────────────────────────────────────────────────────────────────

# proximity factors (applied to student's rank)
_DREAM_LO  = 0.70   # cutoff must be >= rank * 0.70 (else excluded — too hard)
_DREAM_HI  = 0.85   # cutoff < rank * 0.85 → Dream
_TARGET_LO = 0.85   # cutoff >= rank * 0.85 → Target (lower bound)
_TARGET_HI = 1.15   # cutoff <= rank * 1.15 → Target (upper bound)
_SAFE_HI   = 1.50   # cutoff <= rank * 1.50 → Safe  (else excluded — too easy)


def _categorize(rank: int, cutoff: float) -> Optional[str]:
    """Return Safe/Target/Dream or None (exclude).

    Lower rank = better performance. cutoff is the last admitted rank.
    If cutoff > rank: student can get in (rank is better).
    If cutoff < rank: student cannot get in unless cutoffs shift.
    """
    lo = rank * _DREAM_LO
    # For very strong ranks (e.g. 345), rank * 1.5 is too narrow.
    # Add a flat buffer to ensure we don't prune perfectly safe options.
    hi = max(rank * _SAFE_HI, rank + 15000)

    # Exclude colleges that are too far in either direction
    if cutoff < lo or cutoff > hi:
        return None

    if cutoff < rank * _DREAM_HI:   # rank*0.70 <= cutoff < rank*0.85
        return "Reach"
    if cutoff <= rank * _TARGET_HI:  # rank*0.85 <= cutoff <= rank*1.15
        return "Target"
    # rank*1.15 < cutoff <= rank*1.50
    return "Safe"


def _matches_goal(prog: dict, goal: str) -> bool:
    if goal in ("undecided", "mba"):
        return True

    prog_name = prog["program"].lower()
    keywords = {
        "coding":      ["computer", "artificial", "data", "information",
                        "software", "machine learning", "electronics"],
        "research":    ["biotech", "biotechnology", "aerospace", "science", "research"],
        "core":        ["mechanical", "civil", "electrical", "chemical",
                        "aeronautical", "industrial", "production"],
        "pure_science":["physics", "chemistry", "mathematics", "math"],
    }
    return any(kw in prog_name for kw in keywords.get(goal, []))


def recommend(req: ComedkRecommendRequest) -> ComedkRecommendResponse:
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
