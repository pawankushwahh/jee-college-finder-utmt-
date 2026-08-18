"""Capture the current API responses as the golden baseline.

Run this **before** any refactor step:

    python -m tests.golden.capture

It writes one JSON file per request under ``tests/golden/<exam>/`` plus a
manifest recording the sha256 of each source CSV.  ``test_golden.py`` then
replays every case and asserts the response is byte-identical.

Re-running overwrites the baseline, so only do that when a change of
behaviour is *intended* — and review the resulting diff, because that diff
is the behaviour change.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import sys
from pathlib import Path
from typing import Any, Dict

from .matrix import DATA_FILES, Case, all_cases

_ROOT = Path(__file__).resolve().parent.parent.parent
_GOLDEN_DIR = Path(__file__).resolve().parent
_MANIFEST = _GOLDEN_DIR / "manifest.json"


def serialize(body: Any) -> str:
    """Canonical JSON form used for both storage and comparison.

    ``sort_keys`` makes the comparison independent of dict insertion order,
    and ``ensure_ascii=False`` keeps the Hindi/Gujarati/Kannada strings
    readable in the committed baseline instead of escaping them to \\uXXXX.
    """
    return json.dumps(body, sort_keys=True, ensure_ascii=False, indent=2)


def execute(client, case: Case):
    """Run one case against a TestClient and return (status, body)."""
    if case.method == "GET":
        res = client.get(case.path, params=case.params)
    else:
        res = client.post(case.path, json=case.payload)
    try:
        body = res.json()
    except Exception:  # non-JSON error body
        body = {"__non_json_body__": res.text}
    return res.status_code, body


def data_fingerprints() -> Dict[str, str]:
    """sha256 of every source CSV the baseline depends on."""
    out: Dict[str, str] = {}
    for rel in DATA_FILES:
        path = _ROOT / rel
        out[rel] = hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else "MISSING"
    return out


def main() -> int:
    from fastapi.testclient import TestClient

    from main import app

    cases = all_cases()

    # Start from scratch so cases deleted from the matrix don't leave orphan
    # baseline files behind, which would silently never be replayed again.
    for exam_dir in _GOLDEN_DIR.iterdir():
        if exam_dir.is_dir() and exam_dir.name not in {"__pycache__"}:
            shutil.rmtree(exam_dir)

    counts: Dict[str, int] = {}
    with TestClient(app) as client:
        for case in cases:
            status, body = execute(client, case)
            out_dir = _GOLDEN_DIR / case.exam
            out_dir.mkdir(parents=True, exist_ok=True)
            record = {
                "note": case.note,
                "request": {
                    "method": case.method,
                    "path": case.path,
                    "payload": case.payload,
                    "params": case.params,
                },
                "status": status,
                "body": body,
            }
            (out_dir / f"{case.key}.json").write_text(
                serialize(record) + "\n", encoding="utf-8"
            )
            counts[case.exam] = counts.get(case.exam, 0) + 1

    _MANIFEST.write_text(
        serialize({"data_files": data_fingerprints(), "case_counts": counts}) + "\n",
        encoding="utf-8",
    )

    total = sum(counts.values())
    for exam in sorted(counts):
        print(f"  {exam:8s} {counts[exam]:4d} cases")
    print(f"  {'TOTAL':8s} {total:4d} cases")
    return 0


if __name__ == "__main__":
    sys.exit(main())
