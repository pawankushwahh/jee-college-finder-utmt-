"""Pydantic request/response models for the KCET /recommend endpoint."""

from typing import List, Literal, Optional
from pydantic import BaseModel, Field

class KcetRecommendRequest(BaseModel):
    rank: int = Field(
        ge=1,
        description="KCET rank.",
    )
    quota: str = Field(
        default="GM",
        description="Quota/Category (e.g. GM, 1G, 2AG, etc.).",
    )
    branches: List[str] = Field(
        default_factory=list,
        description="List of selected branch families.",
    )
    bucket: Optional[str] = Field(
        default="all",
        description="Bucket filter: safe, target, reach, or all.",
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

class KcetProgramNode(BaseModel):
    institute: str
    program: str
    quota: str
    cutoff_rank: float
    bucket: str
    tags: List[str] = Field(default_factory=list)

class KcetRecommendResponse(BaseModel):
    safe: List[KcetProgramNode]
    target: List[KcetProgramNode]
    reach: List[KcetProgramNode]
    total_safe: int
    total_target: int
    total_reach: int
    has_next: bool

class KcetMetaResponse(BaseModel):
    quotas: List[str]
    goals: List[dict]
    total_programs: int
