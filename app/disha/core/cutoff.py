"""Cutoff models — how a rank and a published cutoff become Safe/Target/Reach.

This is the one stage of the pipeline that genuinely cannot be shared across
*all* exams, because the exams do not publish the same thing:

``window`` (JoSAA / JEE)
    An opening **and** a closing rank. The admitted band is observed fact, so
    JEE can ask a factual question — "did someone at your rank get a seat here
    last year?" — and can meaningfully prune a candidate as overqualified.

``point`` (KCET, COMEDK)
    A single closing rank. The admitted band is unobserved and has to be
    *modelled* as a fraction of the cutoff, clamped into an absolute range.

Only the point model lives here, because KCET and COMEDK were independently
implementing the same formulas with different constants. JEE's window model
stays in ``app/disha/recommender.py``: it is used by exactly one exam, and
generalising a sample size of one produces an abstraction shaped like JoSAA.

**``PointCutoffModel`` has no overqualification prune, and must never gain
one.** Without a published opening rank there is no factual basis for calling
a rank "too good" for a seat. Porting JEE's ``LOWER_MARGIN`` here once caused
a rank-500 COMEDK student to be shown 37 programmes instead of 459. The
absence is the design, not an omission.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional

Bucket = Optional[str]  # "Safe" | "Target" | "Reach" | None


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


@dataclass(frozen=True)
class PointCutoffModel:
    """Bucketing and probability for exams publishing one closing rank.

    Every constant is supplied by the exam rather than defaulted, because the
    right values are measured from each dataset's own distribution. KCET's
    cutoffs run to ~250,000 where COMEDK's stop at 111,800, so reusing one
    exam's absolute ceilings for the other would push everything past the
    ~90th percentile onto the ceiling. See each exam's ``config.py`` for the
    measured percentiles behind its numbers.
    """

    safe_margin: float
    target_band_floor: float
    target_band_ceiling: float
    upper_margin: float
    reach_band_ceiling: float
    sigma_fraction: float
    sigma_floor: float
    sigma_ceiling: float
    steepness: float

    # COMEDK lowers the target-band floor for very competitive programmes:
    # at cutoff 692 a flat 1,000-rank floor would swallow the whole rank range
    # below it and stop top ranks reading as Safe. KCET leaves this None and
    # uses a flat floor. Expressed as a parameter rather than an
    # ``if exam == "comedk"``.
    dynamic_floor_fraction: Optional[float] = None

    def target_band(self, cutoff: float) -> float:
        """Width of the modelled admitted window below ``cutoff``.

        A pure fraction breaks down at both ends of the range — 15% is 104
        ranks at a cutoff of 692 and 16,770 at 111,800 — so it is clamped into
        an absolute range. That keeps one interpretable meaning across the
        whole scale: "within roughly N ranks of the cutoff", not "within N%".
        """
        floor = self.target_band_floor
        if self.dynamic_floor_fraction is not None:
            floor = min(floor, cutoff * self.dynamic_floor_fraction)
        return clamp(self.safe_margin * cutoff, floor, self.target_band_ceiling)

    def reach_band(self, cutoff: float) -> float:
        """How far past ``cutoff`` a programme is still worth listing.

        Capped, and deliberately with **no floor**: at low cutoffs the
        multiplicative form is the honest one. A floor would tell a rank-2,000
        student that a programme closing at 692 is a Dream when their real
        chance is ~0%.
        """
        return min(self.upper_margin * cutoff, self.reach_band_ceiling)

    def categorize(self, rank: int, cutoff: float) -> Bucket:
        """Safe / Target / Reach, or None if the option should be dropped.

        Reads as one number line, with ``gap = cutoff - rank`` (positive means
        the student has headroom below the cutoff)::

            gap < -reach_band        -> None     no realistic chance
            -reach_band <= gap < 0   -> Reach    just past the cutoff
            0 <= gap < target_band   -> Target   right at the cutoff
            gap >= target_band       -> Safe     comfortably clear of it
        """
        gap = cutoff - rank
        if gap < -self.reach_band(cutoff):
            return None
        if gap >= self.target_band(cutoff):
            return "Safe"
        if gap >= 0:
            return "Target"
        return "Reach"

    def sigma(self, cutoff: float) -> float:
        """Spread of the probability curve, proportional to the cutoff.

        Year-over-year drift is roughly proportional to where the cutoff sits,
        but clamped at both ends for the same reason the bands are: an
        unclamped sigma of 13,400 at cutoff 111,800 read a 6,800-rank cushion
        as only 79% likely.

        ``sigma_fraction`` is a stated prior, not a fitted value — neither
        dataset has a second year in the repo to fit against.
        """
        return clamp(self.sigma_fraction * cutoff, self.sigma_floor, self.sigma_ceiling)

    def z_score(self, rank: int, cutoff: float) -> float:
        """Standardised distance from the cutoff. Positive means headroom."""
        return (cutoff - rank) / self.sigma(cutoff)

    def probability(self, rank: int, cutoff: float) -> float:
        """Admission probability as a percentage, 0.0-100.0.

        ``rank == cutoff`` gives exactly 50.0%. Exams derive their confidence
        label from :meth:`z_score` so that the label and the percentage on a
        card can never disagree — but the *labels themselves* stay per-exam,
        because JEE's four round-volatility tags and the point exams' headroom
        buckets answer different questions and a shared vocabulary would force
        one of them to lie.
        """
        return self.probability_from_z(self.z_score(rank, cutoff))

    def probability_from_z(self, z: float) -> float:
        """As :meth:`probability`, for callers that already hold the z-score.

        KCET computes the z-score once and reuses it for both the percentage
        and the confidence label; COMEDK passes rank and cutoff. Both entry
        points exist so neither exam has to recompute or restructure.
        """
        try:
            prob = 100.0 / (1.0 + math.exp(-self.steepness * z))
        except OverflowError:
            prob = 100.0 if z > 0 else 0.0
        return round(prob, 1)
