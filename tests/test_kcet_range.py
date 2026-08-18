"""Unit tests for KCET's observed-range bucketing and relevance floor.

A programme's Safe/Target/Dream bucket comes from the range of ranks KEA
actually admitted across the rounds, not from a band modelled around a single
number. These pin the two rules that replaced the modelled band, and the two
places the design was validated against the data and had to be corrected:

  * the imputed band for single-round programmes must extend *upward*, because
    95% of those publish only a round-1 value, which is the tough end;
  * the relevance floor is separate from bucketing, because a weak programme's
    own band is wide enough to make it Safe at every rank.
"""

from __future__ import annotations

import pytest

from app.disha.core.cutoff import RangeCutoffModel
from app.disha.kcet import data_loader
from app.disha.kcet.config import settings
from app.disha.kcet.data_loader import load_programs
from app.disha.kcet.recommender import recommend
from app.disha.kcet.schemas import KcetRecommendRequest


MODEL = RangeCutoffModel(steepness=1.5)


# ── Bucketing straight off the observed range ───────────────────────────────


def test_rank_clearing_the_toughest_round_is_safe():
    assert MODEL.categorize(4_000, 4_628, 7_213) == "Safe"


def test_rank_inside_the_admitted_range_is_target():
    """The literal meaning of Target: admitted in some round, but not the
    toughest one."""
    assert MODEL.categorize(4_628, 4_628, 7_213) == "Target"
    assert MODEL.categorize(6_000, 4_628, 7_213) == "Target"
    assert MODEL.categorize(7_213, 4_628, 7_213) == "Target"


def test_rank_past_the_loosest_round_is_reach():
    assert MODEL.categorize(7_500, 4_628, 7_213) == "Reach"


def test_rank_far_past_every_round_is_dropped():
    assert MODEL.categorize(999_999, 4_628, 7_213) is None


def test_boundaries_are_the_observed_ranks_themselves():
    """No modelled band: moving one rank across `low` or `high` must flip the
    bucket, so the boundary is exactly the published number."""
    low, high = 10_000, 20_000
    assert MODEL.categorize(low - 1, low, high) == "Safe"
    assert MODEL.categorize(low, low, high) == "Target"
    assert MODEL.categorize(high, low, high) == "Target"
    assert MODEL.categorize(high + 1, low, high) == "Reach"


def test_zero_width_band_still_buckets():
    """A programme whose rounds all closed at the same rank must not divide by
    zero or collapse to a single bucket."""
    assert MODEL.categorize(900, 1_000, 1_000) == "Safe"
    assert MODEL.categorize(1_000, 1_000, 1_000) == "Target"
    assert MODEL.probability(1_000, 1_000, 1_000) == pytest.approx(50.0)


def test_probability_is_centred_on_the_loose_end():
    """`rank == high` is the real admission boundary, so it is 50%."""
    assert MODEL.probability(7_213, 4_628, 7_213) == pytest.approx(50.0)
    assert MODEL.probability(4_628, 4_628, 7_213) > 90.0
    assert MODEL.probability(9_000, 4_628, 7_213) < 50.0


def test_sigma_comes_from_the_programmes_own_band():
    """A volatile programme must report less certainty than a stable one at the
    same headroom — the point of dropping a single global sigma."""
    stable = MODEL.probability(9_000, 9_500, 10_000)
    volatile = MODEL.probability(9_000, 2_000, 10_000)
    assert stable > volatile


# ── Imputation for the 26% with only one round ──────────────────────────────


def test_imputed_band_extends_upward_from_the_known_value():
    """95% of single-round programmes publish only round 1, which is the tough
    end. Imputing downward would treat it as the loose end and mislabel
    genuinely-Safe students as Target."""
    low, high, imputed = data_loader._observed_range({1: 100_000.0})
    assert imputed is True
    assert low == 100_000.0
    assert high > low


def test_observed_band_is_not_imputed():
    low, high, imputed = data_loader._observed_range({1: 4_628.0, 3: 7_213.0})
    assert (low, high, imputed) == (4_628.0, 7_213.0, False)


def test_imputed_flag_is_exposed_on_programmes():
    programs = load_programs()
    assert any(p.band_imputed for p in programs)
    assert any(not p.band_imputed for p in programs)
    for program in programs:
        assert program.rank_high >= program.rank_low
        if not program.band_imputed:
            published = [rank for _, rank in program.closing_rank_by_round]
            assert program.rank_low == min(published)
            assert program.rank_high == max(published)


# ── The relevance floor, which bucketing cannot do ──────────────────────────


def test_top_rank_no_longer_sees_the_whole_state():
    """The case this was built for: a rank-100 student opening Safe used to get
    1,576 options running out to cut-off 262,158 at '100% probability'."""
    response = recommend(
        KcetRecommendRequest(rank=100, seat_category="GM", bucket="safe")
    )
    assert len(response.recommendations) <= settings.min_options
    worst = max(r.rank_high for r in response.recommendations)
    assert worst < 50_000, f"still offering a cut-off of {worst:,.0f} to a rank-100 student"


def test_relevance_floor_tracks_the_students_rank():
    """The worst option offered must scale with the rank, at every scale."""
    previous = 0.0
    for rank in (1_000, 20_000, 100_000, 200_000):
        response = recommend(KcetRecommendRequest(rank=rank, seat_category="GM"))
        worst = max(r.rank_low for r in response.recommendations)
        assert worst > previous, "relevance boundary must move with the rank"
        previous = worst


def test_never_returns_fewer_than_the_minimum():
    """A very strong rank has a tiny relevance window; the top-up must still
    produce a list worth choosing from."""
    response = recommend(KcetRecommendRequest(rank=1, seat_category="GM"))
    assert response.total_count >= min(settings.min_options, 25)


def test_bucketing_and_relevance_are_independent():
    """A weak programme's band is wide enough to make it Safe for any rank, so
    the floor has to be a separate rule rather than a wider band."""
    weak = max(load_programs(), key=lambda p: p.rank_high)
    assert MODEL.categorize(100, weak.rank_low, weak.rank_high) == "Safe"
    response = recommend(KcetRecommendRequest(rank=100, seat_category=weak.seat_category))
    assert all(r.college_code != weak.college_code or r.program != weak.program
               for r in response.recommendations)


def test_cards_expose_the_range_used_for_bucketing():
    """The numbers shown and the numbers modelled must be the same ones."""
    response = recommend(KcetRecommendRequest(rank=50_000, seat_category="GM"))
    assert response.recommendations
    for rec in response.recommendations:
        assert rec.rank_low <= rec.rank_high
        expected = MODEL.categorize(50_000, rec.rank_low, rec.rank_high)
        assert rec.category == expected
