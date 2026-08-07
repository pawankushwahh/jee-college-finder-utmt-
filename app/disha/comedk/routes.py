"""COMEDK API routes."""

from fastapi import APIRouter, Depends
from typing import Optional

from app.disha.states import VALID_GOALS, GOAL_LABELS
from .schemas import ComedkRecommendRequest, ComedkRecommendResponse, ComedkMetaResponse
from .recommender import recommend
from .data_loader import get_programs

router = APIRouter(prefix="/api/comedk", tags=["comedk"])

@router.get("/meta", response_model=ComedkMetaResponse)
def meta() -> ComedkMetaResponse:
    return ComedkMetaResponse(
        quotas=["GM", "KKR"],
        goals=[{"value": g, "label": GOAL_LABELS[g]} for g in VALID_GOALS],
        total_programs=len(get_programs())
    )

@router.get("/stats", tags=["comedk"])
def stats_endpoint() -> dict:
    from .stats_loader import compute_comedk_stats
    return compute_comedk_stats()

@router.post("/recommend", response_model=ComedkRecommendResponse)
def recommend_endpoint_post(req: ComedkRecommendRequest) -> ComedkRecommendResponse:
    return recommend(req)
