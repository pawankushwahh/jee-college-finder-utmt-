"""Pydantic request/response models for the /recommend endpoint."""

from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel, Field, model_validator

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
    goal: Literal["coding", "research", "mba", "core", "undecided"] = Field(
        description="Career interest, used to re-rank branches and produce guidance.",
    )
    data_mode: Literal["basic", "extended"] = Field(
        default="basic",
        description=(
            "Which dataset to use. 'basic' = JEE_2025_Cutoffs.xlsx (OPEN only, 2025). "
            "'extended' = merged CSV (all categories, 2018-2025). "
            "Ignored if the server has allow_user_data_toggle=False."
        ),
    )
    seat_category: str = Field(
        default="OPEN",
        description=(
            "Reservation category for seat allocation: OPEN, OBC-NCL, SC, ST, EWS, or PwD. "
            "The current dataset contains OPEN seats only; support for reserved categories "
            "will be added when multi-category cutoff data becomes available."
        ),
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
    max_results: int = Field(
        default=60,
        ge=1,
        le=300,
        description="Maximum number of recommendations to return.",
    )
    lang: Literal["en", "hi", "gu", "kn"] = Field(
        default="en",
        description=(
            "Language for user-facing generated text (guidance, notes, category "
            "blurbs, fit labels and per-card reasons). 'en' English, 'hi' Hindi, 'gu' Gujarati, 'kn' Kannada."
        ),
    )

    @model_validator(mode="after")
    def _check(self) -> "RecommendRequest":
        if self.adv_rank is None and self.mains_rank is None:
            raise ValueError(
                "Provide at least one of adv_rank or mains_rank."
            )
        # Normalise home_state to the canonical casing if it matches a known state.
        match = next(
            (s for s in states.INDIAN_STATES if s.lower() == self.home_state.strip().lower()),
            None,
        )
        if match:
            self.home_state = match
        return self


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
    confidence: str = "medium"  # high / medium / fragile (from the rank spread)
    reason: str = ""  # templated "why this is here" explanation
    # estimated_fees, fee_waiver_applied, and fee_note are removed to focus on admission insights.
    # Future-proofing: If verified fees data becomes available, uncomment these fields:
    # estimated_fees: int = 0
    # fee_waiver_applied: bool = False
    # fee_note: str = ""
    region: str = "other"  # geographic region (north/south/east/west/northeast)
    is_metro: bool = False  # true if located in a major metro hub
    history: Optional[dict[int, int]] = None  # historical closing ranks by year
    admission_probability: Optional[float] = None  # calculated admission probability %


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


class MetaResponse(BaseModel):
    states: List[str]
    goals: List[dict]
    genders: List[str]
    categories: List[dict]
    branches: List[dict]
    total_programs: int
    data_mode: str              # server default: "basic" or "extended"
    allow_toggle: bool          # whether the UI data-source toggle is visible
    extended_available: bool    # whether the extended CSV file actually exists
