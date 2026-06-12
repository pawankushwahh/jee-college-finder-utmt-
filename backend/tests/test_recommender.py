"""Tests for the recommendation pipeline.

Unit tests use small synthetic ``Program`` lists (so they don't depend on exact
dataset values); a couple of integration tests exercise the real workbook
through the FastAPI app.
"""

import pytest

from app import recommender
from app.data_loader import Program, load_programs
from app.recommender import (
    _categorize,
    _passes_gender,
    _passes_quota,
    _relevant_rank,
    recommend,
)
from app.schemas import RecommendRequest


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
