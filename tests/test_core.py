"""Unit tests for the shared, exam-agnostic engine (`app/disha/core/`).

The golden suite proves these modules didn't change any exam's output, but it
exercises them only indirectly and only at the values the three real datasets
happen to produce. These tests pin the contracts directly — especially the
boundaries and the properties that other code silently relies on.
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from app.disha.core import curation, rounds, scoring
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
    # Only `group_and_order` reads this; every other function is told which
    # bucket it is working on by the caller.
    category: str = "Target"


def _rows(*specs) -> list[Row]:
    return [Row(inst, score, rank) for inst, score, rank in specs]


def _bucketed(*specs) -> list[Row]:
    return [Row(inst, score, rank, "CSE", bucket) for inst, score, rank, bucket in specs]


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
# group_and_order / curate_all / top_rank_view / flatten
#
# The stages both point exams compose their pipeline out of. What they must
# guarantee is that the composition is the *only* thing that differs between
# the exams — see docs/EXAM_DIFFERENCES.md.
# --------------------------------------------------------------------------


def test_group_and_order_buckets_rows_and_orders_each_one():
    rows = _bucketed(
        ("A", 1.0, 300, "Safe"),
        ("B", 9.0, 200, "Target"),
        ("C", 9.0, 100, "Target"),
    )
    grouped = curation.group_and_order(rows, rank_attr="closing_rank", name_attr="branch")
    assert [r.institute for r in grouped["Target"]] == ["C", "B"]
    assert [r.institute for r in grouped["Safe"]] == ["A"]


def test_group_and_order_always_returns_every_bucket():
    """Callers index the result unguarded, and an empty bucket's count is as
    much a part of the response as a full one's."""
    grouped = curation.group_and_order([], rank_attr="closing_rank", name_attr="branch")
    assert set(grouped) == set(curation.BUCKET_ORDER) == {"Target", "Reach", "Safe"}
    assert all(rows == [] for rows in grouped.values())


def test_group_and_order_applies_the_reach_tiebreak_per_bucket():
    """Ordering is per bucket, not one flat sort, because "best first" inverts
    inside Reach."""
    rows = _bucketed(
        ("Low", 9.0, 100, "Reach"),
        ("High", 9.0, 500, "Reach"),
        ("Low", 9.0, 100, "Target"),
        ("High", 9.0, 500, "Target"),
    )
    grouped = curation.group_and_order(rows, rank_attr="closing_rank", name_attr="branch")
    assert [r.institute for r in grouped["Reach"]] == ["High", "Low"]
    assert [r.institute for r in grouped["Target"]] == ["Low", "High"]


def test_curate_all_applies_each_buckets_own_cap():
    eligible = {
        "Target": _rows(*[(f"T{i}", 1.0, i) for i in range(10)]),
        "Reach": _rows(*[(f"R{i}", 1.0, i) for i in range(10)]),
        "Safe": _rows(*[(f"S{i}", 1.0, i) for i in range(10)]),
    }
    curated = curation.curate_all(
        eligible, {"Target": 3, "Reach": 2, "Safe": 1}, max_per_institute=2
    )
    assert [len(curated[b]) for b in ("Target", "Reach", "Safe")] == [3, 2, 1]


def test_top_rank_view_empties_target_and_reach():
    """Top-rank mode's whole point: the three-bucket framing carries no signal,
    so only the strongest Safe options are shown."""
    eligible = {
        "Target": _rows(("T", 1.0, 1)),
        "Reach": _rows(("R", 1.0, 2)),
        "Safe": _rows(*[(f"S{i}", 1.0, i) for i in range(10)]),
    }
    curated = curation.top_rank_view(eligible, cap=4, max_per_institute=2)
    assert curated["Target"] == [] and curated["Reach"] == []
    assert len(curated["Safe"]) == 4


def test_flatten_uses_display_order_not_dict_order():
    curated = {
        "Safe": _rows(("S", 1.0, 1)),
        "Reach": _rows(("R", 1.0, 2)),
        "Target": _rows(("T", 1.0, 3)),
    }
    assert [r.institute for r in curation.flatten(curated)] == ["T", "R", "S"]


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


# --------------------------------------------------------------------------
# rounds — round selection, shared by KCET and COMEDK
# --------------------------------------------------------------------------

THREE_ROUNDS = {1: 4628.0, 2: 6389.0, 3: 7213.0}


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("1234", 1234.0),
        ("  1234  ", 1234.0),
        ("1,234", 1234.0),      # the source PDFs print thousands separators
        ("76553.5", 76553.5),   # KEA publishes fractional cut-offs
        ("", None),
        ("   ", None),
        (None, None),
        ("not a rank", None),
    ],
)
def test_parse_number(raw, expected):
    assert rounds.parse_number(raw) == expected


def test_parse_int_truncates():
    assert rounds.parse_int("18.0") == 18
    assert rounds.parse_int("") is None


def test_round_columns_are_discovered_and_sorted():
    columns = rounds.round_columns(
        ["college_name", "closing_rank_r3", "closing_rank_r1", "closing_rank_r2"]
    )
    assert columns == [
        ("closing_rank_r1", 1),
        ("closing_rank_r2", 2),
        ("closing_rank_r3", 3),
    ]


def test_round_columns_never_matches_the_mock_round():
    """COMEDK's mock round allotted no seat, so it must never be selectable as
    a cut-off. The pattern excluding it is the only thing enforcing that."""
    assert rounds.round_columns(["closing_rank_mock", "closing_rank_r1"]) == [
        ("closing_rank_r1", 1)
    ]


def test_ranks_by_round_omits_blank_cells():
    """A blank cell means "allotted no seat that round" — absent, not zero."""
    columns = [("closing_rank_r1", 1), ("closing_rank_r2", 2), ("closing_rank_r3", 3)]
    row = {"closing_rank_r1": "100", "closing_rank_r2": "", "closing_rank_r3": "300"}
    assert rounds.ranks_by_round(row, columns) == {1: 100.0, 3: 300.0}


def test_resolve_rank_strategies():
    assert rounds.resolve_rank(THREE_ROUNDS, rounds.STRATEGY_MAX) == 7213.0
    assert rounds.resolve_rank(THREE_ROUNDS, rounds.STRATEGY_LAST) == 7213.0
    assert rounds.resolve_rank(THREE_ROUNDS, rounds.STRATEGY_FIRST) == 4628.0
    assert rounds.resolve_rank(THREE_ROUNDS, 2) == 6389.0


def test_resolve_rank_max_and_last_differ_when_a_round_tightens():
    """`max` is the most permissive rank ever admitted; `last` is the final
    round's, which can be lower."""
    tightened = {1: 900.0, 2: 500.0}
    assert rounds.resolve_rank(tightened, rounds.STRATEGY_MAX) == 900.0
    assert rounds.resolve_rank(tightened, rounds.STRATEGY_LAST) == 500.0


def test_resolve_rank_returns_none_rather_than_borrowing_another_round():
    assert rounds.resolve_rank({1: 4628.0}, 3) is None
    assert rounds.resolve_rank({}, rounds.STRATEGY_MAX) is None


def test_resolve_rank_treats_true_as_a_strategy_not_round_one():
    """`True` is an `int` in Python; "round True" is a bug, not round 1."""
    assert rounds.resolve_rank(THREE_ROUNDS, True) == 7213.0


def test_strategy_cache_builds_once_per_strategy():
    builds = []

    def build(strategy):
        builds.append(strategy)
        return [strategy]

    cache = rounds.StrategyCache(build, lambda: "max")
    assert cache.get() is cache.get("max")   # the default resolves to a key
    assert cache.get("first") is cache.get("first")
    assert cache.get("first") is not cache.get("max")
    assert builds == ["max", "first"]


def test_strategy_cache_reads_the_default_lazily():
    """The exam's `settings.round_strategy` must be read at call time —
    capturing it at import would freeze whatever the module saw first."""
    default = {"value": "max"}
    cache = rounds.StrategyCache(lambda strategy: [strategy], lambda: default["value"])
    assert cache.get() == ["max"]
    default["value"] = "first"
    assert cache.get() == ["first"]


def test_strategy_cache_does_not_rebuild_an_empty_view():
    """A missing data file logs an error and returns []. Rebuilding on every
    call would turn one logged error into one per request."""
    builds = []

    def build(strategy):
        builds.append(strategy)
        return []

    cache = rounds.StrategyCache(build, lambda: "max")
    cache.get()
    cache.get()
    assert builds == ["max"]

    cache.clear()
    cache.get()
    assert builds == ["max", "max"]


# --------------------------------------------------------------------------
# scoring — the competitiveness percentile
# --------------------------------------------------------------------------


def test_competitiveness_orients_one_at_the_lowest_cutoff():
    """Load-bearing for both exams: 1.0 means "most in demand"."""
    assert scoring.competitiveness([100.0, 500.0, 900.0]) == [1.0, 0.5, 0.0]


def test_competitiveness_of_a_lone_row_is_one():
    """A single-row group is both the most and least competitive thing in it;
    1.0 is the reading that does not penalise a small category."""
    assert scoring.competitiveness([42.0]) == [1.0]
    assert scoring.competitiveness([]) == []


def test_dense_ties_share_a_percentile():
    """COMEDK's choice: two programmes that closed at the same rank are never
    ordered against each other by this key."""
    scores = scoring.competitiveness(
        [100.0, 100.0, 900.0], ties=scoring.TIES_DENSE
    )
    assert scores == [1.0, 1.0, 0.0]


def test_ordinal_ties_take_consecutive_positions():
    """KCET's choice: a category holding thousands of rows stays spread across
    the full range instead of compressing where the data is densest."""
    scores = scoring.competitiveness(
        [100.0, 100.0, 900.0], ties=scoring.TIES_ORDINAL
    )
    assert scores == [1.0, 0.5, 0.0]


def test_ordinal_ties_are_broken_by_input_order_not_hash_order():
    """Stability is what lets the golden baseline assert byte-equality."""
    values = [100.0] * 5
    assert scoring.competitiveness(values, ties=scoring.TIES_ORDINAL) == [
        1.0, 0.75, 0.5, 0.25, 0.0
    ]


def test_competitiveness_by_group_never_ranks_across_groups():
    """A GM cutoff and an STK cutoff are not on the same scale, so each seat
    pool is scored only against itself."""
    rows = [
        {"quota": "GM", "rank": 1_000.0},
        {"quota": "GM", "rank": 9_000.0},
        {"quota": "KKR", "rank": 50_000.0},
        {"quota": "KKR", "rank": 90_000.0},
    ]
    scores = scoring.competitiveness_by_group(
        rows, group_of=lambda r: r["quota"], value_of=lambda r: r["rank"]
    )
    # KKR's 50,000 is the best *KKR* option, so it scores 1.0 despite being
    # numerically far worse than either GM cutoff.
    assert scores == [1.0, 0.0, 1.0, 0.0]


def test_competitiveness_by_group_returns_scores_in_caller_order():
    rows = [
        {"quota": "GM", "rank": 9_000.0},
        {"quota": "KKR", "rank": 50_000.0},
        {"quota": "GM", "rank": 1_000.0},
    ]
    scores = scoring.competitiveness_by_group(
        rows, group_of=lambda r: r["quota"], value_of=lambda r: r["rank"]
    )
    assert scores == [0.0, 1.0, 1.0]
