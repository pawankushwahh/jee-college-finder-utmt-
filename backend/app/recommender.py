"""Core recommendation pipeline: take a student profile and return a filtered,
categorized and interest-ranked list of institute + branch options.
"""

from __future__ import annotations

from typing import List, Optional

from . import states
from .data_loader import Program, load_programs
from .schemas import (
    CategoryGuidance,
    Recommendation,
    RecommendRequest,
    RecommendResponse,
)

# How far past the closing rank we still treat an option as a (Reach) possibility.
UPPER_MARGIN = 0.25
# How far below the opening rank before we consider the student "overqualified"
# (i.e. they should be aiming materially higher) and drop the option.
LOWER_MARGIN = 0.50

# Display order of the three buckets.
CATEGORY_ORDER = {"Target": 0, "Reach": 1, "Safe": 2}

FIT_LABELS = {
    "Safe": "Comfortable - your rank is better than last year's opening rank.",
    "Target": "Achievable - your rank lies within last year's opening to closing range.",
    "Reach": "Ambitious - just beyond last year's closing rank, but worth a try.",
}

CATEGORY_BLURBS = {
    "Target": (
        "These match your rank closely (within last year's opening-closing "
        "window). They are your most realistic picks."
    ),
    "Reach": (
        "These closed slightly above your rank last year. Cutoffs fluctuate, so "
        "list a few as ambitious choices."
    ),
    "Safe": (
        "Your rank comfortably beats last year's opening rank here, so these are "
        "strong backups you are very likely to get."
    ),
}


def _relevant_rank(prog: Program, req: RecommendRequest) -> Optional[int]:
    return req.adv_rank if prog.exam == "advanced" else req.mains_rank


def _passes_gender(prog: Program, gender: str) -> bool:
    if gender == "female":
        return True  # female applicants are eligible for both pools
    return prog.gender_pool == "neutral"


def _passes_quota(prog: Program, home_state: str) -> bool:
    quota = prog.quota
    if prog.institute_type == "IIT" or quota == "AI":
        return True
    if quota == "HS":
        return prog.institute_state == home_state
    if quota == "OS":
        return prog.institute_state != home_state
    if quota in states.SPECIAL_QUOTA_STATE:
        return states.SPECIAL_QUOTA_STATE[quota] == home_state
    return True


def _categorize(rank: int, opening: int, closing: int) -> Optional[str]:
    """Return Safe/Target/Reach, or None if the option should be dropped."""
    if rank > closing * (1 + UPPER_MARGIN):
        return None  # no realistic chance
    if rank < opening * (1 - LOWER_MARGIN):
        return None  # heavily overqualified - aim higher
    if rank <= opening:
        return "Safe"
    if rank <= closing:
        return "Target"
    return "Reach"


def _interest_score(prog: Program, goal: str) -> tuple[float, bool]:
    weights = states.GOAL_TAG_WEIGHTS.get(goal, {})
    base = max((weights.get(t, 0) for t in prog.tags), default=0)
    brand_sensitivity = states.GOAL_BRAND_SENSITIVE.get(goal, 0.0)
    score = base + brand_sensitivity * prog.brand_score * 5.0
    return float(score), base > 0


def recommend(req: RecommendRequest) -> RecommendResponse:
    programs = load_programs()
    notes: List[str] = []

    if req.adv_rank is None:
        notes.append(
            "No JEE Advanced rank provided, so IITs are not shown. Add an "
            "Advanced rank to include them."
        )
    if req.mains_rank is None:
        notes.append(
            "No JEE Mains rank provided, so NITs / IIITs / GFTIs are not shown. "
            "Add a Mains rank to include them."
        )
    if req.seat_category != "OPEN":
        notes.append(
            f"Category '{req.seat_category}' is not yet supported — the current dataset "
            "contains OPEN (CRL) seats only. Results shown are for OPEN seats. "
            "Reserved-category cutoffs will be added in a future data release."
        )
    if req.home_state not in states.INDIAN_STATES:
        notes.append(
            f"Home state '{req.home_state}' was not recognised, so Home-State "
            "quota seats may be missed. Pick a state from the list for accurate "
            "results."
        )

    results: List[Recommendation] = []
    for prog in programs:
        rank = _relevant_rank(prog, req)
        if rank is None:
            continue
        if not _passes_gender(prog, req.gender):
            continue
        if not _passes_quota(prog, req.home_state):
            continue
        category = _categorize(rank, prog.opening_rank, prog.closing_rank)
        if category is None:
            continue
        score, matched = _interest_score(prog, req.goal)
        results.append(
            Recommendation(
                institute=prog.institute,
                institute_type=prog.institute_type,
                institute_state=prog.institute_state,
                exam=prog.exam,
                branch=prog.branch,
                branch_full=prog.branch_full,
                degree=prog.degree,
                quota=prog.quota,
                gender_pool=prog.gender_pool,
                opening_rank=prog.opening_rank,
                closing_rank=prog.closing_rank,
                category=category,
                fit_label=FIT_LABELS[category],
                interest_score=round(score, 2),
                matched_interest=matched,
            )
        )

    results.sort(
        key=lambda r: (
            CATEGORY_ORDER[r.category],
            -r.interest_score,
            r.closing_rank,
            r.institute,
            r.branch,
        )
    )

    total_found = len(results)
    results = results[: req.max_results]

    counts = {
        "total": total_found,
        "shown": len(results),
        "by_category": {c: sum(1 for r in results if r.category == c) for c in CATEGORY_ORDER},
        "by_type": {
            t: sum(1 for r in results if r.institute_type == t)
            for t in ("IIT", "NIT", "IIIT", "GFTI")
        },
    }

    category_guidance = [
        CategoryGuidance(
            category=c,
            count=counts["by_category"][c],
            blurb=CATEGORY_BLURBS[c],
        )
        for c in CATEGORY_ORDER
        if counts["by_category"][c] > 0
    ]

    if total_found == 0:
        overall = (
            "No options matched closely. Your rank may be far from this dataset's "
            "cutoffs for the chosen filters - try providing the other rank, or "
            "double-check your gender / home-state selection."
        )
    else:
        overall = (
            f"Found {total_found} eligible institute-branch options for your "
            f"profile (showing {len(results)}). They are grouped into Target, "
            "Reach and Safe, and ordered to match your stated interest."
        )

    interest_guidance = states.GOAL_GUIDANCE.get(req.goal, "")

    return RecommendResponse(
        guidance=overall,
        interest_guidance=interest_guidance,
        counts=counts,
        notes=notes,
        category_guidance=category_guidance,
        recommendations=results,
    )
