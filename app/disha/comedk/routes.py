"""COMEDK API routes.

Mirrors ``app/disha/routes.py`` in shape: /meta, /stats, /recommend.
"""

from fastapi import APIRouter

from .schemas import (
    ComedkMetaResponse,
    ComedkRecommendRequest,
    ComedkRecommendResponse,
)
from .recommender import recommend
from .data_loader import get_programs, get_quotas
from . import states

router = APIRouter(prefix="/api/comedk", tags=["comedk"])


@router.get("/meta", response_model=ComedkMetaResponse)
def meta() -> ComedkMetaResponse:
    """Return available quotas, branch families and programme count."""
    return ComedkMetaResponse(
        quotas=get_quotas(),
        goals=[],  # goals removed — branch preferences are used instead
        branch_families=states.BRANCH_PREFERENCES,
        total_programs=len(get_programs()),
    )


@router.get("/stats", tags=["comedk"])
def stats_endpoint() -> dict:
    from .stats_loader import compute_comedk_stats
    return compute_comedk_stats()


@router.post("/recommend", response_model=ComedkRecommendResponse)
def recommend_endpoint_post(req: ComedkRecommendRequest) -> ComedkRecommendResponse:
    return recommend(req)
