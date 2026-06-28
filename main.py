"""FastAPI application entry point.

Disha lives under:
  - Backend:  app/disha/
  - Frontend: templates/disha_templates/

Run: uvicorn main:app --reload --port 8000
"""

from __future__ import annotations

import logging
import mimetypes
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.disha import states
from app.disha.config import settings
from app.disha.data_loader import load_programs, load_programs_basic, load_programs_extended
from app.disha.recommender import recommend
from app.disha.schemas import MetaResponse, RecommendRequest, RecommendResponse

logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parent
_TEMPLATES_DIR = _PROJECT_ROOT / "templates" / "disha_templates"


def _static_file_response(path: Path) -> FileResponse:
    media_type, _ = mimetypes.guess_type(str(path))
    headers: dict[str, str] = {}
    rel = path.name.lower()
    if rel in {"index.html", "sw.js", "manifest.json"} or rel.endswith((".js", ".css")):
        headers["Cache-Control"] = "no-cache, must-revalidate"
    return FileResponse(str(path), media_type=media_type, headers=headers)


@asynccontextmanager
async def lifespan(_: FastAPI):
    # Always preload the basic (default) dataset so the first request is fast.
    load_programs_basic()
    # Preload the extended dataset too when the user toggle is allowed, so
    # switching modes is instant rather than incurring a cold-parse delay.
    if settings.allow_user_data_toggle and settings.resolved_extended_data_path.exists():
        logger.info("Preloading extended dataset…")
        load_programs_extended()
    logger.info("Serving frontend from %s", _TEMPLATES_DIR)
    yield


app = FastAPI(
    title="Disha — JEE College Recommender",
    description=(
        "Open-source intelligent pipeline that suggests institutes and branches "
        "from JEE Advanced/Mains rank, gender, home state and career interest, "
        "using JoSAA 2025 cutoffs. Portal and API served from the same origin."
    ),
    version="3.0.0",
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# API routes  (/api/*)
# ---------------------------------------------------------------------------

@app.get("/api/health", tags=["meta"])
def health() -> dict:
    return {"status": "ok", "programs": len(load_programs())}


@app.get("/api/meta", response_model=MetaResponse, tags=["meta"])
def meta() -> MetaResponse:
    """Form metadata: valid states, goals, genders, categories and dataset size."""
    extended_exists = settings.resolved_extended_data_path.exists()
    categories = [
        {**c, "available": True if extended_exists else c["available"]}
        for c in states.VALID_CATEGORIES
    ]
    return MetaResponse(
        states=states.INDIAN_STATES,
        goals=[{"value": g, "label": states.GOAL_LABELS[g]} for g in states.VALID_GOALS],
        genders=states.VALID_GENDERS,
        categories=categories,
        branches=[{"value": b["value"], "label": b["label"]} for b in states.BRANCH_PREFERENCES],
        total_programs=len(load_programs(settings.data_mode)),
        data_mode=settings.data_mode,
        allow_toggle=settings.allow_user_data_toggle and extended_exists,
        extended_available=extended_exists,
    )


@app.post("/api/recommend", response_model=RecommendResponse, tags=["recommend"])
def recommend_endpoint(req: RecommendRequest) -> RecommendResponse:
    """Return filtered, categorized and interest-ranked recommendations."""
    return recommend(req)


# ---------------------------------------------------------------------------
# Static file serving  (must come AFTER API routes)
# ---------------------------------------------------------------------------

@app.get("/", include_in_schema=False)
def portal_root() -> FileResponse:
    return _static_file_response(_TEMPLATES_DIR / "index.html")


@app.get("/{full_path:path}", include_in_schema=False)
def spa_fallback(full_path: str) -> FileResponse:
    """Serve static assets or index.html for unmatched paths."""
    target = _TEMPLATES_DIR / full_path
    if target.is_file():
        return _static_file_response(target)
    return _static_file_response(_TEMPLATES_DIR / "index.html")


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", 8000))
    debug = os.getenv("APP_DEBUG", "false").lower() == "true"

    print()
    print("  Disha — JEE College Recommender")
    print("  ===============================")
    print(f"  Open: http://127.0.0.1:{port}/")
    print()

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
        reload=debug,
    )
