"""KCET API routes."""

from fastapi import APIRouter
from typing import Optional

from app.disha.states import VALID_GOALS, GOAL_LABELS
from .schemas import KcetRecommendRequest, KcetRecommendResponse, KcetMetaResponse
from .recommender import recommend
from .data_loader import get_programs

router = APIRouter(prefix="/api/kcet", tags=["kcet"])

@router.get("/meta", response_model=KcetMetaResponse)
def meta() -> KcetMetaResponse:
    # Extract unique quotas/categories from loaded programs
    programs = get_programs()
    quotas = sorted(list(set(p["quota"] for p in programs if p.get("quota"))))
    if not quotas:
        quotas = ["GM"]  # default fallback
        
    return KcetMetaResponse(
        quotas=quotas,
        goals=[{"value": g, "label": GOAL_LABELS[g]} for g in VALID_GOALS],
        total_programs=len(programs)
    )

@router.post("/recommend", response_model=KcetRecommendResponse)
def recommend_endpoint_post(req: KcetRecommendRequest) -> KcetRecommendResponse:
    return recommend(req)

@router.get("/stats", tags=["kcet"])
def stats_endpoint() -> dict:
    from .stats_loader import compute_kcet_stats
    return compute_kcet_stats()
