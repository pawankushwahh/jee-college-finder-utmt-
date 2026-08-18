"""Statistical insights for the COMEDK dataset, served at /api/comedk/stats.

What makes this COMEDK-specific rather than a port of the KCET or JEE page:

* **Fees are published.** COMEDK is the only one of the three datasets carrying
  tuition and other fees per programme, so cost-versus-competitiveness is an
  insight only this exam can offer. It is also the question a private-college
  applicant actually asks.
* **A seat matrix.** ``total_seats`` and ``category_seats`` come from the
  pre-counselling matrix, so supply can be reported next to demand.
* **Two quotas that are not symmetric.** GM ran in rounds 1/3/4 and KKR in
  rounds 1/2, so the GM-vs-KKR gap is computed per (institute, branch) pair
  present in both, never as a difference of pooled medians.
* **A mock round.** COMEDK publishes a simulation before counselling opens. It
  allotted no seat, so it is never a cut-off — but comparing it against round 1
  says something real about how well the mock predicted the actual.

Backwards compatibility: every key the previous version returned is still
returned with the same shape. New sections are additive.
"""

from __future__ import annotations

import math
from collections import defaultdict
from statistics import median
from typing import Any, Dict, List, Optional

from .data_loader import get_programs

# Cut-offs are compared within General Merit. GM and KKR are different seat
# pools, so a pooled median would order colleges by quota mix rather than
# competitiveness.
REFERENCE_QUOTA = "GM"

# COMEDK's largest closing rank is 111,800, so the buckets stop well short of
# KCET's scale — reusing KCET's would leave the top three empty.
_RANK_BUCKETS: List[tuple[int, Optional[int], str]] = [
    (0, 1_000, "Under 1K"),
    (1_000, 5_000, "1K–5K"),
    (5_000, 10_000, "5K–10K"),
    (10_000, 20_000, "10K–20K"),
    (20_000, 40_000, "20K–40K"),
    (40_000, 70_000, "40K–70K"),
    (70_000, None, "Over 70K"),
]

# Annual total fee, in rupees.
_FEE_BUCKETS: List[tuple[int, Optional[int], str]] = [
    (0, 100_000, "Under ₹1L"),
    (100_000, 175_000, "₹1L–1.75L"),
    (175_000, 225_000, "₹1.75L–2.25L"),
    (225_000, 275_000, "₹2.25L–2.75L"),
    (275_000, None, "Over ₹2.75L"),
]

_TIER_ORDER = ["elite", "top", "strong", "mid", "emerging"]

_EMPTY: Dict[str, Any] = {
    "summary": {
        "total_records": 0,
        "unique_institutes": 0,
        "unique_programs": 0,
        "unique_quotas": 0,
        "unique_seat_types": 0,
        "total_seats": 0,
        "rounds_published": 0,
        "median_fee": 0,
        "rank_min": 0,
        "rank_max": 0,
    },
    "quota_counts": {},
    "highest_cutoffs": [],
    "lowest_cutoffs": [],
    "inst_competitiveness": {},
    "branch_popularity": [],
    "branch_counts": {},
    "round_averages": {},
    "round_averages_main": {},
    "round_averages_adv": {},
    "rank_distribution": [],
    "fee_distribution": [],
    "fee_vs_competitiveness": [],
    "value_picks": [],
    "seat_matrix": {},
    "branch_families": [],
    "quota_gap": {},
    "round_participation": [],
    "mock_accuracy": {},
    "brand_tiers": [],
    "metro_split": {},
}


def _percentile(values: List[float], fraction: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, math.ceil(fraction * len(ordered)) - 1))
    return float(ordered[index])


def _bucket(values: List[float], buckets) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for low, high, label in buckets:
        count = sum(1 for v in values if v >= low and (high is None or v < high))
        out.append({"label": label, "count": count})
    return out


def compute_comedk_stats() -> Dict[str, Any]:
    programs = get_programs()
    if not programs:
        return _EMPTY

    institutes = {p["institute"] for p in programs}
    courses = {p["program"] for p in programs}
    quotas = sorted({p["quota"] for p in programs})

    quota_counts: Dict[str, int] = defaultdict(int)
    for p in programs:
        quota_counts[p["quota"]] += 1

    reference = [p for p in programs if p["quota"] == REFERENCE_QUOTA] or programs
    ref_ranks = [p["cutoff_rank"] for p in reference]
    all_ranks = [p["cutoff_rank"] for p in programs]

    # ── Extremes ──────────────────────────────────────────────────────────
    by_rank = sorted(
        reference, key=lambda p: (p["cutoff_rank"], p["institute"], p["program"])
    )

    def _row(p: dict) -> Dict[str, Any]:
        return {
            "institute": p["institute"],
            "program": p["program"],
            "quota": p["quota"],
            "closing_rank": int(p["cutoff_rank"]),
            "inst_type": "COMEDK",
        }

    highest_cutoffs = [_row(p) for p in by_rank[:10]]
    lowest_cutoffs = [_row(p) for p in reversed(by_rank[-10:])]

    # ── Institute competitiveness ─────────────────────────────────────────
    inst_groups: Dict[str, List[float]] = defaultdict(list)
    for p in reference:
        inst_groups[p["institute"]].append(p["cutoff_rank"])
    inst_rows = sorted(
        (
            {
                "institute": inst,
                "avg_closing_rank": round(sum(r) / len(r), 1),
                "min_opening_rank": int(min(r)),
                "total_programs": len(r),
            }
            for inst, r in inst_groups.items()
        ),
        key=lambda r: r["avg_closing_rank"],
    )
    inst_competitiveness = {"COMEDK": inst_rows[:15]}

    # ── Branch popularity ─────────────────────────────────────────────────
    branch_groups: Dict[str, List[float]] = defaultdict(list)
    for p in reference:
        branch_groups[p["program"]].append(p["cutoff_rank"])
    eligible = {b: r for b, r in branch_groups.items() if len(r) >= 3} or branch_groups
    branch_popularity = sorted(
        (
            {
                "branch": b,
                "avg_closing_rank": round(sum(r) / len(r), 1),
                "total_programs": len(r),
            }
            for b, r in eligible.items()
        ),
        key=lambda r: r["avg_closing_rank"],
    )[:15]

    # ── Fees — the insight only COMEDK's data supports ────────────────────
    fees = [p["total_fee"] for p in programs if p.get("total_fee")]
    fee_distribution = _bucket([float(f) for f in fees], _FEE_BUCKETS)

    # Fee against competitiveness, per institute. Both sides are medians over
    # the institute's GM programmes so one outlier course cannot move it.
    inst_fee: Dict[str, List[int]] = defaultdict(list)
    for p in reference:
        if p.get("total_fee"):
            inst_fee[p["institute"]].append(p["total_fee"])
    fee_vs_competitiveness = []
    for inst, inst_fees in inst_fee.items():
        ranks = inst_groups.get(inst)
        if not ranks or len(inst_fees) < 2:
            continue
        fee_vs_competitiveness.append(
            {
                "institute": inst,
                "median_fee": int(median(inst_fees)),
                "median_cutoff": int(median(ranks)),
                "programs": len(ranks),
            }
        )
    fee_vs_competitiveness.sort(key=lambda r: r["median_cutoff"])

    # "Value picks": competitive on cut-off (top tercile) yet cheaper than the
    # median fee. Stated as a filter over observed data, not a score.
    if fee_vs_competitiveness:
        cutoff_cap = _percentile([r["median_cutoff"] for r in fee_vs_competitiveness], 0.33)
        fee_cap = median([r["median_fee"] for r in fee_vs_competitiveness])
        value_picks = sorted(
            (
                r
                for r in fee_vs_competitiveness
                if r["median_cutoff"] <= cutoff_cap and r["median_fee"] <= fee_cap
            ),
            key=lambda r: r["median_cutoff"],
        )[:12]
    else:
        value_picks = []

    # ── Seat matrix ───────────────────────────────────────────────────────
    seat_by_quota: Dict[str, int] = defaultdict(int)
    for p in programs:
        seat_by_quota[p["quota"]] += int(p.get("category_seats") or 0)
    # total_seats is a property of the (institute, branch) pair, so summing it
    # across quota rows would double-count the same physical seats.
    seats_by_pair = {
        (p["institute"], p["branch"]): int(p.get("total_seats") or 0) for p in programs
    }
    seat_matrix = {
        "total_seats": sum(seats_by_pair.values()),
        "category_seats_by_quota": dict(seat_by_quota),
        "programs_with_seats": sum(1 for v in seats_by_pair.values() if v > 0),
        "largest_intake": max(seats_by_pair.values()) if seats_by_pair else 0,
    }

    # ── Branch families: supply and demand together ───────────────────────
    fam_ranks: Dict[str, List[float]] = defaultdict(list)
    fam_seats: Dict[str, int] = defaultdict(int)
    fam_fees: Dict[str, List[int]] = defaultdict(list)
    for p in reference:
        fam = p.get("branch_family") or "other"
        fam_ranks[fam].append(p["cutoff_rank"])
        if p.get("total_fee"):
            fam_fees[fam].append(p["total_fee"])
    family_of_pair = {
        (p["institute"], p["branch"]): p.get("branch_family") or "other" for p in programs
    }
    for pair, seats in seats_by_pair.items():
        fam_seats[family_of_pair.get(pair, "other")] += seats
    branch_families = sorted(
        (
            {
                "family": fam,
                "programs": len(ranks),
                "median_cutoff": int(median(ranks)),
                "seats": fam_seats.get(fam, 0),
                "median_fee": int(median(fam_fees[fam])) if fam_fees.get(fam) else 0,
            }
            for fam, ranks in fam_ranks.items()
            if len(ranks) >= 3
        ),
        key=lambda r: r["median_cutoff"],
    )

    # ── GM vs KKR, paired ─────────────────────────────────────────────────
    gm = {(p["institute"], p["branch"]): p["cutoff_rank"]
          for p in programs if p["quota"] == "GM"}
    kkr = {(p["institute"], p["branch"]): p["cutoff_rank"]
           for p in programs if p["quota"] == "KKR"}
    paired = sorted(gm.keys() & kkr.keys())
    gaps = [kkr[k] - gm[k] for k in paired]
    quota_gap = {
        "paired_programs": len(paired),
        "median_gap": int(median(gaps)) if gaps else 0,
        "kkr_easier_pct": round(100.0 * sum(1 for g in gaps if g > 0) / len(gaps), 1)
        if gaps
        else 0.0,
        "gm_median": int(median([gm[k] for k in paired])) if paired else 0,
        "kkr_median": int(median([kkr[k] for k in paired])) if paired else 0,
        "note": "Paired per (college, branch); GM ran rounds 1/3/4 and KKR rounds 1/2.",
    }

    # ── Round participation ───────────────────────────────────────────────
    round_ranks: Dict[int, List[float]] = defaultdict(list)
    for p in programs:
        for round_no, rank in p.get("cutoff_by_round") or ():
            round_ranks[round_no].append(rank)
    round_participation = [
        {
            "round": r,
            "programs": len(v),
            "coverage_pct": round(100.0 * len(v) / len(programs), 1),
            "median_cutoff": int(median(v)),
        }
        for r, v in sorted(round_ranks.items())
    ]

    # ── Mock round vs the actual round 1 ──────────────────────────────────
    deltas = []
    for p in programs:
        mock = p.get("mock_rank")
        actual = next((rank for rnd, rank in (p.get("cutoff_by_round") or ()) if rnd == 1), None)
        if mock and actual:
            deltas.append(actual - mock)
    mock_accuracy = {
        "comparable_programs": len(deltas),
        "median_delta": int(median(deltas)) if deltas else 0,
        "actual_looser_pct": round(100.0 * sum(1 for d in deltas if d > 0) / len(deltas), 1)
        if deltas
        else 0.0,
        "note": "Mock allotted no seat; shown only as a predictor of round 1.",
    }

    # ── Brand tiers and metro split ───────────────────────────────────────
    tier_ranks: Dict[str, List[float]] = defaultdict(list)
    for p in reference:
        tier_ranks[p.get("brand_tier") or "unknown"].append(p["cutoff_rank"])
    brand_tiers = [
        {
            "tier": t,
            "programs": len(tier_ranks[t]),
            "median_cutoff": int(median(tier_ranks[t])),
        }
        for t in _TIER_ORDER
        if tier_ranks.get(t)
    ]

    metro_ranks = [p["cutoff_rank"] for p in reference if p.get("is_metro")]
    non_metro_ranks = [p["cutoff_rank"] for p in reference if not p.get("is_metro")]
    metro_split = {
        "metro": {
            "programs": len(metro_ranks),
            "median_cutoff": int(median(metro_ranks)) if metro_ranks else 0,
        },
        "non_metro": {
            "programs": len(non_metro_ranks),
            "median_cutoff": int(median(non_metro_ranks)) if non_metro_ranks else 0,
        },
    }

    return {
        "summary": {
            "total_records": len(programs),
            "unique_institutes": len(institutes),
            "unique_programs": len(courses),
            "unique_quotas": len(quotas),
            "unique_seat_types": len(quotas),
            "total_seats": seat_matrix["total_seats"],
            "rounds_published": len(round_ranks),
            "median_fee": int(median(fees)) if fees else 0,
            "rank_min": int(min(all_ranks)),
            "rank_max": int(max(all_ranks)),
        },
        "quota_counts": dict(quota_counts),
        "highest_cutoffs": highest_cutoffs,
        "lowest_cutoffs": lowest_cutoffs,
        "inst_competitiveness": inst_competitiveness,
        "branch_popularity": branch_popularity,
        "branch_counts": {},
        "round_averages": {},
        "round_averages_main": {},
        "round_averages_adv": {},
        # ── COMEDK-specific additions ─────────────────────────────────────
        "reference_quota": REFERENCE_QUOTA,
        "rank_distribution": _bucket(ref_ranks, _RANK_BUCKETS),
        "fee_distribution": fee_distribution,
        "fee_vs_competitiveness": fee_vs_competitiveness,
        "value_picks": value_picks,
        "seat_matrix": seat_matrix,
        "branch_families": branch_families,
        "quota_gap": quota_gap,
        "round_participation": round_participation,
        "mock_accuracy": mock_accuracy,
        "brand_tiers": brand_tiers,
        "metro_split": metro_split,
    }
