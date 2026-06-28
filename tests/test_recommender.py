"""Tests for the recommendation pipeline.

Unit tests use small synthetic ``Program`` lists (so they don't depend on exact
dataset values); a couple of integration tests exercise the real workbook
through the FastAPI app.
"""

import pytest

from app.disha import data_loader, recommender
from app.disha.data_loader import (
    Program,
    female_seat_advantage_index,
    home_state_advantage_index,
    load_programs,
)
from app.disha.recommender import (
    _categorize,
    _confidence,
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
        opening_rank=1000,
        closing_rank=2000,
        brand_score=0.7,
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
        (400, None),         # below opening * 0.5 -> overqualified, dropped
    ],
)
def test_categorize(rank, expected):
    assert _categorize(rank, 1000, 2000) == expected


# --------------------------- full pipeline (synthetic) ---------------------------
def _patch_programs(monkeypatch, programs):
    monkeypatch.setattr(recommender, "load_programs", lambda: programs)


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
        # within the kept band
        assert rank <= r.closing_rank * 1.25 + 1
        assert rank >= r.opening_rank * 0.5 - 1


# --------------------------- confidence band ---------------------------
@pytest.mark.parametrize(
    "opening,closing,expected",
    [
        (1000, 1500, "fragile"),    # spread 500 < 1,000 -> fragile
        (1000, 1000, "fragile"),    # zero window -> always fragile
        (5000, 4000, "fragile"),    # closing <= opening -> always fragile
        (1000, 4000, "medium"),     # spread 3,000 (~median) -> medium
        (1000, 8000, "high"),       # spread 7,000 >= 6,000 -> high
    ],
)
def test_confidence_band(opening, closing, expected):
    assert _confidence(opening, closing) == expected


def test_recommendation_has_confidence_and_nonempty_reason():
    req = RecommendRequest(adv_rank=1500, mains_rank=6000, gender="female",
                           home_state="Rajasthan", goal="coding")
    resp = recommend(req)
    assert resp.recommendations
    for r in resp.recommendations:
        assert r.confidence in {"high", "medium", "fragile"}
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
    # A very tight window (spread 300) must be classified fragile end-to-end.
    prog = make_program(opening_rank=1000, closing_rank=1300)
    _patch_programs(monkeypatch, [prog])
    monkeypatch.setattr(recommender, "home_state_advantage_index", lambda: {})
    monkeypatch.setattr(recommender, "female_seat_advantage_index", lambda: {})
    req = RecommendRequest(mains_rank=1200, gender="male",
                           home_state="Rajasthan", goal="coding")
    resp = recommend(req)
    assert resp.recommendations
    rec = resp.recommendations[0]
    assert rec.confidence == "fragile"
    assert "volatile" in rec.reason


# --------------------------- advantage lookup indices ---------------------------
def test_home_state_advantage_index(monkeypatch):
    hs = make_program(quota="HS", opening_rank=2000, closing_rank=5000)
    os_seat = make_program(quota="OS", opening_rank=4000, closing_rank=9000)
    monkeypatch.setattr(data_loader, "load_programs", lambda: [hs, os_seat])
    home_state_advantage_index.cache_clear()
    try:
        idx = home_state_advantage_index()
        key = (hs.institute, hs.branch_full, hs.exam, hs.gender_pool)
        assert idx[key] == 4000  # 9000 (OS) - 5000 (HS)
    finally:
        home_state_advantage_index.cache_clear()


def test_female_seat_advantage_index(monkeypatch):
    neutral = make_program(gender_pool="neutral", closing_rank=3000)
    female = make_program(gender_pool="female", closing_rank=5500)
    monkeypatch.setattr(data_loader, "load_programs", lambda: [neutral, female])
    female_seat_advantage_index.cache_clear()
    try:
        idx = female_seat_advantage_index()
        key = (female.institute, female.branch_full, female.exam, female.quota)
        assert idx[key] == 2500  # 5500 (female) - 3000 (neutral)
    finally:
        female_seat_advantage_index.cache_clear()


def test_home_state_advantage_surfaced_in_recommendation(monkeypatch):
    hs = make_program(quota="HS", institute_state="Rajasthan",
                      opening_rank=2000, closing_rank=5000)
    _patch_programs(monkeypatch, [hs])
    key = (hs.institute, hs.branch_full, hs.exam, hs.gender_pool)
    monkeypatch.setattr(recommender, "home_state_advantage_index", lambda: {key: 4000})
    monkeypatch.setattr(recommender, "female_seat_advantage_index", lambda: {})
    req = RecommendRequest(mains_rank=4500, gender="male",
                           home_state="Rajasthan", goal="coding")
    resp = recommend(req)
    assert resp.recommendations
    rec = resp.recommendations[0]
    assert rec.home_state_advantage == 4000
    assert "cushion" in rec.reason


def test_female_seat_advantage_surfaced_in_recommendation(monkeypatch):
    female = make_program(quota="AI", gender_pool="female",
                          opening_rank=2000, closing_rank=5000)
    _patch_programs(monkeypatch, [female])
    key = (female.institute, female.branch_full, female.exam, female.quota)
    monkeypatch.setattr(recommender, "home_state_advantage_index", lambda: {})
    monkeypatch.setattr(recommender, "female_seat_advantage_index", lambda: {key: 2500})
    req = RecommendRequest(mains_rank=4500, gender="female",
                           home_state="Rajasthan", goal="coding")
    resp = recommend(req)
    assert resp.recommendations
    rec = resp.recommendations[0]
    assert rec.female_seat_advantage == 2500
    assert "later" in rec.reason
