"""Page routes are generated from the exam registry — verify they still resolve.

The golden suite covers JSON APIs only, so when the hand-written page handlers
in ``routes.py`` were replaced by registry-driven generation these URLs had no
coverage at all. They are the entry point to the entire app: if ``/exam/kcet``
404s, nothing else matters.

Every expectation here is derived from ``registry.EXAMS`` rather than
hardcoded, so registering a new exam extends this suite automatically.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.disha.registry import EXAMS
from main import app

client = TestClient(app)

_NO_CACHE = "no-cache, no-store, must-revalidate"


@pytest.mark.parametrize("exam", EXAMS, ids=lambda e: e.id)
def test_exam_page_serves_html(exam):
    res = client.get(exam.page_route)
    assert res.status_code == 200, f"{exam.page_route} did not resolve"
    assert res.headers["content-type"].startswith("text/html")
    assert len(res.content) > 0


@pytest.mark.parametrize(
    "exam", [e for e in EXAMS if e.stats_route], ids=lambda e: e.id
)
def test_exam_stats_page_serves_html(exam):
    res = client.get(exam.stats_route)
    assert res.status_code == 200, f"{exam.stats_route} did not resolve"
    assert res.headers["content-type"].startswith("text/html")


@pytest.mark.parametrize(
    "exam", [e for e in EXAMS if e.stats_route], ids=lambda e: e.id
)
def test_stats_cache_headers_match_registration(exam):
    """JEE's /stats sends no cache headers where KCET's and COMEDK's do.

    That inconsistency predates the registry and is preserved deliberately;
    pinned here so it stays a *decision* rather than drifting silently.
    """
    res = client.get(exam.stats_route)
    if exam.stats_no_cache:
        assert res.headers.get("cache-control") == _NO_CACHE
    else:
        assert "cache-control" not in res.headers


def test_every_registered_template_exists():
    """A typo in a registration should fail here, not as a 404 in production."""
    from pathlib import Path

    templates = (
        Path(__file__).resolve().parent.parent / "templates" / "disha_templates"
    )
    for exam in EXAMS:
        assert (templates / exam.page_template).is_file(), (
            f"{exam.id}: missing page template {exam.page_template}"
        )
        if exam.stats_template:
            assert (templates / exam.stats_template).is_file(), (
                f"{exam.id}: missing stats template {exam.stats_template}"
            )


def test_registry_ids_are_unique():
    ids = [e.id for e in EXAMS]
    assert len(ids) == len(set(ids))
