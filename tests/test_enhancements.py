"""Tests for the new enhancements in Disha.

This includes fee waivers, region classification, metro status, and the ratio-blended scoring.
"""

import pytest
from app.disha.recommender import (
    _get_region,
    _is_metro,
    _calculate_fees,
    _interest_score,
)
from app.disha.data_loader import Program


def make_test_program(**kw) -> Program:
    defaults = dict(
        institute="IIT Madras",
        institute_type="IIT",
        institute_state="Tamil Nadu",
        exam="advanced",
        branch="Computer Science and Engineering",
        branch_full="Computer Science and Engineering (4 Years, Bachelor of Technology)",
        degree="Bachelor of Technology",
        quota="AI",
        gender_pool="neutral",
        opening_rank=100,
        closing_rank=500,
        brand_score=0.9,
        tags={"cse"},
    )
    defaults.update(kw)
    return Program(**defaults)


# --------------------------- Region & Metro classification ---------------------------

def test_get_region():
    assert _get_region("Delhi") == "north"
    assert _get_region("Tamil Nadu") == "south"
    assert _get_region("West Bengal") == "east"
    assert _get_region("Maharashtra") == "west"
    assert _get_region("Assam") == "northeast"
    assert _get_region("Unknown State") == "northeast"


def test_is_metro():
    # Metro cities like Mumbai, Delhi, Bengaluru, Chennai, etc. should map to True
    assert _is_metro("IIT Bombay, Mumbai", "Maharashtra") is True
    assert _is_metro("IIT Madras, Chennai", "Tamil Nadu") is True
    assert _is_metro("IIT Delhi", "Delhi") is True
    assert _is_metro("IIT Kharagpur", "West Bengal") is False  # Kharagpur is not a metro city
    assert _is_metro("NIT Trichy", "Tamil Nadu") is False


# --------------------------- Fee and Tuition Waivers ---------------------------

def test_calculate_fees_sc_st_pwd():
    # SC/ST/PwD candidates get 100% waiver at IITs and NITs regardless of income (but pay other charges)
    for cat in ["SC", "ST", "PwD"]:
        fee, waiver, note = _calculate_fees("IIT", "above_5l", cat)
        assert fee == 25000  # other charges only
        assert waiver is True
        assert "tuition waiver applied" in note

        fee, waiver, note = _calculate_fees("NIT", "below_3l", cat)
        assert fee == 15000  # other charges only
        assert waiver is True
        assert "tuition waiver applied" in note


def test_calculate_fees_low_income_general_obc_ews():
    # Income < 3L gets 100% tuition waiver (but pay other charges)
    for cat in ["OPEN", "OBC-NCL", "GEN-EWS"]:
        fee, waiver, note = _calculate_fees("IIT", "below_3l", cat)
        assert fee == 25000  # other charges only
        assert waiver is True
        assert "tuition fee waiver" in note

        fee, waiver, note = _calculate_fees("NIT", "below_3l", cat)
        assert fee == 15000  # other charges only
        assert waiver is True
        assert "tuition fee waiver" in note


def test_calculate_fees_mid_income_general_obc_ews():
    # Income 3L-5L gets 2/3rd tuition waiver (meaning they pay 1/3rd of the tuition fees + other charges)
    for cat in ["OPEN", "OBC-NCL", "GEN-EWS"]:
        fee, waiver, note = _calculate_fees("IIT", "3l_5l", cat)
        assert fee == 91666  # int(200000 / 3) + 25000 = 66666 + 25000 = 91666
        assert waiver is True
        assert "2/3rd tuition fee waiver" in note

        fee, waiver, note = _calculate_fees("NIT", "3l_5l", cat)
        assert fee == 56666  # int(125000 / 3) + 15000 = 41666 + 15000 = 56666
        assert waiver is True
        assert "2/3rd tuition fee waiver" in note


def test_calculate_fees_high_income_general_obc_ews():
    # Income > 5L gets standard fees (no waiver)
    for cat in ["OPEN", "OBC-NCL", "GEN-EWS"]:
        fee, waiver, note = _calculate_fees("IIT", "above_5l", cat)
        assert fee == 225000  # 200k tuition + 25k other
        assert waiver is False
        assert "Standard fees" in note

        fee, waiver, note = _calculate_fees("NIT", "above_5l", cat)
        assert fee == 140000  # 125k tuition + 15k other
        assert waiver is False
        assert "Standard fees" in note


def test_calculate_fees_gfti_iiit_not_eligible_for_standard_mhrd():
    # IIITs and GFTIs do not follow standard MHRD IIT/NIT waiver schemes
    fee, waiver, note = _calculate_fees("IIIT", "below_3l", "OPEN")
    assert fee == 200000  # 180k tuition + 20k other
    assert waiver is False
    assert "no standard income waivers" in note


# --------------------------- Blended scoring ---------------------------

def test_interest_score_pure_branch_focus():
    prog = make_test_program(brand_score=0.9, tags={"cse"})
    # brand_branch_ratio = 0.0 means pure branch focus
    score, matched = _interest_score(prog, "coding", 0.0)
    # matching "coding" with cse program: score should be 10.0 (since it matches branch perfectly)
    assert score == 10.0
    assert matched is True


def test_interest_score_pure_brand_focus():
    prog = make_test_program(brand_score=0.7, tags={"civil"})
    # brand_branch_ratio = 1.0 means pure brand focus
    score, matched = _interest_score(prog, "coding", 1.0)
    # since it's pure brand, score should equal program's brand score * 10 (7.0)
    assert score == 7.0
    # matched is False because "civil" does not match "coding"
    assert matched is False


def test_interest_score_blended():
    prog = make_test_program(brand_score=0.8, tags={"cse"})
    # brand_branch_ratio = 0.5 means 50% brand, 50% branch
    score, matched = _interest_score(prog, "coding", 0.5)
    # branch matching score is 10.0 (matches coding), brand score is 8.0
    # blended score: 0.5 * 8.0 (brand) + 0.5 * 10.0 (branch) = 9.0
    assert score == pytest.approx(9.0)
    assert matched is True
