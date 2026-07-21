"""Pydantic request/response models for the /recommend endpoint."""

from __future__ import annotations

from typing import List, Literal, Optional

import pydantic
from pydantic import BaseModel, Field

IS_PYDANTIC_V2 = pydantic.__version__.startswith("2")

if IS_PYDANTIC_V2:
    from pydantic import model_validator
else:
    from pydantic import root_validator

from .config import settings

from . import states


class RecommendRequest(BaseModel):
    adv_rank: Optional[int] = Field(
        default=None,
        ge=1,
        description="JEE Advanced Common Rank List (CRL) rank. Required to see IITs.",
    )
    mains_rank: Optional[int] = Field(
        default=None,
        ge=1,
        description="JEE Mains CRL rank. Required to see NITs / IIITs / GFTIs.",
    )
    gender: Literal["male", "female"] = Field(
        description="Used to include Female-only (supernumerary) seats for female applicants.",
    )
    home_state: str = Field(
        description="Home state / UT, used for Home-State (HS) vs Other-State (OS) quota at NITs/IIITs.",
    )
    goal: Literal["coding", "research", "mba", "core", "undecided", "pure_science"] = Field(
        description="Career interest, used to re-rank branches and produce guidance.",
    )
    data_mode: Literal["basic", "extended"] = Field(
        default="basic",
        description=(
            # TODO (reworkable): change Literal to just "basic" once the frontend
            # stops sending data_mode in the request payload.  For now, 'extended'
            # is accepted but silently treated as 'basic' by the recommender.
            "Dataset to use. Only 'basic' (2025 round-wise data) is active; "
            "'extended' is accepted for compatibility but resolves to 'basic'."
        ),
    )
    seat_category: str = Field(
        default="OPEN",
        description=(
            "Reservation category for seat allocation: OPEN, OBC-NCL, SC, ST, or EWS."
        ),
    )
    is_pwd: bool = Field(
        default=False,
        description="Whether the candidate belongs to Persons with Disabilities (PwD) subcategory.",
    )
    # family_income is removed to focus exclusively on admission probability insights.
    brand_branch_ratio: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Priority between branch tag weight (0.0) and institute brand (1.0).",
    )
    branch_preferences: List[str] = Field(
        default_factory=list,
        description=(
            "Branch families to filter by (e.g. 'cs_it', 'ece', 'mechanical'). "
            "An empty list (or only 'any') means show all branches. Unknown values "
            "are ignored. See /api/meta for the available options."
        ),
    )
    bucket: Optional[str] = Field(
        default="all",
        description="Bucket filter: safe, target, dream (or reach), or all.",
    )
    college_type: Optional[str] = Field(
        default="all",
        description="College type filter: IIT, NIT, IIIT, GFTI, or all.",
    )
    page: int = Field(
        default=1,
        ge=1,
        description="Page number for pagination (1-indexed).",
    )
    page_size: int = Field(
        default=50,
        ge=1,
        le=500,
        description="Page size for pagination.",
    )
    max_results: int = Field(
        default=5000,
        ge=1,
        le=10000,
        description="Maximum number of recommendations to return (legacy/fallback).",
    )
    lang: Literal["en", "hi", "gu", "kn"] = Field(
        default="en",
        description=(
            "Language for user-facing generated text (guidance, notes, category "
            "blurbs, fit labels and per-card reasons). 'en' English, 'hi' Hindi, 'gu' Gujarati, 'kn' Kannada."
        ),
    )

    # Pydantic v1 / v2 compatibility for model validation
    if IS_PYDANTIC_V2:
        @model_validator(mode="after")
        def _check_v2(self) -> "RecommendRequest":
            if self.adv_rank is None and self.mains_rank is None:
                raise ValueError("Provide at least one of adv_rank or mains_rank.")
            match = next(
                (s for s in states.INDIAN_STATES if s.lower() == self.home_state.strip().lower()),
                None,
            )
            if match:
                self.home_state = match
            return self
    else:
        @root_validator(pre=False)
        def _check_v1(cls, values):
            adv_rank = values.get("adv_rank")
            mains_rank = values.get("mains_rank")
            if adv_rank is None and mains_rank is None:
                raise ValueError("Provide at least one of adv_rank or mains_rank.")
            home_state = values.get("home_state")
            if home_state:
                match = next(
                    (s for s in states.INDIAN_STATES if s.lower() == home_state.strip().lower()),
                    None,
                )
                if match:
                    values["home_state"] = match
            return values


class Recommendation(BaseModel):
    institute: str
    institute_type: str
    institute_state: str
    exam: str
    branch: str
    branch_full: str
    degree: str
    quota: str
    gender_pool: str
    opening_rank: int
    closing_rank: int
    category: str  # Safe / Target / Reach
    fit_label: str  # human-readable explanation of the category
    interest_score: float
    matched_interest: bool
    home_state_advantage: Optional[int] = None  # ranks saved by the HS quota
    female_seat_advantage: Optional[int] = None  # extra rank cushion from the female pool
    confidence: str = "medium"  # high / medium / fragile OR the new custom volatility tags
    flag_round: Optional[int] = None  # the round where the largest vacancy-driven jump happened
    reason: str = ""  # templated "why this is here" explanation
    # estimated_fees, fee_waiver_applied, and fee_note are removed to focus on admission insights.
    # Future-proofing: If verified fees data becomes available, uncomment these fields:
    # estimated_fees: int = 0
    # fee_waiver_applied: bool = False
    # fee_note: str = ""
    region: str = "other"  # geographic region (north/south/east/west/northeast)
    is_metro: bool = False  # true if located in a major metro hub
    is_top_iit: bool = False  # true for Top 5 IITs (Bombay, Delhi, Madras, Kanpur, Kharagpur)
    history: Optional[dict[int, int]] = None  # historical closing ranks by year
    admission_probability: Optional[float] = None  # calculated admission probability %
    is_preparatory: bool = False
    has_preparatory_rounds: bool = False


class CategoryGuidance(BaseModel):
    category: str
    count: int
    blurb: str


class RecommendResponse(BaseModel):
    guidance: str
    interest_guidance: str
    counts: dict
    notes: List[str]
    category_guidance: List[CategoryGuidance]
    recommendations: List[Recommendation]
    page: int = 1
    page_size: int = 50
    total_count: int = 0
    total_pages: int = 0
    total_by_type: dict = Field(default_factory=dict)


class MetaResponse(BaseModel):
    states: List[str]
    goals: List[dict]
    genders: List[str]
    categories: List[dict]
    branches: List[dict]
    total_programs: int
    data_mode: str              # always "basic"
    allow_toggle: bool          # always False (extended toggle removed)
    extended_available: bool    # always False (extended dataset removed)
