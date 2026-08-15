"""Request matrix for the golden baseline.

Every case here is replayed before and after each refactor step and the
response must come back byte-identical.  The matrix is deliberately built
from *targeted* axes rather than a full cross-product: a full cross of the
JEE axes alone is ~32,000 cases, which is slow to run and no more revealing
than a core grid plus one-axis-at-a-time variation.

Two shapes are used:

``core grid``
    A full cross-product of the axes that genuinely *interact* — rank,
    seat category and (for JEE) which ranks the student supplied.  These
    are the inputs that decide which rows are eligible at all, so their
    combinations are where behaviour actually changes.

``variations``
    Everything else is varied one axis at a time against a fixed base
    case.  Language, bucket filter and pagination do not interact with
    rank selection; crossing them would multiply the case count without
    covering new branches.

Edge cases are pinned explicitly rather than sampled, and each carries a
comment saying which code path it exists to hold still.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class Case:
    """One replayable request."""

    exam: str
    method: str
    path: str
    payload: Optional[Dict[str, Any]] = None
    params: Optional[Dict[str, Any]] = None
    note: str = ""

    @property
    def key(self) -> str:
        """Stable filename for this case.

        Derived from the request itself, so reordering the matrix never
        renames a baseline file and a changed payload never silently
        overwrites an unrelated one.
        """
        blob = json.dumps(
            {
                "method": self.method,
                "path": self.path,
                "payload": self.payload,
                "params": self.params,
            },
            sort_keys=True,
            ensure_ascii=False,
        )
        return hashlib.sha1(blob.encode("utf-8")).hexdigest()[:16]


# ---------------------------------------------------------------------------
# JEE
# ---------------------------------------------------------------------------

# Spans the full observed rank range.  Closing ranks in josaa_merged_2025.csv
# run to 937,704, so 900,000 sits just inside the data and 2,000,000 lands
# past every cutoff — the empty-result path.
_JEE_RANKS = [1, 1_000, 6_000, 50_000, 250_000, 900_000, 2_000_000]

# All ten canonical categories exist, but these seven cover both PwD variants
# and the extremes of the scale problem: OPEN closes at 937,704 while
# ST (PwD) is exhausted by 116.
_JEE_CATEGORIES = [
    "OPEN",
    "OBC-NCL",
    "SC",
    "ST",
    "EWS",
    "OPEN (PwD)",
    "ST (PwD)",
]

# The axis that pins _relevant_rank(): IIT rows read adv_rank, everything
# else reads mains_rank.  Supplying only one of the two must silently drop
# the other half of the dataset.
_JEE_RANK_PRESENCE = ["adv_only", "mains_only", "both"]

_JEE_BASE: Dict[str, Any] = {
    "adv_rank": 1_500,
    "mains_rank": 6_000,
    "gender": "female",
    "home_state": "Rajasthan",
    "goal": "coding",
    "seat_category": "OPEN",
}


def _jee_ranks_for(presence: str, rank: int) -> Dict[str, Any]:
    if presence == "adv_only":
        return {"adv_rank": rank, "mains_rank": None}
    if presence == "mains_only":
        return {"adv_rank": None, "mains_rank": rank}
    return {"adv_rank": rank, "mains_rank": rank}


def _jee_cases() -> List[Case]:
    cases: List[Case] = []

    # Core grid: rank x category x rank-presence.
    for rank in _JEE_RANKS:
        for category in _JEE_CATEGORIES:
            for presence in _JEE_RANK_PRESENCE:
                payload = {
                    **_JEE_BASE,
                    **_jee_ranks_for(presence, rank),
                    "seat_category": category,
                }
                cases.append(
                    Case(
                        "jee",
                        "POST",
                        "/api/recommend",
                        payload,
                        note=f"core grid rank={rank} cat={category} ranks={presence}",
                    )
                )

    # One-axis variations against the base case.
    variations: List[tuple[str, Any]] = []
    variations += [("gender", g) for g in ("male", "female")]
    # "Atlantis" is not a real state: pins the get_institute_state() ->
    # "Unknown" fallback and the HS/OS quota behaviour for an unmatched state.
    variations += [
        ("home_state", s) for s in ("Delhi", "Karnataka", "Goa", "Atlantis")
    ]
    variations += [
        ("goal", g)
        for g in ("coding", "research", "mba", "core", "undecided", "pure_science")
    ]
    variations += [("lang", lg) for lg in ("en", "hi", "gu", "kn")]
    variations += [("bucket", b) for b in ("all", "safe", "target", "dream")]
    variations += [("college_type", t) for t in ("all", "IIT", "NIT", "IIIT", "GFTI")]
    variations += [("brand_branch_ratio", r) for r in (0.0, 0.5, 1.0)]
    variations += [("is_pwd", v) for v in (True, False)]
    variations += [("max_results", n) for n in (10, 5000)]
    # Declared but never applied by recommend() today; pinned so that stays true.
    variations += [("page", n) for n in (1, 2)]
    variations += [("page_size", n) for n in (10, 50)]
    # Unknown branch values must be ignored rather than filter everything out.
    variations += [
        ("branch_preferences", b)
        for b in ([], ["cs_it"], ["cs_it", "ece"], ["nonsense"], ["any"])
    ]

    for field_name, value in variations:
        cases.append(
            Case(
                "jee",
                "POST",
                "/api/recommend",
                {**_JEE_BASE, field_name: value},
                note=f"variation {field_name}={value!r}",
            )
        )

    # GET /api/recommend has a hand-rolled query-param adapter that POST does
    # not share, so it needs its own coverage.
    cases.append(
        Case(
            "jee",
            "GET",
            "/api/recommend",
            params={
                "adv_rank": 1500,
                "mains_rank": 6000,
                "gender": "female",
                "home_state": "Rajasthan",
                "goal": "coding",
            },
            note="GET query-param adapter",
        )
    )

    cases.append(Case("jee", "GET", "/api/meta", note="meta"))
    cases.append(Case("jee", "GET", "/api/stats", note="stats"))
    cases.append(Case("jee", "GET", "/api/health", note="health"))
    return cases


# ---------------------------------------------------------------------------
# KCET
# ---------------------------------------------------------------------------

# GM opens at 234 and the dataset's maximum closing rank is 249,733.
# 400,001 is one past settings.max_rank, pinning the implausible-rank note.
_KCET_RANKS = [1, 234, 5_000, 67_328, 200_000, 249_733, 400_001]

# Covers a state-wide code, a Kalyana-Karnataka code, a rural code, and an
# unknown code that must not crash parse_category().
_KCET_CATEGORIES = ["GM", "1G", "2AG", "3BG", "SCK", "STR", "ZZZ"]

_KCET_BASE: Dict[str, Any] = {"rank": 45_000, "seat_category": "GM"}


def _kcet_cases() -> List[Case]:
    cases: List[Case] = []

    for rank in _KCET_RANKS:
        for category in _KCET_CATEGORIES:
            cases.append(
                Case(
                    "kcet",
                    "POST",
                    "/api/kcet/recommend",
                    {"rank": rank, "seat_category": category},
                    note=f"core grid rank={rank} cat={category}",
                )
            )

    variations: List[tuple[str, Any]] = []
    variations += [("brand_branch_ratio", r) for r in (0.0, 0.5, 1.0)]
    variations += [("bucket", b) for b in ("all", "safe", "target", "dream")]
    variations += [("max_results", n) for n in (10, 5000)]
    variations += [
        ("goal", g) for g in ("coding", "research", "mba", "core", "undecided")
    ]
    variations += [
        ("branch_preferences", b)
        for b in ([], ["cse"], ["cse", "ece"], ["nonsense"])
    ]

    for field_name, value in variations:
        cases.append(
            Case(
                "kcet",
                "POST",
                "/api/kcet/recommend",
                {**_KCET_BASE, field_name: value},
                note=f"variation {field_name}={value!r}",
            )
        )

    cases.append(Case("kcet", "GET", "/api/kcet/meta", note="meta"))
    cases.append(Case("kcet", "GET", "/api/kcet/stats", note="stats"))
    cases.append(Case("kcet", "GET", "/api/kcet/health", note="health"))
    return cases


# ---------------------------------------------------------------------------
# COMEDK
# ---------------------------------------------------------------------------

# 100 vs 101 straddles settings.top_rank_threshold, the one place COMEDK
# still uses a hardcoded rank gate where JEE and KCET derive it from bucket
# counts.  200,001 is one past max_rank and pins the rank_implausible
# early-return envelope.
_COMEDK_RANKS = [1, 100, 101, 692, 20_000, 76_983, 111_800, 200_001]

_COMEDK_BASE: Dict[str, Any] = {"rank": 20_000, "quota": "GM"}


def _comedk_cases() -> List[Case]:
    cases: List[Case] = []

    for rank in _COMEDK_RANKS:
        for quota in ("GM", "KKR"):
            cases.append(
                Case(
                    "comedk",
                    "POST",
                    "/api/comedk/recommend",
                    {"rank": rank, "quota": quota},
                    note=f"core grid rank={rank} quota={quota}",
                )
            )

    variations: List[tuple[str, Any]] = []
    variations += [("lang", lg) for lg in ("en", "hi", "gu", "kn")]
    variations += [("bucket", b) for b in ("all", "safe", "target", "dream")]
    # COMEDK is the one exam that actually applies pagination.
    variations += [("page", n) for n in (1, 2, 3)]
    variations += [("page_size", n) for n in (10, 150)]
    variations += [
        ("branch_families", b)
        for b in ([], ["cse"], ["cse", "ece"], ["nonsense"])
    ]

    for field_name, value in variations:
        cases.append(
            Case(
                "comedk",
                "POST",
                "/api/comedk/recommend",
                {**_COMEDK_BASE, field_name: value},
                note=f"variation {field_name}={value!r}",
            )
        )

    cases.append(Case("comedk", "GET", "/api/comedk/meta", note="meta"))
    cases.append(Case("comedk", "GET", "/api/comedk/stats", note="stats"))
    return cases


def all_cases() -> List[Case]:
    """Every golden case, across all exams."""
    return _jee_cases() + _kcet_cases() + _comedk_cases()


# Data files whose contents the baseline depends on.  A change here must fail
# loudly rather than silently rebase every expectation.
DATA_FILES = [
    "app/disha/data/josaa_merged_2025.csv",
    "app/disha/kcet/data/kcet_2025.csv",
    "app/disha/comedk/data/comedk_2025.csv",
]
