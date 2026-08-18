"""Core KCET recommendation pipeline.

Runs the same six stages every exam in this repo runs — filter by eligibility,
categorize into Safe/Target/Reach, score, explain, order each bucket
best-first, curate with an institute-diversity cap — and the stage *rules* come
from ``app/disha/core/``, so KCET and COMEDK cannot drift apart on what
"Target" or "best first" means.

What is KCET's own, and why (see ``docs/EXAM_DIFFERENCES.md`` for the full
inventory):

* **Bucketing reads the observed round range**, not a modelled band. KEA
  publishes three rounds, so the tough and loose ends of what was actually
  admitted are data rather than an assumption — ``RangeCutoffModel``, where
  COMEDK uses ``PointCutoffModel``.
* **A relevance window** decides whether an option is worth showing at all,
  separately from which bucket it lands in, with a top-up when the window is
  tighter than a usable list. COMEDK has no equivalent: its bands are narrow
  enough that bucketing alone does the job.
* **Two confidence values**, not COMEDK's three.
* **Eligibility is an exact seat-category code** out of 48 spanning two seat
  pools, where COMEDK has two quotas.
* **Top-rank mode is detected from bucket counts alone**, with no rank gate,
  and loses to an explicit single-bucket request.

Self-contained apart from core: no imports from app.disha.recommender,
app.disha.states, or app.disha.comedk.*.
"""

from __future__ import annotations

from typing import Dict, List, Optional

from . import states
from ..core import curation
# Imported by name: `cutoff` is used as a local variable throughout this
# module, so binding the module to that name would shadow it.
from ..core.cutoff import PointCutoffModel, RangeCutoffModel, clamp as _core_clamp
from .config import settings
from .data_loader import KcetProgram, load_programs
from .schemas import (
    CategoryGuidance,
    KcetRecommendation,
    KcetRecommendRequest,
    KcetRecommendResponse,
)

CATEGORY_ORDER = curation.BUCKET_ORDER

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


# Bucketing from the range of ranks KEA actually admitted across the rounds,
# rather than a band modelled around a single number. See config.py for the
# measurements that motivated the switch.
RANGE_MODEL = RangeCutoffModel(
    steepness=settings.steepness,
    safe_buffer_fraction=settings.safe_buffer_fraction,
    sigma_floor=settings.sigma_floor,
)


def _relevance_sigma(low: float) -> float:
    return _core_clamp(
        settings.relevance_sigma_fraction * low,
        settings.relevance_sigma_floor,
        settings.relevance_sigma_ceiling,
    )


def _is_relevant(rank: int, prog: KcetProgram) -> bool:
    """Is this option close enough to the student's rank to be worth listing?

    Separate from bucketing on purpose. A programme's own band decides *which*
    bucket it lands in, but it cannot decide whether to show it at all — the
    weakest programmes have the widest bands, so they would qualify as Safe at
    every rank. Without this a rank-100 student was offered 1,576 "Safe"
    options running out to cut-off 262,158, each labelled 100% probability.
    """
    return (prog.rank_low - rank) / _relevance_sigma(prog.rank_low) <= settings.relevance_ceiling_z


def _categorize(rank: int, prog: KcetProgram):
    if settings.use_observed_range:
        return RANGE_MODEL.categorize(rank, prog.rank_low, prog.rank_high)
    return CUTOFF_MODEL.categorize(rank, prog.closing_rank)


def _score_pair(rank: int, prog: KcetProgram) -> tuple[float, float]:
    """(z-score, probability) for one programme."""
    if settings.use_observed_range:
        z = RANGE_MODEL.z_score(rank, prog.rank_low, prog.rank_high)
        return z, RANGE_MODEL.probability(rank, prog.rank_low, prog.rank_high)
    z = CUTOFF_MODEL.z_score(rank, prog.closing_rank)
    return z, CUTOFF_MODEL.probability_from_z(z)


def _unreachable_ceiling(prog_high: float) -> float:
    """The rank past which nothing in the dataset is reachable any more.

    Used only for the "your rank is past every seat" message, so it takes the
    weakest programme's loose end and adds the same one-band allowance the
    bucketing uses.
    """
    return RANGE_MODEL.dream_ceiling(prog_high, prog_high)


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


def _group_and_order(rows: List[KcetRecommendation]) -> Dict[str, List[KcetRecommendation]]:
    """Bucket the scored rows, each bucket best-first — see ``core.curation``.

    KCET's cutoff attribute is ``closing_rank`` and its programme name is
    ``program``; COMEDK names the same two things ``cutoff_rank`` and
    ``branch``. Naming them at the call site is what lets one implementation
    serve both without either schema knowing about the other.
    """
    return curation.group_and_order(
        rows, rank_attr="closing_rank", name_attr="program"
    )


def _build_recommendation(
    req: KcetRecommendRequest, prog: KcetProgram, bucket: str
) -> KcetRecommendation:
    """Score one eligible programme and turn it into a response card.

    The scoring stage of the pipeline, in one place: interest score, admission
    probability, confidence label and the explanation sentence all derive from
    the same z-score, so a card can never show a percentage that disagrees with
    its own label.
    """
    score, matched = _interest_score(prog, req.goal, req.brand_branch_ratio)
    z, prob = _score_pair(req.rank, prog)
    confidence = _confidence(z)
    return KcetRecommendation(
        institute=prog.institute,
        college_code=prog.college_code,
        program=prog.program,
        seat_category=prog.seat_category,
        seat_category_label=prog.seat_category_label,
        closing_rank=prog.closing_rank,
        rank_low=prog.rank_low,
        rank_high=prog.rank_high,
        band_imputed=prog.band_imputed,
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


def recommend(req: KcetRecommendRequest) -> KcetRecommendResponse:
    programs = load_programs()
    wanted_tags = states.tags_for_branch_preferences(req.branch_preferences)

    notes: List[str] = []
    if req.rank > settings.max_rank:
        notes.append(
            f"A rank of {req.rank:,} is well outside KCET's published range and may be a typo."
        )

    results: List[KcetRecommendation] = []
    # Options the student is certain to get but which sit too far below their
    # rank to be worth listing. Held back rather than discarded so that a very
    # strong rank, whose relevance window is naturally tiny, still gets a
    # usable list — see the top-up below.
    near_certain: List[KcetProgram] = []
    weakest_reachable: Optional[float] = None

    for prog in programs:
        if prog.seat_category != req.seat_category:
            continue
        if wanted_tags and prog.tags.isdisjoint(wanted_tags):
            continue
        if weakest_reachable is None or prog.rank_high > weakest_reachable:
            weakest_reachable = prog.rank_high

        bucket = _categorize(req.rank, prog)
        if bucket is None:
            continue
        if not _is_relevant(req.rank, prog):
            near_certain.append(prog)
            continue

        results.append(_build_recommendation(req, prog, bucket))

    # ── Top up when the relevance window is tighter than a usable list ───
    # A rank-100 student clears everything, so almost nothing survives the
    # window. Add back the most competitive of the near-certain options until
    # there are enough to choose between.
    if len(results) < settings.min_options and near_certain:
        near_certain.sort(key=lambda p: (p.rank_low, p.institute, p.program))
        for prog in near_certain[: settings.min_options - len(results)]:
            # A topped-up option cleared the relevance window by being far
            # *below* the student's rank, so it is Safe unless the model says
            # otherwise; `or "Safe"` covers the None the categorizer returns for
            # an option outside every band.
            bucket = _categorize(req.rank, prog) or "Safe"
            results.append(_build_recommendation(req, prog, bucket))

    # ── Curate: order each bucket best-first, then cap ───────────────────
    eligible = _group_and_order(results)

    count_target, count_reach, count_safe = len(eligible["Target"]), len(eligible["Reach"]), len(eligible["Safe"])
    total_unfiltered = count_target + count_reach + count_safe

    is_top_rank = curation.detect_top_rank(
        total_unfiltered, count_target, count_reach
    )

    # Precedence is KCET's own: an explicit single-bucket request wins over
    # top-rank mode, because a student who opened "Safe" asked for that bucket's
    # full ordered list and the top-rank shortlist would silently truncate it.
    # COMEDK resolves the same collision the other way round — see the note in
    # its recommender. On the 2025 dataset the two branches happen to agree
    # (every top-rank case has exactly 25 eligible Safe options, and
    # top_rank_cap is 25), so this ordering is currently unobservable; it stops
    # being so the moment either constant moves.
    requested_bucket = _SINGLE_BUCKETS.get((req.bucket or "all").lower())
    single_bucket = requested_bucket is not None
    if single_bucket:
        curated = {c: [] for c in CATEGORY_ORDER}
        curated[requested_bucket] = eligible[requested_bucket][: req.max_results]
    elif is_top_rank:
        curated = curation.top_rank_view(eligible, TOP_RANK_CAP, MAX_PER_INSTITUTE)
    else:
        curated = curation.curate_all(eligible, BUCKET_CAPS, MAX_PER_INSTITUTE)

    all_matches = curation.flatten(curated)
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
        and req.rank > _unreachable_ceiling(weakest_reachable)
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
            # Buckets come from each programme's observed round range, so the
            # old synthetic band constants no longer describe the behaviour.
            "use_observed_range": settings.use_observed_range,
            "safe_buffer_fraction": settings.safe_buffer_fraction,
            "relevance_ceiling_z": settings.relevance_ceiling_z,
            "min_options": settings.min_options,
            "caps": dict(BUCKET_CAPS),
            "max_per_institute": MAX_PER_INSTITUTE,
            "top_rank_cap": TOP_RANK_CAP,
        },
    )
