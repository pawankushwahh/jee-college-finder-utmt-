"""FastAPI application entry point — standalone development & UTMT integration.

Disha lives under:
  - Backend:  app/disha/
  - Frontend: templates/disha_templates/

UTMT Integration:
  Sir's main.py plugs Disha in with:
      from app.disha.routes import router as disha_router
      app.include_router(disha_router, prefix="/learning_games", tags=["learning_games"])
      app.mount("/learning_games", StaticFiles(..., html=True), name="disha")

Standalone:
  Run: uvicorn main:app --reload --port 8000
  Open: http://127.0.0.1:8000/
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

from app.disha.routes import router as disha_router
from app.disha.config import settings
from app.disha.data_loader import load_programs_basic

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
    # Preload the 2025 dataset at startup so the first request is fast.
    load_programs_basic()
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
# API routes — imported from app/disha/routes.py
# In standalone mode these live at the root (no prefix).
# On UTMT portal Sir adds prefix="/learning_games".
# ---------------------------------------------------------------------------
app.include_router(disha_router)


# ---------------------------------------------------------------------------
# Static file serving  (must come AFTER API routes)
# ---------------------------------------------------------------------------

@app.get("/", include_in_schema=False)
def portal_root() -> FileResponse:
    return _static_file_response(_TEMPLATES_DIR / "index.html")


@app.get("/{full_path:path}", include_in_schema=False)
def spa_fallback(full_path: str) -> FileResponse:
    """Serve static assets from the templates directory.

    For paths that look like files (have an extension), serve the file or 404.
    For navigation-like paths (no extension), fall back to index.html.
    """
    from fastapi.responses import JSONResponse

    target = _TEMPLATES_DIR / full_path
    if target.is_file():
        return _static_file_response(target)

    # Only fall back to index.html for navigation-like paths (no file extension).
    # Asset requests (e.g. /exam/sw.js) should 404 properly.
    if '.' in full_path.split('/')[-1]:
        from fastapi.responses import PlainTextResponse
        return PlainTextResponse("Not Found", status_code=404)

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
