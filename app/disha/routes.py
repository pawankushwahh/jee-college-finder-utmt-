"""
Disha API routes — JEE College Recommendation engine.

All API endpoints are defined on an APIRouter so Sir's UTMT portal
can plug them in with:

    from app.disha.routes import router as disha_router
    app.include_router(disha_router, prefix="/learning_games", tags=["learning_games"])

For standalone development, main.py includes this router at the root.
"""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse

from app.disha import states
from app.disha.config import settings
from app.disha.data_loader import load_programs, load_programs_basic
from app.disha.stats_loader import compute_dataset_stats
from app.disha.recommender import recommend
from app.disha.schemas import MetaResponse, RecommendRequest, RecommendResponse
from app.disha.comedk.routes import router as comedk_router
from app.disha.kcet.routes import router as kcet_router

logger = logging.getLogger(__name__)

_TEMPLATES_DIR = Path(__file__).resolve().parent.parent.parent / "templates" / "disha_templates"

router = APIRouter()
router.include_router(comedk_router)
router.include_router(kcet_router)


# ── Page routes (extension-less clean URLs) ──────────────────────────────
# StaticFiles(html=True) auto-resolves index.html for directory paths but
# does NOT resolve other pages by clean URL.  We add explicit routes here
# so they work under Sir's prefix (e.g. /learning_games/stats).

@router.get("/stats", include_in_schema=False)
def stats_page() -> FileResponse:
    """Serve the Statistical Insights page at the clean URL /stats."""
    return FileResponse(str(_TEMPLATES_DIR / "stats.html"))


@router.get("/exam/jee", include_in_schema=False)
def exam_jee_page() -> FileResponse:
    return FileResponse(str(_TEMPLATES_DIR / "jee.html"))


@router.get("/exam/kcet", include_in_schema=False)
def exam_kcet_page() -> FileResponse:
    return FileResponse(str(_TEMPLATES_DIR / "kcet" / "index.html"))


@router.get("/exam/kcet/stats", include_in_schema=False)
def exam_kcet_stats_page() -> FileResponse:
    return FileResponse(
        str(_TEMPLATES_DIR / "kcet" / "stats.html"),
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0",
        },
    )


@router.get("/exam/comedk", include_in_schema=False)
def exam_comedk_page() -> FileResponse:
    return FileResponse(str(_TEMPLATES_DIR / "comedk" / "index.html"))

@router.get("/exam/comedk/stats", include_in_schema=False)
def exam_comedk_stats_page() -> FileResponse:
    return FileResponse(
        str(_TEMPLATES_DIR / "comedk" / "stats.html"),
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0",
        },
    )


@router.get("/api/health", tags=["meta"])
def health() -> dict:
    return {"status": "ok", "programs": len(load_programs())}


@router.get("/api/meta", response_model=MetaResponse, tags=["meta"])
def meta() -> MetaResponse:
    """Form metadata: valid states, goals, genders, categories and dataset size."""
    categories = states.VALID_CATEGORIES
    return MetaResponse(
        states=states.INDIAN_STATES,
        goals=[{"value": g, "label": states.GOAL_LABELS[g]} for g in states.VALID_GOALS],
        genders=states.VALID_GENDERS,
        categories=categories,
        branches=[{"value": b["value"], "label": b["label"]} for b in states.BRANCH_PREFERENCES],
        total_programs=len(load_programs(settings.data_mode)),
        data_mode=settings.data_mode,
        allow_toggle=False,
        extended_available=False,
    )


from typing import Optional
from fastapi import Query


@router.api_route("/api/recommend", methods=["GET", "POST"], response_model=RecommendResponse, tags=["recommend"])
def recommend_endpoint(
    req: Optional[RecommendRequest] = None,
    adv_rank: Optional[int] = Query(default=None),
    mains_rank: Optional[int] = Query(default=None),
    gender: Optional[str] = Query(default="male"),
    home_state: Optional[str] = Query(default="Delhi"),
    goal: Optional[str] = Query(default="coding"),
    seat_category: Optional[str] = Query(default="OPEN"),
    is_pwd: Optional[bool] = Query(default=False),
    bucket: Optional[str] = Query(default=None),
    college_type: Optional[str] = Query(default=None),
    page: Optional[int] = Query(default=None, ge=1),
    page_size: Optional[int] = Query(default=None, ge=1, le=500),
) -> RecommendResponse:
    """Return filtered, categorized and interest-ranked recommendations."""
    if req is None:
        cat = seat_category or "OPEN"
        if is_pwd and not cat.endswith(" (PwD)"):
            cat = f"{cat} (PwD)"
        req = RecommendRequest(
            adv_rank=adv_rank,
            mains_rank=mains_rank,
            gender=gender if gender in ("male", "female") else "male",
            home_state=home_state or "Delhi",
            goal=goal if goal in ("coding", "research", "mba", "core", "undecided", "pure_science") else "coding",
            seat_category=cat,
            is_pwd=bool(is_pwd),
        )
    if bucket is not None:
        req.bucket = bucket
    if college_type is not None:
        req.college_type = college_type
    if page is not None:
        req.page = page
    if page_size is not None:
        req.page_size = page_size
    return recommend(req)


@router.get("/api/stats", tags=["meta"])
def stats_endpoint() -> dict:
    """Return dynamically computed statistical insights on the active dataset."""
    return compute_dataset_stats()
