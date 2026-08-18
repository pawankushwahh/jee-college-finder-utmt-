"""Pydantic request/response models for the COMEDK /recommend endpoint.

Mirrors ``app/disha/schemas.py`` in shape: request, per-card recommendation,
category guidance, and response envelope.  All legacy field names that the
existing frontend reads (``safe``, ``target``, ``reach``, ``total_safe``,
``total_target``, ``total_reach``, ``has_next``, per-card ``institute`` /
``program`` / ``quota`` / ``cutoff_rank``) are preserved.
"""

from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Request
# ---------------------------------------------------------------------------
class ComedkRecommendRequest(BaseModel):
    rank: int = Field(
        ge=1,
        description="COMEDK rank.",
    )
    quota: str = Field(
        default="GM",
        description="Quota: GM (General Merit) or KKR (Kalyana Karnataka Region).",
    )
    branch_families: List[str] = Field(
        default_factory=list,
        description=(
            "Preferred branch-family filter (e.g. ['cse', 'ai_ds']).  "
            "Empty list means show all families."
        ),
    )
    bucket: Optional[str] = Field(
        default="all",
        description="Bucket filter: safe, target, reach/dream, or all.",
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
    lang: Literal["en", "hi", "gu", "kn"] = Field(
        default="en",
        description=(
            "Language for user-facing text (guidance, notes, fit labels, reasons). "
            "'en' English, 'hi' Hindi, 'gu' Gujarati, 'kn' Kannada."
        ),
    )


# ---------------------------------------------------------------------------
# Per-card recommendation
# ---------------------------------------------------------------------------
class ComedkProgramNode(BaseModel):
    """Single recommendation card.

    Legacy fields (``institute``, ``program``, ``quota``, ``cutoff_rank``,
    ``bucket``, ``tags``) are kept so the existing frontend keeps working.
    New fields are additive.
    """
    # ── Legacy fields (frontend reads these) ─────────────────────────────
    institute: str
    program: str
    quota: str
    cutoff_rank: float
    bucket: str                         # "Safe" / "Target" / "Reach" — legacy
    tags: List[str] = Field(default_factory=list)

    # ── New JEE-parallel fields ──────────────────────────────────────────
    category: str = ""                  # same as bucket, canonical name
    fit_label: str = ""
    reason: str = ""
    admission_probability: Optional[float] = None
    confidence: str = "medium"
    interest_score: float = 0.0
    matched_interest: bool = False
    rank_gap: int = 0                   # cutoff - rank (positive = student ahead)
    brand_score: float = 0.55
    brand_tier: str = "emerging"
    is_metro: bool = False
    kkr_gap: Optional[float] = None     # KKR_cutoff - GM_cutoff
    branch: str = ""                    # short name (without degree suffix)
    branch_family: str = ""
    degree: str = ""


# ---------------------------------------------------------------------------
# Category guidance
# ---------------------------------------------------------------------------
class ComedkCategoryGuidance(BaseModel):
    category: str
    count: int
    blurb: str


# ---------------------------------------------------------------------------
# Response envelope
# ---------------------------------------------------------------------------
class ComedkRecommendResponse(BaseModel):
    """Full response envelope.

    Legacy fields (``safe``, ``target``, ``reach``, ``total_safe``,
    ``total_target``, ``total_reach``, ``has_next``) are kept for backward
    compatibility with the existing frontend JS.  New JEE-parallel fields
    are additive.
    """
    # ── Legacy fields (frontend reads these) ─────────────────────────────
    safe: List[ComedkProgramNode] = Field(default_factory=list)
    target: List[ComedkProgramNode] = Field(default_factory=list)
    reach: List[ComedkProgramNode] = Field(default_factory=list)
    total_safe: int = 0
    total_target: int = 0
    total_reach: int = 0
    has_next: bool = False

    # ── New JEE-parallel fields ──────────────────────────────────────────
    guidance: str = ""
    interest_guidance: str = ""
    counts: dict = Field(default_factory=dict)
    notes: List[str] = Field(default_factory=list)
    category_guidance: List[ComedkCategoryGuidance] = Field(default_factory=list)
    recommendations: List[ComedkProgramNode] = Field(default_factory=list)
    total_count: int = 0
    total_by_type: dict = Field(default_factory=dict)
    thresholds: dict = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Meta response
# ---------------------------------------------------------------------------
class ComedkMetaResponse(BaseModel):
    quotas: List[str]
    goals: List[dict]
    branch_families: List[dict]
    total_programs: int
