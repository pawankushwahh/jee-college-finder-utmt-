"""Bucket ordering, capping and top-rank detection — shared by every exam.

These three functions were previously implemented once per exam
(``app/disha/recommender.py``, ``app/disha/kcet/recommender.py``,
``app/disha/comedk/recommender.py``). The three copies were character-identical
apart from attribute names — ``closing_rank`` vs ``cutoff_rank``, ``branch`` vs
``program`` — so they are parameterised here by attribute name rather than
duplicated.

The functions are deliberately generic over the row type. They need only three
attributes, named by the caller, so they work equally well on JEE's
``Recommendation``, KCET's ``KcetRecommendation`` and COMEDK's
``ComedkProgramNode`` without those types knowing anything about each other.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Sequence, Set, TypeVar

Row = TypeVar("Row")


def order_bucket(
    rows: Sequence[Row],
    bucket: str,
    *,
    rank_attr: str,
    name_attr: str,
    score_attr: str = "interest_score",
) -> List[Row]:
    """Order one bucket best-first, so that a cap keeps the strongest options.

    Target and Safe lead with the most competitive programme the rank can
    reach — the lowest cutoff breaks a score tie.

    Reach inverts that tiebreak. Inside the Dream band the *highest* cutoff is
    the one the student is closest to reaching, so sorting Dreams ascending —
    as a single flat sort would — puts the least attainable option first.

    The key ends in ``(institute, name)``, making it a **total order**. That is
    load-bearing: it means the output cannot vary with input order or hash
    seed, which is what lets the golden baseline assert byte-equality.

    Parameters
    ----------
    rank_attr:
        Attribute holding the cutoff to sort by — ``closing_rank`` for JEE and
        KCET, ``cutoff_rank`` for COMEDK.
    name_attr:
        Final tiebreak attribute — ``branch`` for JEE and COMEDK, ``program``
        for KCET.
    """
    descending_rank = bucket == "Reach"

    def key(row: Row):
        rank = getattr(row, rank_attr)
        return (
            -getattr(row, score_attr),
            -rank if descending_rank else rank,
            row.institute,
            getattr(row, name_attr),
        )

    return sorted(rows, key=key)


def curate_bucket(
    rows: Sequence[Row], cap: int, max_per_institute: int
) -> List[Row]:
    """Take the first ``cap`` options, allowing at most N per institute.

    ``rows`` must already be ordered best-first. Nothing is deleted from the
    caller's data — this only chooses what the default response displays.

    The per-institute allowance is raised one seat at a time rather than
    abandoned, so a bucket that cannot fill under a strict limit still fills,
    and does so fairly: every college gets a third seat before any college gets
    a fourth. Relaxing in plain quality order instead would hand the spare
    seats to whichever college sits highest in the ordering — at COMEDK rank
    20,000 KKR that produced four BMS rows in an eight-card bucket.

    Diversity therefore never costs the student options: if a bucket holds
    three programmes and all three are from one institute, all three are still
    shown.
    """
    if cap <= 0 or not rows:
        return []

    kept: List[Row] = []
    taken: Set[int] = set()
    per_institute: Dict[str, int] = {}
    allowance = max(1, max_per_institute)

    while len(kept) < cap:
        progressed = False
        for idx, row in enumerate(rows):
            if len(kept) >= cap:
                break
            if idx in taken:
                continue
            if per_institute.get(row.institute, 0) >= allowance:
                continue
            kept.append(row)
            taken.add(idx)
            per_institute[row.institute] = per_institute.get(row.institute, 0) + 1
            progressed = True
        if not progressed:
            break
        allowance += 1

    return kept


def detect_top_rank(
    total: int,
    count_target: int,
    count_reach: int,
    *,
    rank: Optional[int] = None,
    rank_gate: Optional[int] = None,
) -> bool:
    """Is this a rank so strong that the three-bucket framing carries no signal?

    Detected from the bucket counts rather than a fixed rank threshold: when
    everything the student is eligible for lands in Safe, Target and Reach are
    both empty and the buckets say nothing. A hardcoded rank cannot do this
    job, because the scale differs wildly per category — a JEE ST (PwD) list is
    exhausted by rank 116 where OPEN runs to 937,704.

    ``rank_gate`` adds an additional hard ceiling. Only COMEDK passes one
    (``top_rank_threshold = 100``); JEE and KCET rely on the counts alone.
    """
    if total <= 0:
        return False
    if rank_gate is not None and (rank is None or rank > rank_gate):
        return False
    return count_target == 0 and count_reach == 0
