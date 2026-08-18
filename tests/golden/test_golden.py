"""Replay every captured request and assert the response is unchanged.

This is the regression net for the multi-exam refactor.  It is the only
thing standing between "the code is tidier" and "the code is tidier and
students get different colleges", and it is the *only* automated coverage
KCET and COMEDK have at all.

If a case fails, the refactor changed behaviour.  Either fix the code, or —
if the change was intended — re-run ``python -m tests.golden.capture`` and
review the resulting diff as a deliberate record of what changed.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

import pytest
from fastapi.testclient import TestClient

from main import app

from .capture import data_fingerprints, execute, serialize
from .matrix import Case, all_cases

_GOLDEN_DIR = Path(__file__).resolve().parent
_MANIFEST = _GOLDEN_DIR / "manifest.json"

client = TestClient(app)


def _load(case: Case) -> Dict[str, Any] | None:
    path = _GOLDEN_DIR / case.exam / f"{case.key}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


_CASES: List[Case] = all_cases()


def test_baseline_exists():
    """A missing baseline is a setup error, not a pass."""
    assert _MANIFEST.exists(), (
        "No golden baseline found. Run `python -m tests.golden.capture` "
        "from the project root before refactoring."
    )


def test_source_data_unchanged():
    """The baseline is only meaningful against the CSVs it was captured from."""
    manifest = json.loads(_MANIFEST.read_text(encoding="utf-8"))
    assert data_fingerprints() == manifest["data_files"], (
        "Source CSV contents changed since the baseline was captured. "
        "Every expectation below is now suspect — re-capture deliberately."
    )


@pytest.mark.parametrize("case", _CASES, ids=lambda c: f"{c.exam}-{c.key}")
def test_response_unchanged(case: Case):
    expected = _load(case)
    assert expected is not None, (
        f"No baseline for {case.exam} {case.method} {case.path} ({case.note}). "
        "Re-run the capture script to add newly-introduced cases."
    )

    status, body = execute(client, case)

    assert status == expected["status"], (
        f"HTTP status changed for {case.note}: "
        f"{expected['status']} -> {status}"
    )
    assert serialize(body) == serialize(expected["body"]), (
        f"Response body changed for {case.note}"
    )
