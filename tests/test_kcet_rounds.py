"""Unit tests for KCET's round-wise cut-off handling.

The KCET dataset keeps every round KEA published; the loader picks one number
per programme to recommend against. The golden suite exercises only the default
(`max`), so these pin the selection logic itself — especially that the raw
round-wise history survives loading, which is the whole point of storing all
rounds rather than only the final one.
"""

from __future__ import annotations

import pytest

from app.disha.core import rounds as core_rounds
from app.disha.kcet import data_loader
from app.disha.kcet.data_loader import (
    STRATEGY_FIRST,
    STRATEGY_LAST,
    STRATEGY_MAX,
    _resolve_rank,
    get_available_rounds,
    load_programs,
)


# ── The selection logic itself ──────────────────────────────────────────────
#
# Round selection is exam-agnostic and now lives in `app/disha/core/rounds.py`,
# shared with COMEDK; every strategy, the int-round case, the empty history and
# the `True is not round 1` trap are pinned in `tests/test_core.py`. What is
# still KCET's own — and tested here — is that this loader keeps using it, and
# what the real KEA dataset does when it does.

THREE_ROUNDS = {1: 4628.0, 2: 6389.0, 3: 7213.0}


def test_kcet_selects_rounds_through_the_shared_implementation():
    """The re-export is the contract: KCET must not grow a second copy of the
    selection logic that could drift from COMEDK's."""
    assert _resolve_rank is core_rounds.resolve_rank
    assert _resolve_rank(THREE_ROUNDS, STRATEGY_MAX) == 7213.0
    assert _resolve_rank(THREE_ROUNDS, STRATEGY_FIRST) == 4628.0
    assert _resolve_rank(THREE_ROUNDS, STRATEGY_LAST) == 7213.0


# ── Loader integration: the real dataset ────────────────────────────────────


def test_dataset_carries_every_round():
    assert get_available_rounds() == [1, 2, 3]


def test_default_strategy_is_max():
    assert data_loader.settings.round_strategy == STRATEGY_MAX
    assert load_programs() is load_programs(STRATEGY_MAX)


def test_round_history_survives_loading():
    """The raw round-wise record is retained per programme, so a round-specific
    question never needs the CSV re-read."""
    programs = load_programs()
    multi = [p for p in programs if len(p.closing_rank_by_round) > 1]
    assert multi, "expected programmes appearing in more than one round"

    sample = multi[0]
    assert sample.rounds == tuple(sorted(sample.rounds)), "rounds must be ascending"
    for round_no, rank in sample.closing_rank_by_round:
        assert sample.rank_in_round(round_no) == rank
    assert sample.rank_in_round(99) is None


@pytest.mark.parametrize("strategy", [STRATEGY_MAX, STRATEGY_LAST, STRATEGY_FIRST])
def test_selected_rank_always_matches_the_retained_history(strategy):
    """Whatever a strategy picks must be one of the ranks KEA actually
    published for that programme — never a computed or borrowed value."""
    for program in load_programs(strategy):
        published = dict(program.closing_rank_by_round)
        assert program.closing_rank in published.values()


def test_full_coverage_strategies_keep_every_programme():
    """`max`, `last` and `first` each resolve for any non-empty history, so all
    three must cover the same programme set."""
    baseline = len(load_programs(STRATEGY_MAX))
    assert len(load_programs(STRATEGY_LAST)) == baseline
    assert len(load_programs(STRATEGY_FIRST)) == baseline


def test_single_round_view_is_a_strict_subset():
    """A fixed round drops programmes that did not allot in it — the documented
    trade-off that makes `max` rather than round 3 the default."""
    everything = load_programs(STRATEGY_MAX)
    round_three = load_programs(3)
    assert 0 < len(round_three) < len(everything)

    key = lambda p: (p.college_code, p.program, p.seat_category)
    assert {key(p) for p in round_three} <= {key(p) for p in everything}
    for program in round_three:
        assert program.closing_rank == program.rank_in_round(3)


def test_quality_score_is_recomputed_per_strategy():
    """quality_score is a percentile of closing_rank within a category, so it
    is only meaningful against the ranks the active strategy selected."""
    by_key = {}
    for program in load_programs(STRATEGY_MAX):
        by_key[(program.college_code, program.program, program.seat_category)] = program

    moved = 0
    for program in load_programs(STRATEGY_FIRST):
        other = by_key.get((program.college_code, program.program, program.seat_category))
        if other and program.closing_rank != other.closing_rank:
            if program.quality_score != other.quality_score:
                moved += 1
    assert moved, "expected differing cutoffs to produce differing quality scores"


def test_views_are_cached_per_strategy():
    assert load_programs(STRATEGY_FIRST) is load_programs(STRATEGY_FIRST)
    assert load_programs(1) is load_programs(1)
    assert load_programs(1) is not load_programs(2)
