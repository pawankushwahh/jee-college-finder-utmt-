"""Unit tests for the shared, exam-agnostic engine (`app/disha/core/`).

The golden suite proves these modules didn't change any exam's output, but it
exercises them only indirectly and only at the values the three real datasets
happen to produce. These tests pin the contracts directly — especially the
boundaries and the properties that other code silently relies on.
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from app.disha.core import curation
from app.disha.core.cutoff import PointCutoffModel, clamp


@dataclass
class Row:
    """Minimal stand-in for a recommendation row.

    curation only needs `institute` plus whatever attribute names the caller
    passes, which is the whole point — it works on JEE's `Recommendation`,
    KCET's `KcetRecommendation` and COMEDK's `ComedkProgramNode` without any
    of them sharing a base class.
    """

    institute: str
    interest_score: float
    closing_rank: int
    branch: str = "CSE"


def _rows(*specs) -> list[Row]:
    return [Row(inst, score, rank) for inst, score, rank in specs]


# --------------------------------------------------------------------------
# order_bucket
# --------------------------------------------------------------------------


def test_order_bucket_sorts_by_score_then_lowest_cutoff():
    rows = _rows(("A", 5.0, 300), ("B", 9.0, 200), ("C", 9.0, 100))
    out = curation.order_bucket(rows, "Target", rank_attr="closing_rank", name_attr="branch")
    # Highest score first; the lower closing rank breaks the 9.0 tie.
    assert [r.institute for r in out] == ["C", "B", "A"]


def test_order_bucket_reach_inverts_the_cutoff_tiebreak():
    """Inside the Dream band the *highest* cutoff is closest to reachable.

    Sorting Reach ascending — as a single flat sort would — puts the least
    attainable option first, which is the bug this special case exists for.
    """
    rows = _rows(("A", 9.0, 100), ("B", 9.0, 500))
    target = curation.order_bucket(rows, "Target", rank_attr="closing_rank", name_attr="branch")
    reach = curation.order_bucket(rows, "Reach", rank_attr="closing_rank", name_attr="branch")
    assert [r.institute for r in target] == ["A", "B"]
    assert [r.institute for r in reach] == ["B", "A"]


def test_order_bucket_is_a_total_order():
    """Load-bearing: byte-identical golden output depends on this.

    If the sort key could tie, output would vary with input order, and the
    whole characterization suite would be unreliable.
    """
    a = _rows(("Same", 5.0, 100), ("Same", 5.0, 100))
    a[0].branch, a[1].branch = "AAA", "BBB"
    forward = curation.order_bucket(a, "Target", rank_attr="closing_rank", name_attr="branch")
    backward = curation.order_bucket(list(reversed(a)), "Target", rank_attr="closing_rank", name_attr="branch")
    assert [r.branch for r in forward] == [r.branch for r in backward] == ["AAA", "BBB"]


def test_order_bucket_supports_alternate_attribute_names():
    """COMEDK stores its cutoff as `cutoff_rank`, not `closing_rank`."""

    @dataclass
    class Comedkish:
        institute: str
        interest_score: float
        cutoff_rank: float
        branch: str

    rows = [Comedkish("A", 1.0, 900, "X"), Comedkish("B", 1.0, 100, "Y")]
    out = curation.order_bucket(rows, "Target", rank_attr="cutoff_rank", name_attr="branch")
    assert [r.institute for r in out] == ["B", "A"]


# --------------------------------------------------------------------------
# curate_bucket
# --------------------------------------------------------------------------


def test_curate_bucket_caps_the_list():
    rows = _rows(*[(f"Inst{i}", 1.0, i) for i in range(20)])
    assert len(curation.curate_bucket(rows, cap=5, max_per_institute=2)) == 5


def test_curate_bucket_limits_per_institute_before_relaxing():
    rows = _rows(("A", 1.0, 1), ("A", 1.0, 2), ("A", 1.0, 3), ("B", 1.0, 4))
    out = curation.curate_bucket(rows, cap=3, max_per_institute=2)
    # A is allowed two seats before B is considered for its first.
    assert [r.institute for r in out] == ["A", "A", "B"]


def test_curate_bucket_relaxes_one_seat_at_a_time_rather_than_starving():
    """Diversity must never cost the student options.

    If every row belongs to one institute, all of them are still shown —
    the allowance is raised until the bucket fills.
    """
    rows = _rows(("Only", 1.0, 1), ("Only", 1.0, 2), ("Only", 1.0, 3))
    out = curation.curate_bucket(rows, cap=3, max_per_institute=1)
    assert len(out) == 3


def test_curate_bucket_gives_every_institute_a_third_seat_before_any_gets_a_fourth():
    """The fairness property that motivated raising the allowance gradually.

    Relaxing in plain quality order instead would hand every spare seat to
    whichever institute sits highest in the ordering.
    """
    rows = _rows(*[("A", 1.0, i) for i in range(5)]) + _rows(*[("B", 1.0, 10 + i) for i in range(5)])
    out = curation.curate_bucket(rows, cap=6, max_per_institute=2)
    counts = {"A": 0, "B": 0}
    for r in out:
        counts[r.institute] += 1
    assert counts == {"A": 3, "B": 3}


@pytest.mark.parametrize("cap", [0, -1])
def test_curate_bucket_returns_empty_for_nonpositive_cap(cap):
    assert curation.curate_bucket(_rows(("A", 1.0, 1)), cap=cap, max_per_institute=2) == []


def test_curate_bucket_handles_empty_input():
    assert curation.curate_bucket([], cap=5, max_per_institute=2) == []


# --------------------------------------------------------------------------
# detect_top_rank
# --------------------------------------------------------------------------


def test_detect_top_rank_when_everything_is_safe():
    """Target and Reach both empty means the three-bucket framing says nothing."""
    assert curation.detect_top_rank(total=100, count_target=0, count_reach=0) is True


@pytest.mark.parametrize(
    "total,target,reach",
    [(0, 0, 0), (100, 1, 0), (100, 0, 1)],
)
def test_detect_top_rank_false_cases(total, target, reach):
    assert curation.detect_top_rank(total, target, reach) is False


def test_detect_top_rank_respects_comedk_rank_gate():
    """COMEDK additionally requires rank <= 100; JEE and KCET pass no gate."""
    assert curation.detect_top_rank(100, 0, 0, rank=50, rank_gate=100) is True
    assert curation.detect_top_rank(100, 0, 0, rank=101, rank_gate=100) is False
    # Same counts, no gate -> the bucket-count rule alone decides.
    assert curation.detect_top_rank(100, 0, 0, rank=101) is True


# --------------------------------------------------------------------------
# PointCutoffModel
# --------------------------------------------------------------------------

MODEL = PointCutoffModel(
    safe_margin=0.15,
    target_band_floor=1_000.0,
    target_band_ceiling=6_000.0,
    upper_margin=0.25,
    reach_band_ceiling=8_000.0,
    sigma_fraction=0.12,
    sigma_floor=150.0,
    sigma_ceiling=5_000.0,
    steepness=1.5,
)


def test_clamp():
    assert clamp(5, 1, 10) == 5
    assert clamp(0, 1, 10) == 1
    assert clamp(99, 1, 10) == 10


def test_target_band_is_clamped_at_both_ends():
    # 15% of 1,000 = 150 -> raised to the floor.
    assert MODEL.target_band(1_000) == 1_000.0
    # 15% of 100,000 = 15,000 -> lowered to the ceiling.
    assert MODEL.target_band(100_000) == 6_000.0
    # In between, the fraction applies.
    assert MODEL.target_band(20_000) == pytest.approx(3_000.0)


def test_reach_band_is_capped_but_has_no_floor():
    """A floor would list a programme closing at 692 as a Dream for a
    rank-2,000 student, whose real chance there is ~0%."""
    assert MODEL.reach_band(1_000) == pytest.approx(250.0)  # not raised
    assert MODEL.reach_band(100_000) == 8_000.0  # capped


def test_dynamic_floor_only_applies_when_configured():
    """COMEDK lowers the floor for very competitive programmes; KCET doesn't."""
    flat = MODEL.target_band(692)
    dynamic = PointCutoffModel(
        **{**MODEL.__dict__, "dynamic_floor_fraction": 0.5}
    ).target_band(692)
    assert flat == 1_000.0
    assert dynamic == pytest.approx(346.0)  # 692 * 0.5


@pytest.mark.parametrize(
    "rank,expected",
    [
        (1, "Safe"),        # miles clear of the cutoff
        (17_000, "Safe"),   # gap 3,000, exactly at the band edge -> Safe
        (18_000, "Target"), # gap 2,000, inside the band
        (20_000, "Target"), # exactly at the cutoff
        (21_000, "Reach"),  # just past it, inside the reach band
        (25_000, "Reach"),  # gap -5,000, exactly at the reach edge -> kept
        (25_001, None),     # one past the reach band -> dropped
    ],
)
def test_categorize_boundaries(rank, expected):
    # cutoff 20,000 -> target band clamp(0.15*20000, 1000, 6000) = 3,000
    #                  reach band  min(0.25*20000, 8000)         = 5,000
    assert MODEL.categorize(rank, 20_000) == expected


def test_categorize_never_prunes_an_overqualified_rank():
    """The defining property of the point model.

    Porting JEE's LOWER_MARGIN here once made a rank-500 COMEDK student see 37
    programmes instead of 459. There is no opening rank, so there is no basis
    for calling a rank "too good" for a seat.
    """
    assert MODEL.categorize(1, 111_800) == "Safe"
    assert not hasattr(MODEL, "lower_margin")


def test_probability_is_exactly_50_at_the_cutoff():
    assert MODEL.probability(20_000, 20_000) == 50.0


def test_probability_moves_the_right_way_and_stays_in_range():
    better = MODEL.probability(10_000, 20_000)
    worse = MODEL.probability(30_000, 20_000)
    assert better > 50.0 > worse
    assert 0.0 <= worse and better <= 100.0


def test_probability_from_z_matches_probability():
    """KCET calls one entry point, COMEDK the other; they must agree."""
    z = MODEL.z_score(15_000, 20_000)
    assert MODEL.probability_from_z(z) == MODEL.probability(15_000, 20_000)


def test_probability_survives_extreme_z_without_overflowing():
    assert MODEL.probability(1, 10_000_000) == 100.0
    assert MODEL.probability(10_000_000, 1) == 0.0


def test_sigma_is_clamped():
    assert MODEL.sigma(100) == 150.0        # floor
    assert MODEL.sigma(1_000_000) == 5_000.0  # ceiling
