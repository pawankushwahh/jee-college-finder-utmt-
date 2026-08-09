"""KCET recommendation logic using single-rank cutoff proximity."""

from typing import List, Optional
from .schemas import KcetRecommendRequest, KcetRecommendResponse, KcetProgramNode
from .data_loader import get_programs

# Proximity factors applied to the student's rank to determine buckets
_REACH_LO  = 0.70   # cutoff must be >= rank * 0.70 (else excluded — too hard)
_REACH_HI  = 0.85   # cutoff < rank * 0.85 -> Reach (Dream)
_TARGET_LO = 0.85   # cutoff >= rank * 0.85 -> Target
_TARGET_HI = 1.15   # cutoff <= rank * 1.15 -> Target
_SAFE_HI   = 1.50   # cutoff <= rank * 1.50 -> Safe (else excluded — too easy)


def _safe_cap(rank: int) -> int:
    """Return the maximum number of Safe options to show for this rank.

        Rank 1-10    → 10
        Rank 11-100  → 15
        Rank 101-1k  → 20
        Rank 1k-10k  → 25
        Rank >10k    → 30
    """
    if rank <= 10:
        return 10
    if rank <= 100:
        return 15
    if rank <= 1000:
        return 20
    if rank <= 10000:
        return 25
    return 30


def _categorize(rank: int, cutoff: float) -> Optional[str]:
    """Return Safe/Target/Reach or None (exclude).
    
    Lower rank = better performance. cutoff is the last admitted rank.
    If cutoff > rank: student can get in (rank is better).
    If cutoff < rank: student cannot get in unless cutoffs shift.
    """
    lo = rank * _REACH_LO
    hi = max(rank * _SAFE_HI, rank + max(2000, int(rank * 0.5)))

    # Exclude colleges that are too far in either direction
    if cutoff < lo or cutoff > hi:
        return None

    if cutoff < rank * _REACH_HI:
        return "Reach"
    if cutoff <= rank * _TARGET_HI:
        return "Target"
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


def recommend(req: KcetRecommendRequest) -> KcetRecommendResponse:
    programs = get_programs()

    safe:   List[KcetProgramNode] = []
    target: List[KcetProgramNode] = []
    reach:  List[KcetProgramNode] = []

    for prog in programs:
        # If the dataset has a quota column, filter by it.
        # Handle cases where quota filtering might be case-insensitive or exact.
        if "quota" in prog and prog["quota"] and req.quota:
            if prog["quota"].lower() != req.quota.lower():
                continue
            
        if not _matches_goal(prog, req.goal):
            continue

        bucket = _categorize(req.rank, prog["cutoff_rank"])
        if bucket is None:
            continue

        node = KcetProgramNode(
            institute=prog["institute"],
            program=prog["program"],
            quota=prog.get("quota", "GM"),
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

    # Cap safe list by rank tier
    cap = _safe_cap(req.rank)
    safe = safe[:cap]

    # Bucket filtering
    if req.bucket == "safe":
        target, reach = [], []
    elif req.bucket == "target":
        safe, reach = [], []
    elif req.bucket in ("reach", "dream"):
        safe, target = [], []

    # Pagination
    start_idx = (req.page - 1) * req.page_size
    end_idx   = start_idx + req.page_size

    page_safe   = safe[start_idx:end_idx]
    page_target = target
    page_reach  = reach
    has_next    = end_idx < len(safe)

    return KcetRecommendResponse(
        safe=page_safe,
        target=page_target,
        reach=page_reach,
        total_safe=total_safe,
        total_target=total_target,
        total_reach=total_reach,
        has_next=has_next,
    )
