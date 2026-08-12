"""Pydantic request/response models for the KCET engine.

Field names deliberately mirror the JEE engine's (``seat_category`` for the
reservation code, ``branch_preferences``, ``bucket``, and a response shape
with ``counts`` / ``notes`` / ``category_guidance`` / ``thresholds``) so a
client already integrated with JEE's API recognises the shape immediately.
Where the underlying data differs — KCET publishes one closing rank per row,
not an opening/closing round-wise window — the fields differ honestly rather
than faking a JEE-shaped field with no real value behind it (no
``opening_rank``, no ``history``, no ``flag_round``).
"""

from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel, Field, field_validator

from . import states


class KcetRecommendRequest(BaseModel):
    rank: int = Field(ge=1, description="KCET 2025 rank.")
    seat_category: str = Field(
        default="GM",
        description=(
            "Exact KCET category/quota code as published by KEA, e.g. GM, "
            "1G, 2AG, 2AK, 2AR, 3BG, SCG, STK, etc. See /api/kcet/meta for "
            "the full list."
        ),
    )
    goal: str = Field(
        default="undecided",
        description="Career interest, used to re-rank branches. See /api/kcet/meta for options.",
    )
    branch_preferences: List[str] = Field(
        default_factory=list,
        description=(
            "Branch families to filter by (e.g. 'cse', 'ece', 'mechanical'). "
            "Empty means no filter. See /api/kcet/meta for options."
        ),
    )
    brand_branch_ratio: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description=(
            "Priority between branch tag weight (0.0) and college quality/"
            "competitiveness score (1.0), mirroring JEE's slider."
        ),
    )
    bucket: Optional[str] = Field(
        default="all",
        description="Bucket filter: safe, target, dream (or reach), or all.",
    )
    max_results: int = Field(
        default=5000,
        ge=1,
        le=20000,
        description=(
            "Safety upper bound on recommendations returned for a single-"
            "bucket request. The default is large enough that no real query "
            "against this dataset is truncated by it — a single bucket is "
            "otherwise uncapped, matching the JEE engine's per-bucket view."
        ),
    )
    lang: Literal["en"] = Field(
        default="en",
        description="Language for generated text. Only English is available for KCET today.",
    )

    @field_validator("seat_category")
    @classmethod
    def _normalize_category(cls, v: str) -> str:
        return (v or "GM").strip().upper()

    @field_validator("goal")
    @classmethod
    def _normalize_goal(cls, v: str) -> str:
        v = (v or "undecided").strip().lower()
        return v if v in states.VALID_GOALS else "undecided"


class KcetRecommendation(BaseModel):
    institute: str
    college_code: str
    program: str  # raw course name as published — see states.py module docstring
    seat_category: str  # exact published code, e.g. "2AG"
    seat_category_label: str  # human-readable, e.g. "Category 2A (State-wide)"
    closing_rank: int
    category: str  # Safe / Target / Reach (display bucket)
    fit_label: str
    interest_score: float
    matched_interest: bool
    confidence: str  # high / medium, derived from the same z-score as probability
    reason: str
    quality_score: float  # 0-10, this row's cutoff percentile within its category
    admission_probability: Optional[float] = None
    tags: List[str] = Field(default_factory=list)


class CategoryGuidance(BaseModel):
    category: str
    count: int
    blurb: str


class KcetRecommendResponse(BaseModel):
    guidance: str
    interest_guidance: str
    counts: dict
    notes: List[str] = Field(default_factory=list)
    category_guidance: List[CategoryGuidance] = Field(default_factory=list)
    recommendations: List[KcetRecommendation] = Field(default_factory=list)
    total_count: int = 0
    thresholds: dict = Field(default_factory=dict)


class KcetMetaResponse(BaseModel):
    seat_categories: List[dict]  # [{value, label}]
    goals: List[dict]  # [{value, label}]
    branch_preferences: List[dict]  # [{value, label}]
    total_programs: int
    total_institutes: int
