"""KCET API routes."""

from __future__ import annotations

from fastapi import APIRouter

from . import states
from .data_loader import get_institute_count, get_seat_categories, load_programs
from .recommender import recommend
from .schemas import KcetMetaResponse, KcetRecommendRequest, KcetRecommendResponse

router = APIRouter(prefix="/api/kcet", tags=["kcet"])


@router.get("/health")
def health() -> dict:
    return {"status": "ok", "programs": len(load_programs())}


@router.get("/meta", response_model=KcetMetaResponse)
def meta() -> KcetMetaResponse:
    categories = get_seat_categories() or ["GM"]
    return KcetMetaResponse(
        seat_categories=[
            {"value": c, "label": states.describe_category(c)} for c in categories
        ],
        goals=[{"value": g, "label": states.GOAL_LABELS[g]} for g in states.VALID_GOALS],
        branch_preferences=[
            {"value": b["value"], "label": b["label"]} for b in states.BRANCH_PREFERENCES
        ],
        total_programs=len(load_programs()),
        total_institutes=get_institute_count(),
    )


@router.post("/recommend", response_model=KcetRecommendResponse)
def recommend_endpoint(req: KcetRecommendRequest) -> KcetRecommendResponse:
    return recommend(req)


@router.get("/stats")
def stats_endpoint() -> dict:
    from .stats_loader import compute_kcet_stats

    return compute_kcet_stats()
