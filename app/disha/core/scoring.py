"""How competitive one programme is, relative to the ones it competes with.

Neither KCET nor COMEDK ships a tier list. There is no authoritative ranking of
Karnataka engineering colleges to hardcode the way JEE's IIT/NIT tiers are
public knowledge, so the sharpest demand signal either dataset offers is a
programme's own cut-off *relative to its peers*: the lower it closed, the more
people wanted it. Both exams were computing that percentile independently.

The percentile is always taken **within a group**, never across the whole
table, because cut-offs from different seat pools are not on the same scale. A
GM cut-off and an STK cut-off answer different questions, and ranking them
against each other would order a shortlist by which category a row belongs to.
Which column defines the group is the exam's own decision — KCET groups by
``seat_category`` (48 codes across two seat pools), COMEDK by ``quota`` (GM and
KKR).

The orientation is fixed here and relied on by both callers: **1.0 is the
lowest cut-off in the group** (most competitive, most in demand) and 0.0 the
highest. What each exam does with the number afterwards differs and stays in
its own module — KCET scales it to a 0-10 ``quality_score`` and uses it alone,
COMEDK blends it 70/30 with a data-derived institute brand tier.
"""

from __future__ import annotations

from typing import Callable, Dict, Hashable, List, Sequence, TypeVar

# ── Tie handling ───────────────────────────────────────────────────────────
# The two exams answer "what about two programmes that closed at the same
# rank?" differently, and both answers are defensible, so the choice is the
# caller's rather than a shared default.
#
# ``dense``    equal cut-offs share a percentile. Two programmes that closed at
#              the same rank are never ordered against each other by this key —
#              their tiebreak comes from the ordering stage instead. COMEDK's
#              choice, where ties are common (1,114 rows over a narrow range).
# ``ordinal``  each row gets its own position, ties broken by the order they
#              appear in. Spreads a large group evenly across the full 0-1
#              range, which keeps the scale usable when a single category holds
#              thousands of rows. KCET's choice.
TIES_DENSE = "dense"
TIES_ORDINAL = "ordinal"


def competitiveness(
    values: Sequence[float], *, ties: str = TIES_DENSE
) -> List[float]:
    """Percentile position of each value, 1.0 for the lowest, aligned to input.

    A single-element group scores 1.0: it is simultaneously the most and least
    competitive thing in its group, and 1.0 is the reading that does not
    penalise a category for being small.
    """
    count = len(values)
    if count == 0:
        return []

    if ties == TIES_DENSE:
        distinct = sorted(set(values))
        denominator = max(1, len(distinct) - 1)
        position = {value: index for index, value in enumerate(distinct)}
        return [1.0 - (position[value] / denominator) for value in values]

    # Ordinal: stable sort, so equal values keep their input order and the
    # result cannot vary with dict or hash ordering. That is load-bearing —
    # the golden baseline asserts byte-identical output.
    order = sorted(range(count), key=lambda index: values[index])
    denominator = max(1, count - 1)
    scores = [0.0] * count
    for place, index in enumerate(order):
        scores[index] = 1.0 - (place / denominator)
    return scores


Row = TypeVar("Row")


def competitiveness_by_group(
    rows: Sequence[Row],
    *,
    group_of: Callable[[Row], Hashable],
    value_of: Callable[[Row], float],
    ties: str = TIES_DENSE,
) -> List[float]:
    """As :func:`competitiveness`, computed inside each group separately.

    Returns one score per row, in the caller's order. Rows are generic: both
    exams pass plain dicts at this stage of loading, and the key names differ
    (``closing_rank`` vs ``cutoff_rank``), so the columns are named by accessor
    rather than by string.
    """
    groups: Dict[Hashable, List[int]] = {}
    for index, row in enumerate(rows):
        groups.setdefault(group_of(row), []).append(index)

    scores = [0.0] * len(rows)
    for indexes in groups.values():
        group_values = [value_of(rows[index]) for index in indexes]
        for index, score in zip(indexes, competitiveness(group_values, ties=ties)):
            scores[index] = score
    return scores
