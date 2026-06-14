"""FastAPI application: serves both the JEE recommendation JSON API and the
static single-page portal in a single unified deployment.

All API routes are namespaced under /api. Static assets (CSS, JS, images) are
served from the frontend/ directory. Any path that does not match an API route
or a static asset falls back to index.html so the SPA works on refresh.

Run locally:
    cd backend && uvicorn app.main:app --reload

Then open http://127.0.0.1:8000 — the portal and API are on the same origin.
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

from . import states
from .config import settings
from .data_loader import load_programs
from .recommender import recommend
from .schemas import MetaResponse, RecommendRequest, RecommendResponse

logger = logging.getLogger(__name__)

_BACKEND_ROOT = Path(__file__).resolve().parent.parent


def _resolve_frontend_dir() -> Path:
    """Locate the static portal directory for dev and Docker layouts."""
    if env_dir := os.environ.get("FRONTEND_DIR"):
        return Path(env_dir)

    for candidate in (
        _BACKEND_ROOT.parent / "frontend",  # local dev: repo root / frontend
        _BACKEND_ROOT / "frontend",         # Docker: backend/frontend
    ):
        if (candidate / "index.html").is_file():
            return candidate

    return _BACKEND_ROOT.parent / "frontend"


_FRONTEND_DIR = _resolve_frontend_dir()


def _frontend_exists() -> bool:
    return _FRONTEND_DIR.is_dir() and (_FRONTEND_DIR / "index.html").exists()


def _static_file_response(path: Path) -> FileResponse:
    media_type, _ = mimetypes.guess_type(str(path))
    headers: dict[str, str] = {}
    # Prevent browsers / CDNs from pinning old HTML/JS/CSS after a deploy.
    rel = path.name.lower()
    if rel in {"index.html", "sw.js", "manifest.json"} or rel.endswith((".js", ".css")):
        headers["Cache-Control"] = "no-cache, must-revalidate"
    return FileResponse(str(path), media_type=media_type, headers=headers)


@asynccontextmanager
async def lifespan(_: FastAPI):
    # Parse the workbook once at startup so the first request is fast.
    load_programs()
    logger.info("Serving frontend from %s (exists=%s)", _FRONTEND_DIR, _frontend_exists())
    yield


app = FastAPI(
    title="JEE College Recommender",
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
    return MetaResponse(
        states=states.INDIAN_STATES,
        goals=[{"value": g, "label": states.GOAL_LABELS[g]} for g in states.VALID_GOALS],
        genders=states.VALID_GENDERS,
        categories=states.VALID_CATEGORIES,
        branches=[{"value": b["value"], "label": b["label"]} for b in states.BRANCH_PREFERENCES],
        total_programs=len(load_programs()),
    )


@app.post("/api/recommend", response_model=RecommendResponse, tags=["recommend"])
def recommend_endpoint(req: RecommendRequest) -> RecommendResponse:
    """Return filtered, categorized and interest-ranked recommendations."""
    return recommend(req)


# ---------------------------------------------------------------------------
# Static file serving  (must come AFTER API routes)
# ---------------------------------------------------------------------------

if _frontend_exists():
    # Serve individual asset directories so paths like /css/style.css work.
    for _subdir in ("css", "js", "assets"):
        _d = _FRONTEND_DIR / _subdir
        if _d.is_dir():
            app.mount(f"/{_subdir}", StaticFiles(directory=str(_d)), name=_subdir)

    @app.get("/", include_in_schema=False)
    def portal_root() -> FileResponse:
        return FileResponse(
            str(_FRONTEND_DIR / "index.html"),
            media_type="text/html",
            headers={"Cache-Control": "no-cache, must-revalidate"},
        )

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa_fallback(full_path: str) -> FileResponse:
        """Serve static assets or index.html for unmatched SPA paths."""
        target = _FRONTEND_DIR / full_path
        if target.is_file():
            return _static_file_response(target)
        return FileResponse(str(_FRONTEND_DIR / "index.html"), media_type="text/html")

else:
    # Frontend directory not present — API-only mode (e.g. running backend/ standalone).
    @app.get("/", include_in_schema=False)
    def root() -> dict:
        return {
            "service": "jee-college-recommender-api",
            "note": "Frontend not found. See /api/docs for the API.",
            "docs": "/api/docs",
            "health": "/api/health",
        }
