"""Statistical insights for the KCET dataset, served at /api/kcet/stats.

What makes this KCET-specific rather than a port of the JEE stats page:

* **Two seat pools.** KEA publishes 48 category codes that split into a
  Rest-of-Karnataka pool and a 371(j) / Kalyana-Karnataka pool (``GM`` vs
  ``GMH``). The same base category closes at very different ranks in each, and
  that gap is the single most actionable thing a Karnataka student can be told.
* **Three counselling rounds, kept.** ``KcetProgram.closing_rank_by_round``
  carries every published round, so round-over-round loosening is an observed
  fact here rather than a model.
* **An observed admitted band.** ``rank_low``/``rank_high`` come off the rounds
  directly, so band width is real data — but 32% of programmes published only
  one round and have an *imputed* high end. That is reported rather than hidden,
  because a band the engine invented should not read as one KEA measured.

Backwards compatibility: every key the previous version returned is still
returned with the same shape, so an older cached copy of stats.html keeps
working. New sections are additive.
"""

from __future__ import annotations

import math
from collections import defaultdict
from statistics import median
from typing import Any, Dict, List, Optional

from .data_loader import load_programs
from .states import describe_category, parse_category, split_seat_pool

# The pool every cross-category comparison is taken within. Mixing pools would
# compare a 371(j) cut-off against a state-wide one and report the pool
# boundary as if it were a difference between categories.
REFERENCE_CATEGORY = "GM"

# Buckets for the rank histogram. KCET runs to 262,188, so the top bucket is
# open-ended rather than pretending the axis stops at a round number.
_RANK_BUCKETS: List[tuple[int, Optional[int], str]] = [
    (0, 1_000, "Under 1K"),
    (1_000, 5_000, "1K–5K"),
    (5_000, 10_000, "5K–10K"),
    (10_000, 25_000, "10K–25K"),
    (25_000, 50_000, "25K–50K"),
    (50_000, 100_000, "50K–1L"),
    (100_000, 150_000, "1L–1.5L"),
    (150_000, None, "Over 1.5L"),
]

_EMPTY: Dict[str, Any] = {
    "summary": {
        "total_records": 0,
        "unique_institutes": 0,
        "unique_programs": 0,
        "unique_quotas": 0,
        "unique_seat_types": 0,
        "rounds_published": 0,
        "general_categories": 0,
        "hk_categories": 0,
        "rank_min": 0,
        "rank_max": 0,
        "imputed_pct": 0.0,
    },
    "quota_counts": {},
    "highest_cutoffs": [],
    "lowest_cutoffs": [],
    "inst_competitiveness": {},
    "branch_popularity": [],
    "branch_counts": {},
    "round_averages": {},
    "rank_distribution": [],
    "round_participation": [],
    "seat_pool": {},
    "category_comparison": [],
    "hk_advantage": [],
    "band_width": {},
    "data_quality": {},
}


def _percentile(values: List[float], fraction: float) -> float:
    """Nearest-rank percentile. Plain sort rather than numpy — these lists are
    at most a few thousand long and the dependency is not worth it."""
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, math.ceil(fraction * len(ordered)) - 1))
    return float(ordered[index])


def _bucket_ranks(ranks: List[float]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for low, high, label in _RANK_BUCKETS:
        count = sum(1 for r in ranks if r >= low and (high is None or r < high))
        out.append({"label": label, "count": count})
    return out


def compute_kcet_stats() -> Dict[str, Any]:
    programs = load_programs()
    if not programs:
        return _EMPTY

    institutes = {p.institute for p in programs}
    courses = {p.program for p in programs}
    categories = sorted({p.seat_category for p in programs})

    # Parse each of the 48 codes once rather than per row: the same handful of
    # codes repeats across 24,495 programmes, and re-parsing per row made this
    # endpoint roughly twenty times slower for no additional information.
    parsed = {
        code: (split_seat_pool(code)[1], parse_category(code)) for code in categories
    }

    general_cats = [c for c in categories if not parsed[c][0]]
    hk_cats = [c for c in categories if parsed[c][0]]

    quota_counts: Dict[str, int] = defaultdict(int)
    for p in programs:
        quota_counts[p.seat_category] += 1

    reference = [p for p in programs if p.seat_category == REFERENCE_CATEGORY]
    if not reference:
        reference = [p for p in programs if p.seat_category == categories[0]]

    all_ranks = [p.closing_rank for p in programs]
    ref_ranks = [p.closing_rank for p in reference]

    # ── Extremes, within the reference category ───────────────────────────
    by_rank = sorted(reference, key=lambda p: (p.closing_rank, p.institute, p.program))
    highest_cutoffs = [
        {
            "institute": p.institute,
            "program": p.program,
            "quota": p.seat_category,
            "closing_rank": int(p.closing_rank),
            "inst_type": "KCET",
        }
        for p in by_rank[:10]
    ]
    lowest_cutoffs = [
        {
            "institute": p.institute,
            "program": p.program,
            "quota": p.seat_category,
            "closing_rank": int(p.closing_rank),
            "inst_type": "KCET",
        }
        for p in reversed(by_rank[-10:])
    ]

    # ── Institute competitiveness ─────────────────────────────────────────
    inst_groups: Dict[str, List[float]] = defaultdict(list)
    for p in reference:
        inst_groups[p.institute].append(p.closing_rank)
    inst_rows = sorted(
        (
            {
                "institute": inst,
                "avg_closing_rank": round(sum(ranks) / len(ranks), 1),
                "min_opening_rank": int(min(ranks)),
                "total_programs": len(ranks),
            }
            for inst, ranks in inst_groups.items()
        ),
        key=lambda r: r["avg_closing_rank"],
    )
    inst_competitiveness = {"KCET": inst_rows[:15]}

    # ── Branch popularity ─────────────────────────────────────────────────
    branch_groups: Dict[str, List[float]] = defaultdict(list)
    for p in reference:
        branch_groups[p.program].append(p.closing_rank)
    eligible = {b: r for b, r in branch_groups.items() if len(r) >= 3} or branch_groups
    branch_popularity = sorted(
        (
            {
                "branch": branch,
                "avg_closing_rank": round(sum(ranks) / len(ranks), 1),
                "total_programs": len(ranks),
            }
            for branch, ranks in eligible.items()
        ),
        key=lambda r: r["avg_closing_rank"],
    )[:15]

    # ── Round participation and movement ──────────────────────────────────
    # A programme appears in a round only if KEA allotted a seat in it, so the
    # per-round counts are coverage, not just volume.
    round_ranks: Dict[int, List[float]] = defaultdict(list)
    for p in programs:
        for round_no, rank in p.closing_rank_by_round:
            round_ranks[round_no].append(rank)
    round_participation = [
        {
            "round": round_no,
            "programs": len(ranks),
            "coverage_pct": round(100.0 * len(ranks) / len(programs), 1),
            "median_cutoff": int(median(ranks)),
        }
        for round_no, ranks in sorted(round_ranks.items())
    ]

    # ── Seat pool: Rest-of-Karnataka vs 371(j) ────────────────────────────
    gen_ranks = [p.closing_rank for p in programs if not parsed[p.seat_category][0]]
    hk_ranks = [p.closing_rank for p in programs if parsed[p.seat_category][0]]
    seat_pool = {
        "general": {
            "label": "Rest of Karnataka",
            "categories": len(general_cats),
            "programs": len(gen_ranks),
            "median_cutoff": int(median(gen_ranks)) if gen_ranks else 0,
        },
        "hk": {
            "label": "371(j) Kalyana-Karnataka",
            "categories": len(hk_cats),
            "programs": len(hk_ranks),
            "median_cutoff": int(median(hk_ranks)) if hk_ranks else 0,
        },
    }

    # ── Base-category comparison, within the state-wide (G) sub-quota ─────
    # Restricted to the "G" sub-quota so that Kannada-medium and Rural codes,
    # which answer a different question, do not distort the category picture.
    base_groups: Dict[str, List[float]] = defaultdict(list)
    for p in programs:
        is_hk, (base, sub) = parsed[p.seat_category]
        if sub == "G" and not is_hk:
            base_groups[base].append(p.closing_rank)
    category_comparison = sorted(
        (
            {
                "category": base,
                "label": describe_category(f"{base}G"),
                "programs": len(ranks),
                "median_cutoff": int(median(ranks)),
                "p10": int(_percentile(ranks, 0.10)),
                "p90": int(_percentile(ranks, 0.90)),
            }
            for base, ranks in base_groups.items()
            if len(ranks) >= 20
        ),
        key=lambda r: r["median_cutoff"],
    )

    # ── 371(j) advantage, per base category ───────────────────────────────
    # Same base category, the two pools side by side. A positive delta means
    # the 371(j) pool closed at a looser rank — an easier entry.
    gen_by_base: Dict[str, List[float]] = defaultdict(list)
    hk_by_base: Dict[str, List[float]] = defaultdict(list)
    for p in programs:
        is_hk, (base, sub) = parsed[p.seat_category]
        if sub != "G":
            continue
        (hk_by_base if is_hk else gen_by_base)[base].append(p.closing_rank)
    hk_advantage = []
    for base in sorted(gen_by_base.keys() & hk_by_base.keys()):
        gen, hk = gen_by_base[base], hk_by_base[base]
        if len(gen) < 20 or len(hk) < 20:
            continue
        gen_med, hk_med = median(gen), median(hk)
        hk_advantage.append(
            {
                "category": base,
                "general_median": int(gen_med),
                "hk_median": int(hk_med),
                "delta": int(hk_med - gen_med),
            }
        )
    hk_advantage.sort(key=lambda r: r["delta"], reverse=True)

    # ── Observed admitted band ────────────────────────────────────────────
    # Only programmes with a genuinely observed high end; the imputed 32% would
    # otherwise report a modelled width as a measured one.
    observed = [p for p in programs if not p.band_imputed and p.band_width > 0]
    widths = [p.band_width for p in observed]
    band_width = {
        "observed_programs": len(observed),
        "median_width": int(median(widths)) if widths else 0,
        "p90_width": int(_percentile(widths, 0.90)) if widths else 0,
        "note": "Measured only on programmes that published more than one round.",
    }

    imputed = sum(1 for p in programs if p.band_imputed)
    data_quality = {
        "imputed_programs": imputed,
        "imputed_pct": round(100.0 * imputed / len(programs), 1),
        "fractional_cutoffs": sum(1 for r in all_ranks if r != int(r)),
        "single_round_programs": sum(1 for p in programs if len(p.rounds) == 1),
        "rounds_published": sorted(round_ranks.keys()),
    }

    return {
        "summary": {
            "total_records": len(programs),
            "unique_institutes": len(institutes),
            "unique_programs": len(courses),
            "unique_quotas": len(categories),
            "unique_seat_types": len(categories),
            "rounds_published": len(round_ranks),
            "general_categories": len(general_cats),
            "hk_categories": len(hk_cats),
            "rank_min": int(min(all_ranks)),
            "rank_max": int(max(all_ranks)),
            "imputed_pct": data_quality["imputed_pct"],
        },
        "quota_counts": dict(quota_counts),
        "highest_cutoffs": highest_cutoffs,
        "lowest_cutoffs": lowest_cutoffs,
        "inst_competitiveness": inst_competitiveness,
        "branch_popularity": branch_popularity,
        "branch_counts": {},
        "round_averages": {},
        # ── KCET-specific additions ───────────────────────────────────────
        "reference_category": REFERENCE_CATEGORY,
        "rank_distribution": _bucket_ranks(ref_ranks),
        "round_participation": round_participation,
        "seat_pool": seat_pool,
        "category_comparison": category_comparison,
        "hk_advantage": hk_advantage,
        "band_width": band_width,
        "data_quality": data_quality,
    }
