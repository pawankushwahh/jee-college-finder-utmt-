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

logger = logging.getLogger(__name__)

_TEMPLATES_DIR = Path(__file__).resolve().parent.parent.parent / "templates" / "disha_templates"

router = APIRouter()


# ── Page routes (extension-less clean URLs) ──────────────────────────────
# StaticFiles(html=True) auto-resolves index.html for directory paths but
# does NOT resolve other pages by clean URL.  We add explicit routes here
# so they work under Sir's prefix (e.g. /learning_games/stats).

@router.get("/stats", include_in_schema=False)
def stats_page() -> FileResponse:
    """Serve the Statistical Insights page at the clean URL /stats."""
    return FileResponse(str(_TEMPLATES_DIR / "stats.html"))


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


@router.post("/api/recommend", response_model=RecommendResponse, tags=["recommend"])
def recommend_endpoint(req: RecommendRequest) -> RecommendResponse:
    """Return filtered, categorized and interest-ranked recommendations."""
    return recommend(req)


@router.get("/api/stats", tags=["meta"])
def stats_endpoint() -> dict:
    """Return dynamically computed statistical insights on the active dataset."""
    return compute_dataset_stats()
