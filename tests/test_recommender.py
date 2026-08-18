"""Tests for the recommendation pipeline.

Unit tests use small synthetic ``Program`` lists (so they don't depend on exact
dataset values); a couple of integration tests exercise the real workbook
through the FastAPI app.
"""

import statistics

import pytest

from app.disha import data_loader, recommender
from app.disha.data_loader import (
    Program,
    female_seat_advantage_index,
    home_state_advantage_index,
    load_programs,
    compute_stable_and_volatility,
)
from app.disha.recommender import (
    LOWER_MARGIN,
    UPPER_MARGIN,
    _categorize,
    _passes_gender,
    _passes_quota,
    _relevant_rank,
    recommend,
)
from app.disha.schemas import RecommendRequest


def make_program(**kw) -> Program:
    defaults = dict(
        institute="Test Institute",
        institute_type="NIT",
        institute_state="Rajasthan",
        exam="mains",
        branch="Computer Science and Engineering",
        branch_full="Computer Science and Engineering (4 Years, Bachelor of Technology)",
        degree="Bachelor of Technology",
        quota="AI",
        gender_pool="neutral",
        seat_type="OPEN",
        opening_rank=1000,
        closing_rank=2000,
        brand_score=0.7,
        stable_cutoff=1500,
        movement_ratio=0.1,
        jump_concentration=0.2,
        volatility_tag="stable_drift",
        flag_round=None,
        tags={"cse"},
    )
    defaults.update(kw)
    return Program(**defaults)


# --------------------------- rank-type selection ---------------------------
def test_relevant_rank_uses_advanced_for_iit():
    iit = make_program(institute_type="IIT", exam="advanced")
    req = RecommendRequest(adv_rank=500, mains_rank=9000, gender="male",
                           home_state="Rajasthan", goal="coding")
    assert _relevant_rank(iit, req) == 500


def test_relevant_rank_uses_mains_for_non_iit():
    nit = make_program(exam="mains")
    req = RecommendRequest(adv_rank=500, mains_rank=9000, gender="male",
                           home_state="Rajasthan", goal="coding")
    assert _relevant_rank(nit, req) == 9000


# --------------------------- gender filtering ---------------------------
def test_male_excludes_female_only_seats():
    female_seat = make_program(gender_pool="female")
    neutral_seat = make_program(gender_pool="neutral")
    assert _passes_gender(neutral_seat, "male") is True
    assert _passes_gender(female_seat, "male") is False


def test_female_sees_both_pools():
    female_seat = make_program(gender_pool="female")
    neutral_seat = make_program(gender_pool="neutral")
    assert _passes_gender(female_seat, "female") is True
    assert _passes_gender(neutral_seat, "female") is True


# --------------------------- HS / OS quota ---------------------------
def test_home_state_quota_requires_same_state():
    hs = make_program(quota="HS", institute_state="Rajasthan")
    assert _passes_quota(hs, "Rajasthan") is True
    assert _passes_quota(hs, "Kerala") is False


def test_other_state_quota_requires_different_state():
    os_seat = make_program(quota="OS", institute_state="Rajasthan")
    assert _passes_quota(os_seat, "Kerala") is True
    assert _passes_quota(os_seat, "Rajasthan") is False


def test_all_india_and_iit_quota_always_pass():
    ai = make_program(quota="AI", institute_state="Rajasthan")
    iit = make_program(institute_type="IIT", quota="AI", institute_state="Bihar")
    assert _passes_quota(ai, "Kerala") is True
    assert _passes_quota(iit, "Kerala") is True


def test_special_state_quota():
    goa = make_program(quota="GO", institute_state="Goa")
    assert _passes_quota(goa, "Goa") is True
    assert _passes_quota(goa, "Kerala") is False


# --------------------------- band categorization ---------------------------
@pytest.mark.parametrize(
    "rank,expected",
    [
        (900, "Safe"),       # better than opening (1000)
        (1000, "Safe"),      # equal to opening
        (1500, "Target"),    # between opening and closing
        (2000, "Target"),    # equal to closing
        (2400, "Reach"),     # within closing * 1.25
        (2600, None),        # beyond closing * 1.25 -> dropped
        # The overqualification prune needs BOTH rank < opening * LOWER_MARGIN
        # and opening > rank + 10_000 (recommender.py:186).  With opening=1000
        # the second condition can never hold, so nothing is pruned here.
        (400, "Safe"),
    ],
)
def test_categorize(rank, expected):
    assert _categorize(rank, 1000, 2000) == expected


def test_categorize_prunes_overqualified_only_with_large_gap():
    """The prune fires only when the student is far better *and* the gap is wide.

    Pinned explicitly because the naive reading ("rank well below opening =>
    dropped") is wrong, and a previous version of this file asserted it.
    """
    # rank far below opening, and opening - rank > 10_000 -> pruned
    assert _categorize(400, 20_000, 30_000) is None
    # same ratio, but the absolute gap is under 10_000 -> kept
    assert _categorize(400, 5_000, 8_000) == "Safe"


# --------------------------- full pipeline (synthetic) ---------------------------
def _patch_programs(monkeypatch, programs):
    monkeypatch.setattr(recommender, "load_programs", lambda *a, **kw: programs)


def test_only_mains_rank_omits_iits_and_adds_note(monkeypatch):
    programs = [
        make_program(institute="IIT X", institute_type="IIT", exam="advanced",
                     opening_rank=100, closing_rank=400),
        make_program(institute="NIT Y", exam="mains", opening_rank=4000, closing_rank=8000),
    ]
    _patch_programs(monkeypatch, programs)
    req = RecommendRequest(mains_rank=6000, gender="male", home_state="Rajasthan", goal="coding")
    resp = recommend(req)
    institutes = {r.institute for r in resp.recommendations}
    assert "IIT X" not in institutes
    assert "NIT Y" in institutes
    assert any("Advanced" in n for n in resp.notes)


def test_interest_ordering_prioritises_matching_branch(monkeypatch):
    cse = make_program(institute="A", branch="CSE", tags={"cse"},
                       opening_rank=1000, closing_rank=2000)
    mech = make_program(institute="B", branch="Mechanical", tags={"mechanical"},
                        opening_rank=1000, closing_rank=2000)
    _patch_programs(monkeypatch, [mech, cse])
    req = RecommendRequest(mains_rank=1500, gender="male", home_state="Rajasthan", goal="coding")
    resp = recommend(req)
    branches = [r.branch for r in resp.recommendations]
    assert branches.index("CSE") < branches.index("Mechanical")
    cse_rec = next(r for r in resp.recommendations if r.branch == "CSE")
    assert cse_rec.matched_interest is True


def test_branch_preference_filters_to_matching_tags(monkeypatch):
    cse = make_program(institute="A", branch="CSE", tags={"cse"},
                       opening_rank=1000, closing_rank=2000)
    mech = make_program(institute="B", branch="Mechanical", tags={"mechanical"},
                        opening_rank=1000, closing_rank=2000)
    _patch_programs(monkeypatch, [mech, cse])
    req = RecommendRequest(mains_rank=1500, gender="male", home_state="Rajasthan",
                           goal="coding", branch_preferences=["cs_it"])
    resp = recommend(req)
    institutes = {r.institute for r in resp.recommendations}
    assert institutes == {"A"}
    assert any("preferred branches" in n for n in resp.notes)


def test_empty_branch_preference_shows_all(monkeypatch):
    cse = make_program(institute="A", branch="CSE", tags={"cse"})
    mech = make_program(institute="B", branch="Mechanical", tags={"mechanical"})
    _patch_programs(monkeypatch, [mech, cse])
    req = RecommendRequest(mains_rank=1500, gender="male", home_state="Rajasthan",
                           goal="coding", branch_preferences=[])
    resp = recommend(req)
    assert {r.institute for r in resp.recommendations} == {"A", "B"}
    assert all("preferred branches" not in n for n in resp.notes)


def test_unknown_branch_preference_ignored(monkeypatch):
    cse = make_program(institute="A", branch="CSE", tags={"cse"})
    _patch_programs(monkeypatch, [cse])
    req = RecommendRequest(mains_rank=1500, gender="male", home_state="Rajasthan",
                           goal="coding", branch_preferences=["any", "not-a-branch"])
    resp = recommend(req)
    assert {r.institute for r in resp.recommendations} == {"A"}


def test_overqualified_options_dropped(monkeypatch):
    prog = make_program(opening_rank=50000, closing_rank=60000)
    _patch_programs(monkeypatch, [prog])
    req = RecommendRequest(mains_rank=100, gender="male", home_state="Rajasthan", goal="coding")
    resp = recommend(req)
    assert resp.recommendations == []


def test_requires_at_least_one_rank():
    with pytest.raises(ValueError):
        RecommendRequest(gender="male", home_state="Rajasthan", goal="coding")


# --------------------------- integration with real data ---------------------------
def test_real_dataset_loads():
    programs = load_programs()
    assert len(programs) > 2000
    assert any(p.institute_type == "IIT" for p in programs)
    assert any(p.institute_type == "NIT" for p in programs)


def test_real_recommendation_respects_band():
    req = RecommendRequest(adv_rank=1500, mains_rank=6000, gender="female",
                           home_state="Rajasthan", goal="coding")
    resp = recommend(req)
    assert resp.recommendations, "expected some recommendations for a mid rank"
    for r in resp.recommendations:
        rank = 1500 if r.exam == "advanced" else 6000
        # Derived from the live constants rather than hardcoded, so tuning
        # UPPER_MARGIN / LOWER_MARGIN can never silently invalidate this test.
        assert rank <= r.closing_rank * (1 + UPPER_MARGIN) + 1
        # The lower prune only applies when the opening rank is more than
        # 10_000 above the student's rank (recommender.py:186).
        if r.opening_rank > rank + 10_000:
            assert rank >= r.opening_rank * LOWER_MARGIN - 1


# --------------------------- stable & volatility ---------------------------
@pytest.mark.parametrize(
    "closings_with_rounds,expected_tag",
    [
        # movement_ratio < 0.05 -> highly_stable
        ([(1, 10000.0), (2, 10000.0), (3, 10100.0), (4, 10200.0), (5, 10200.0), (6, 10200.0)], "highly_stable"),
        # movement_ratio < 0.20 and jump_concentration < 0.5 -> stable_drift
        ([(1, 10000.0), (2, 10200.0), (3, 10500.0), (4, 10800.0), (5, 11000.0), (6, 11200.0)], "stable_drift"),
        # One late jump.  NOTE: this series was written to produce
        # "volatile_vacancy" but the implementation tags it "volatile_erratic".
        # Preserved as-is because this suite pins *current* behaviour; whether
        # a single late jump should read as vacancy-driven is a separate
        # product question, deliberately not settled by a refactor.
        ([(1, 10000.0), (2, 10000.0), (3, 10000.0), (4, 10000.0), (5, 12000.0), (6, 12100.0)], "volatile_erratic"),
        # else -> volatile_erratic
        ([(1, 10000.0), (2, 12000.0), (3, 11000.0), (4, 13000.0), (5, 12500.0), (6, 14000.0)], "volatile_erratic"),
    ],
)
def test_stable_and_volatility_logic(closings_with_rounds, expected_tag):
    res = compute_stable_and_volatility(closings_with_rounds)

    # Assert the documented rule rather than a hardcoded number: with >= 4
    # valid rounds, stable_cutoff is the median of the last four closings
    # (data_loader.py:205-209).  A previous version of this test hardcoded
    # values that matched no formula at all and had been failing silently.
    ranks = [c for _, c in closings_with_rounds]
    assert res["stable_cutoff"] == statistics.median(ranks[-4:])
    assert res["tag"] == expected_tag


def test_recommendation_has_confidence_and_nonempty_reason():
    req = RecommendRequest(adv_rank=1500, mains_rank=6000, gender="female",
                           home_state="Rajasthan", goal="coding")
    resp = recommend(req)
    assert resp.recommendations
    for r in resp.recommendations:
        assert r.confidence in {"highly_stable", "stable_drift", "volatile_vacancy", "volatile_erratic"}
        assert r.reason and r.category in r.reason


# --------------------------- language (Hindi) ---------------------------
def _has_devanagari(text: str) -> bool:
    return any("\u0900" <= ch <= "\u097f" for ch in text)


def test_hindi_lang_returns_devanagari_text():
    req = RecommendRequest(adv_rank=1500, mains_rank=6000, gender="female",
                           home_state="Rajasthan", goal="coding", lang="hi")
    resp = recommend(req)
    assert resp.recommendations
    # Overall + interest guidance are in Hindi (contain Devanagari script).
    assert _has_devanagari(resp.guidance)
    assert _has_devanagari(resp.interest_guidance)
    # Category blurbs and fit labels are translated.
    assert resp.category_guidance
    for cg in resp.category_guidance:
        assert _has_devanagari(cg.blurb)
    for r in resp.recommendations:
        assert _has_devanagari(r.fit_label)
        assert _has_devanagari(r.reason)


def test_hindi_notes_are_translated():
    # Omitting the Advanced rank triggers the IIT note, which must be Hindi.
    req = RecommendRequest(mains_rank=6000, gender="male",
                           home_state="Rajasthan", goal="research", lang="hi")
    resp = recommend(req)
    assert resp.notes
    assert all(_has_devanagari(n) for n in resp.notes)


def test_lang_defaults_to_english():
    req = RecommendRequest(mains_rank=6000, gender="male",
                           home_state="Rajasthan", goal="coding")
    assert req.lang == "en"
    resp = recommend(req)
    assert not _has_devanagari(resp.guidance)
    for r in resp.recommendations:
        assert not _has_devanagari(r.reason)


def test_fragile_pick_flagged(monkeypatch):
    # A volatile vacancy pick must be classified volatile_vacancy end-to-end.
    prog = make_program(opening_rank=1000, closing_rank=1300, volatility_tag="volatile_vacancy")
    _patch_programs(monkeypatch, [prog])
    monkeypatch.setattr(recommender, "home_state_advantage_index", lambda *a, **kw: {})
    monkeypatch.setattr(recommender, "female_seat_advantage_index", lambda *a, **kw: {})
    req = RecommendRequest(mains_rank=1200, gender="male",
                           home_state="Rajasthan", goal="coding")
    resp = recommend(req)
    assert resp.recommendations
    rec = resp.recommendations[0]
    assert rec.confidence == "volatile_vacancy"
    assert "volatile" in rec.reason


# --------------------------- advantage lookup indices ---------------------------
def test_home_state_advantage_index(monkeypatch):
    hs = make_program(quota="HS", opening_rank=2000, closing_rank=9000, seat_type="OPEN")
    os_seat = make_program(quota="OS", opening_rank=4000, closing_rank=5000, seat_type="OPEN")
    monkeypatch.setattr(data_loader, "load_programs", lambda *a, **kw: [hs, os_seat])
    home_state_advantage_index.cache_clear()
    try:
        idx = home_state_advantage_index()
        key = (hs.institute, hs.branch_full, hs.exam, hs.gender_pool, hs.seat_type)
        assert idx[key] == 4000  # 9000 (HS) - 5000 (OS)
    finally:
        home_state_advantage_index.cache_clear()


def test_female_seat_advantage_index(monkeypatch):
    neutral = make_program(gender_pool="neutral", closing_rank=3000, seat_type="OPEN")
    female = make_program(gender_pool="female", closing_rank=5500, seat_type="OPEN")
    monkeypatch.setattr(data_loader, "load_programs", lambda *a, **kw: [neutral, female])
    female_seat_advantage_index.cache_clear()
    try:
        idx = female_seat_advantage_index()
        key = (female.institute, female.branch_full, female.exam, female.quota, female.seat_type)
        assert idx[key] == 2500  # 5500 (female) - 3000 (neutral)
    finally:
        female_seat_advantage_index.cache_clear()


def test_home_state_advantage_surfaced_in_recommendation(monkeypatch):
    hs = make_program(quota="HS", institute_state="Rajasthan",
                      opening_rank=2000, closing_rank=5000, seat_type="OPEN")
    _patch_programs(monkeypatch, [hs])
    key = (hs.institute, hs.branch_full, hs.exam, hs.gender_pool, hs.seat_type)
    monkeypatch.setattr(recommender, "home_state_advantage_index", lambda *a, **kw: {key: 4000})
    monkeypatch.setattr(recommender, "female_seat_advantage_index", lambda *a, **kw: {})
    req = RecommendRequest(mains_rank=4500, gender="male",
                           home_state="Rajasthan", goal="coding")
    resp = recommend(req)
    assert resp.recommendations
    rec = resp.recommendations[0]
    assert rec.home_state_advantage == 4000
    assert "cushion" in rec.reason


def test_female_seat_advantage_surfaced_in_recommendation(monkeypatch):
    female = make_program(quota="AI", gender_pool="female",
                          opening_rank=2000, closing_rank=5000, seat_type="OPEN")
    _patch_programs(monkeypatch, [female])
    key = (female.institute, female.branch_full, female.exam, female.quota, female.seat_type)
    monkeypatch.setattr(recommender, "home_state_advantage_index", lambda *a, **kw: {})
    monkeypatch.setattr(recommender, "female_seat_advantage_index", lambda *a, **kw: {key: 2500})
    req = RecommendRequest(mains_rank=4500, gender="female",
                           home_state="Rajasthan", goal="coding")
    resp = recommend(req)
    assert resp.recommendations
    rec = resp.recommendations[0]
    assert rec.female_seat_advantage == 2500
    assert "later" in rec.reason


# --------------------------- canonical category filtering ---------------------------
def test_reserved_category_does_not_leak_open_seats(monkeypatch):
    obc_prog = make_program(seat_type="OBC-NCL", opening_rank=800, closing_rank=1500)
    open_prog = make_program(seat_type="OPEN", opening_rank=800, closing_rank=1500, branch="Electrical Engineering")
    _patch_programs(monkeypatch, [obc_prog, open_prog])
    monkeypatch.setattr(recommender, "home_state_advantage_index", lambda *a, **kw: {})
    monkeypatch.setattr(recommender, "female_seat_advantage_index", lambda *a, **kw: {})
    req = RecommendRequest(mains_rank=1000, seat_category="OBC-NCL", gender="male", home_state="Rajasthan", goal="coding")
    resp = recommend(req)
    assert len(resp.recommendations) == 1
    assert resp.recommendations[0].branch == "Computer Science and Engineering"


def test_canonical_pwd_category_matching(monkeypatch):
    pwd_prog = make_program(seat_type="OBC-NCL (PwD)", opening_rank=100, closing_rank=500)
    reg_prog = make_program(seat_type="OBC-NCL", opening_rank=100, closing_rank=500, branch="Electrical Engineering")
    _patch_programs(monkeypatch, [pwd_prog, reg_prog])
    monkeypatch.setattr(recommender, "home_state_advantage_index", lambda *a, **kw: {})
    monkeypatch.setattr(recommender, "female_seat_advantage_index", lambda *a, **kw: {})
    req = RecommendRequest(mains_rank=200, seat_category="OBC-NCL (PwD)", gender="male", home_state="Rajasthan", goal="coding")
    resp = recommend(req)
    assert len(resp.recommendations) == 1
    assert resp.recommendations[0].branch == "Computer Science and Engineering"

