"""Core KCET recommendation pipeline.

Architecture mirrors the JEE engine (``app/disha/recommender.py``): filter by
eligibility, categorize into Safe/Target/Reach, score by career-goal fit,
order each bucket best-first, curate with an institute-diversity cap, and
detect a "top-rank" collapse the same way JEE does — from the bucket counts,
not a hardcoded rank. The categorization and probability *math* instead
follows COMEDK's approach, because KCET's data has COMEDK's shape: one
published closing rank per row, not JoSAA's opening-closing window. See
config.py for where every constant comes from.

Self-contained: no imports from app.disha.recommender, app.disha.states, or
app.disha.comedk.*.
"""

from __future__ import annotations

from typing import Dict, List, Optional

from . import states
from ..core import curation
# Imported by name: `cutoff` is used as a local variable throughout this
# module, so binding the module to that name would shadow it.
from ..core.cutoff import PointCutoffModel, clamp as _core_clamp
from .config import settings
from .data_loader import KcetProgram, load_programs
from .schemas import (
    CategoryGuidance,
    KcetRecommendation,
    KcetRecommendRequest,
    KcetRecommendResponse,
)

CATEGORY_ORDER = {"Target": 0, "Reach": 1, "Safe": 2}

BUCKET_CAPS = {
    "Target": settings.cap_target,
    "Reach": settings.cap_reach,
    "Safe": settings.cap_safe,
}
MAX_PER_INSTITUTE = settings.max_per_institute
TOP_RANK_CAP = settings.top_rank_cap

_SINGLE_BUCKETS = {
    "safe": "Safe",
    "target": "Target",
    "reach": "Reach",
    "dream": "Reach",
}

FIT_LABELS = {
    "Safe": "Comfortable - your rank is well inside last year's closing rank.",
    "Target": "Achievable - your rank is close to last year's closing rank.",
    "Reach": "Ambitious - just beyond last year's closing rank, but worth a try.",
}

CATEGORY_BLURBS = {
    "Target": (
        "These closed right around your rank last year. They are your most "
        "realistic picks."
    ),
    "Reach": (
        "These closed slightly above your rank last year. Cutoffs move "
        "between rounds, so list a few as ambitious choices."
    ),
    "Safe": (
        "Your rank comfortably beats last year's closing rank here, so these "
        "are strong backups you are very likely to get."
    ),
}


# KCET's cutoff model. Shared with COMEDK — same formulas, KCET's own
# constants, measured from this dataset's distribution (see config.py).
# No dynamic_floor_fraction: KCET uses a flat target-band floor.
CUTOFF_MODEL = PointCutoffModel(
    safe_margin=settings.safe_margin,
    target_band_floor=settings.target_band_floor,
    target_band_ceiling=settings.target_band_ceiling,
    upper_margin=settings.upper_margin,
    reach_band_ceiling=settings.reach_band_ceiling,
    sigma_fraction=settings.sigma_fraction,
    sigma_floor=settings.sigma_floor,
    sigma_ceiling=settings.sigma_ceiling,
    steepness=settings.steepness,
)

_clamp = _core_clamp
_target_band = CUTOFF_MODEL.target_band
_reach_band = CUTOFF_MODEL.reach_band
_categorize = CUTOFF_MODEL.categorize


_z_score = CUTOFF_MODEL.z_score
_calculate_probability = CUTOFF_MODEL.probability_from_z


def _confidence(z: float) -> str:
    """Two-value headroom label, derived from the same z-score as the
    percentage so the two can never disagree on a card.

    Deliberately *not* shared with COMEDK, which uses three values (it adds
    ``borderline``), or with JEE, whose four values describe round-to-round
    volatility rather than headroom. Same field name, different questions.
    """
    return "high" if abs(z) >= 1.5 else "medium"


def _interest_score(prog: KcetProgram, goal: str, ratio: float) -> tuple[float, bool]:
    weights = states.GOAL_TAG_WEIGHTS.get(goal, {})
    branch_score = max((weights.get(t, 0) for t in prog.tags), default=0)
    score = (1.0 - ratio) * branch_score + ratio * prog.quality_score
    return float(score), branch_score > 0


def _build_reason(prog: KcetProgram, category: str, matched: bool, confidence: str) -> str:
    lead = f"{category} for you"
    fit = "strong fit for your goal" if matched else "a sensible option to keep on your list"
    sentence = f"{lead} - {fit} ({prog.program.strip()} at {prog.institute})"
    if prog.seat_category != "GM":
        sentence += f", under the {prog.seat_category_label} category"
    tail = (
        "This cutoff sits in a wide, stable part of the rank range."
        if confidence == "high"
        else "Cutoffs can move a little between rounds, so treat this as an estimate."
    )
    return f"{sentence}. {tail}"


def _order_bucket(rows: List[KcetRecommendation], bucket: str) -> List[KcetRecommendation]:
    """Best-first ordering — see ``core.curation.order_bucket``."""
    return curation.order_bucket(
        rows, bucket, rank_attr="closing_rank", name_attr="program"
    )


# Signature is identical to the shared implementation, so this is a plain
# alias rather than a wrapper.
_curate_bucket = curation.curate_bucket


def recommend(req: KcetRecommendRequest) -> KcetRecommendResponse:
    programs = load_programs()
    wanted_tags = states.tags_for_branch_preferences(req.branch_preferences)

    notes: List[str] = []
    if req.rank > settings.max_rank:
        notes.append(
            f"A rank of {req.rank:,} is well outside KCET's published range and may be a typo."
        )

    results: List[KcetRecommendation] = []
    weakest_reachable: Optional[int] = None

    for prog in programs:
        if prog.seat_category != req.seat_category:
            continue
        if wanted_tags and prog.tags.isdisjoint(wanted_tags):
            continue
        if weakest_reachable is None or prog.closing_rank > weakest_reachable:
            weakest_reachable = prog.closing_rank

        bucket = _categorize(req.rank, prog.closing_rank)
        if bucket is None:
            continue

        score, matched = _interest_score(prog, req.goal, req.brand_branch_ratio)
        z = _z_score(req.rank, prog.closing_rank)
        confidence = _confidence(z)
        prob = _calculate_probability(z)

        results.append(
            KcetRecommendation(
                institute=prog.institute,
                college_code=prog.college_code,
                program=prog.program,
                seat_category=prog.seat_category,
                seat_category_label=prog.seat_category_label,
                closing_rank=prog.closing_rank,
                category=bucket,
                fit_label=FIT_LABELS[bucket],
                interest_score=round(score, 2),
                matched_interest=matched,
                confidence=confidence,
                reason=_build_reason(prog, bucket, matched, confidence),
                quality_score=prog.quality_score,
                admission_probability=prob,
                tags=sorted(prog.tags),
            )
        )

    # ── Curate: order each bucket best-first, then cap ───────────────────
    eligible: Dict[str, List[KcetRecommendation]] = {c: [] for c in CATEGORY_ORDER}
    for r in results:
        eligible[r.category].append(r)
    for cat in eligible:
        eligible[cat] = _order_bucket(eligible[cat], cat)

    count_target, count_reach, count_safe = len(eligible["Target"]), len(eligible["Reach"]), len(eligible["Safe"])
    total_unfiltered = count_target + count_reach + count_safe

    is_top_rank = curation.detect_top_rank(
        total_unfiltered, count_target, count_reach
    )

    requested_bucket = _SINGLE_BUCKETS.get((req.bucket or "all").lower())
    single_bucket = requested_bucket is not None
    if single_bucket:
        curated = {c: [] for c in CATEGORY_ORDER}
        curated[requested_bucket] = eligible[requested_bucket][: req.max_results]
    elif is_top_rank:
        curated = {
            "Target": [],
            "Reach": [],
            "Safe": _curate_bucket(eligible["Safe"], TOP_RANK_CAP, MAX_PER_INSTITUTE),
        }
    else:
        curated = {cat: _curate_bucket(rows, BUCKET_CAPS[cat], MAX_PER_INSTITUTE) for cat, rows in eligible.items()}

    all_matches: List[KcetRecommendation] = []
    for cat in sorted(CATEGORY_ORDER, key=lambda c: CATEGORY_ORDER[c]):
        all_matches.extend(curated[cat])
    shown_count = len(all_matches)

    if wanted_tags:
        valid_prefs = [p for p in req.branch_preferences if p in states.VALID_BRANCH_PREFERENCES]
        pref_labels = {b["value"]: b["label"] for b in states.BRANCH_PREFERENCES}
        branch_names = ", ".join(pref_labels.get(p, p) for p in valid_prefs)
        if total_unfiltered:
            notes.append(
                f"Showing only your preferred branches ({branch_names}). Clear the branch filter to see every eligible option."
            )
        else:
            notes.append(
                f"No options matched your branch preferences ({branch_names}). Try adding more branches or clearing the filter."
            )

    if is_top_rank and not single_bucket:
        notes.append(
            f"Your rank clears the cutoff for all {total_unfiltered} options you are eligible for under "
            f"{req.seat_category}, so there is nothing to mark Target or Dream. Showing the {shown_count} "
            "most competitive of them."
        )
    elif shown_count < total_unfiltered and not single_bucket:
        notes.append(
            f"Showing the {shown_count} strongest picks out of {total_unfiltered} eligible options, with at "
            "most a couple of programmes per college. Open a single section to see every option in it."
        )

    beyond_data = (
        total_unfiltered == 0
        and weakest_reachable is not None
        and req.rank > weakest_reachable + _reach_band(weakest_reachable)
    )
    if total_unfiltered == 0:
        if beyond_data:
            guidance = (
                f"Your rank ({req.rank:,}) is past the last seat you are eligible for under "
                f"{req.seat_category} in this dataset — the weakest cutoff closed at "
                f"{weakest_reachable:,}. Adding a different rank will not change this; try another "
                "category, or check KEA's special/extended rounds."
            )
        else:
            guidance = (
                "No options matched closely. Try double-checking your rank and category, or clear the "
                "branch filter."
            )
    else:
        guidance = (
            f"Found {total_unfiltered} eligible college-programme options for your profile (showing "
            f"{shown_count}). They are grouped into Target, Dream and Safe, and ordered to match your "
            "stated interest."
        )

    interest_guidance = states.GOAL_GUIDANCE.get(req.goal, "")

    counts = {
        "total": total_unfiltered,
        "shown": shown_count,
        "by_category": {"Safe": count_safe, "Target": count_target, "Reach": count_reach},
        "shown_by_category": {
            "Safe": len(curated["Safe"]),
            "Target": len(curated["Target"]),
            "Reach": len(curated["Reach"]),
        },
        "is_curated": shown_count < total_unfiltered,
        "is_top_rank": is_top_rank,
    }

    category_guidance = [
        CategoryGuidance(category=c, count=counts["by_category"][c], blurb=CATEGORY_BLURBS[c])
        for c in CATEGORY_ORDER
        if counts["by_category"][c] > 0
    ]

    return KcetRecommendResponse(
        guidance=guidance,
        interest_guidance=interest_guidance,
        counts=counts,
        notes=notes,
        category_guidance=category_guidance,
        recommendations=all_matches,
        total_count=total_unfiltered,
        thresholds={
            "safe_margin": settings.safe_margin,
            "upper_margin": settings.upper_margin,
            "target_band_floor": settings.target_band_floor,
            "target_band_ceiling": settings.target_band_ceiling,
            "reach_band_ceiling": settings.reach_band_ceiling,
            "caps": dict(BUCKET_CAPS),
            "max_per_institute": MAX_PER_INSTITUTE,
            "top_rank_cap": TOP_RANK_CAP,
        },
    )
