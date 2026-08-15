"""The single place where an exam is registered.

Adding an exam previously meant editing five separate files — this module,
``landing.js``, ``sw.js``, ``main.py``'s preload and the exam's own package —
with nothing keeping them in step. That drift is not hypothetical: ``sw.js``
still precaches ``kcet.html``, a file that has never existed at that path.

Everything the backend needs to know about which exams exist now lives here.
Route mounting and page serving derive from this list, so a new exam adds one
``ExamRegistration`` rather than a new set of hand-written route handlers.

The registration deliberately describes *routing*, not engine behaviour. How
an exam buckets a rank or scores a branch stays in its own package; this is
only the wiring.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter
from fastapi.responses import FileResponse

# Headers used on the KCET and COMEDK stats pages. JEE's /stats deliberately
# does not send them — preserved as-is rather than harmonised, because that
# would be a behaviour change wearing a refactor's clothing.
_NO_CACHE_HEADERS = {
    "Cache-Control": "no-cache, no-store, must-revalidate",
    "Pragma": "no-cache",
    "Expires": "0",
}


@dataclass(frozen=True)
class ExamRegistration:
    """One exam's public wiring.

    Attributes
    ----------
    id:
        Short slug used in URLs and as the registry key (``"jee"``).
    label:
        Human-readable name, for docs and API tags.
    page_route / page_template:
        Clean URL for the exam's SPA shell, and the template file it serves.
    stats_route / stats_template:
        The exam's insights page, if it has one.
    stats_no_cache:
        Whether the stats page sends no-store headers. True for KCET and
        COMEDK, False for JEE — an existing inconsistency, preserved.
    api_router:
        The exam's own ``APIRouter``. ``None`` for JEE, whose endpoints are
        defined directly on the root router for backwards compatibility with
        the ``/api/recommend`` (unprefixed) paths the portal already calls.
    """

    id: str
    label: str
    page_route: str
    page_template: str
    stats_route: Optional[str] = None
    stats_template: Optional[str] = None
    stats_no_cache: bool = False
    api_router: Optional[APIRouter] = None


def _build() -> List[ExamRegistration]:
    # Imported inside the function so the registry module itself stays free of
    # import-order constraints: each exam package imports from core, and core
    # must never import an exam.
    from app.disha.comedk.routes import router as comedk_router
    from app.disha.kcet.routes import router as kcet_router

    return [
        ExamRegistration(
            id="jee",
            label="JEE / JEE Advanced",
            page_route="/exam/jee",
            page_template="jee.html",
            # JEE's insights page predates the /exam/<id>/stats convention and
            # is still linked as /stats from the frontend.
            stats_route="/stats",
            stats_template="stats.html",
            stats_no_cache=False,
            api_router=None,
        ),
        ExamRegistration(
            id="kcet",
            label="KCET",
            page_route="/exam/kcet",
            page_template="kcet/index.html",
            stats_route="/exam/kcet/stats",
            stats_template="kcet/stats.html",
            stats_no_cache=True,
            api_router=kcet_router,
        ),
        ExamRegistration(
            id="comedk",
            label="COMEDK",
            page_route="/exam/comedk",
            page_template="comedk/index.html",
            stats_route="/exam/comedk/stats",
            stats_template="comedk/stats.html",
            stats_no_cache=True,
            api_router=comedk_router,
        ),
    ]


EXAMS: List[ExamRegistration] = _build()

EXAMS_BY_ID = {exam.id: exam for exam in EXAMS}


def register(router: APIRouter, templates_dir: Path) -> None:
    """Mount every registered exam's API router and page routes.

    Page routes exist because ``StaticFiles(html=True)`` resolves
    ``index.html`` for directory paths but not other pages by clean URL, and
    they must work under the portal's ``/learning_games`` prefix.
    """
    for exam in EXAMS:
        if exam.api_router is not None:
            router.include_router(exam.api_router)

    for exam in EXAMS:
        _add_page_route(
            router, exam.page_route, templates_dir / exam.page_template, False
        )
        if exam.stats_route and exam.stats_template:
            _add_page_route(
                router,
                exam.stats_route,
                templates_dir / exam.stats_template,
                exam.stats_no_cache,
            )


def _add_page_route(
    router: APIRouter, route: str, template: Path, no_cache: bool
) -> None:
    # Defaults bind the loop variables at definition time; without them every
    # generated handler would close over the last exam in the list.
    def handler(_template: Path = template, _no_cache: bool = no_cache) -> FileResponse:
        if _no_cache:
            return FileResponse(str(_template), headers=_NO_CACHE_HEADERS)
        return FileResponse(str(_template))

    router.add_api_route(
        route,
        handler,
        methods=["GET"],
        include_in_schema=False,
        name=f"page:{route}",
    )
