"""Integration tests for the HTTP API surface (routes, schemas, errors)."""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health():
    res = client.get("/api/health")
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "ok"
    assert body["programs"] > 0


def test_meta_shape():
    res = client.get("/api/meta")
    assert res.status_code == 200
    body = res.json()
    assert "Rajasthan" in body["states"]
    assert {g["value"] for g in body["goals"]} == {
        "coding", "research", "mba", "core", "undecided",
    }
    assert body["genders"] == ["male", "female"]
    assert body["total_programs"] > 2000
    # Reservation categories should be present
    cat_values = {c["value"] for c in body["categories"]}
    assert "OPEN" in cat_values
    assert {"OBC-NCL", "SC", "ST", "EWS", "PwD"}.issubset(cat_values)
    # Branch-preference options should be present
    branch_values = {b["value"] for b in body["branches"]}
    assert {"cs_it", "ece", "mechanical"}.issubset(branch_values)


def test_recommend_branch_preference_filters_branches():
    res = client.post(
        "/api/recommend",
        json={
            "mains_rank": 6000,
            "gender": "male",
            "home_state": "Rajasthan",
            "goal": "coding",
            "branch_preferences": ["cs_it"],
        },
    )
    assert res.status_code == 200
    body = res.json()
    assert body["recommendations"], "expected CS/IT options for a mid rank"
    for r in body["recommendations"]:
        text = (r["branch"] + " " + r["branch_full"]).lower()
        assert any(k in text for k in ("computer", "information technology", "cse"))


def test_recommend_endpoint_returns_results():
    res = client.post(
        "/api/recommend",
        json={
            "adv_rank": 1500,
            "mains_rank": 6000,
            "gender": "female",
            "home_state": "Rajasthan",
            "goal": "coding",
        },
    )
    assert res.status_code == 200
    body = res.json()
    assert body["recommendations"], "expected recommendations for a mid rank"
    assert set(body["counts"]) == {"total", "shown", "by_category", "by_type"}
    first = body["recommendations"][0]
    assert first["category"] in {"Safe", "Target", "Reach"}


def test_recommend_hindi_lang_returns_devanagari():
    res = client.post(
        "/api/recommend",
        json={
            "adv_rank": 1500,
            "mains_rank": 6000,
            "gender": "female",
            "home_state": "Rajasthan",
            "goal": "coding",
            "lang": "hi",
        },
    )
    assert res.status_code == 200
    body = res.json()
    assert body["recommendations"], "expected recommendations for a mid rank"

    def has_devanagari(text: str) -> bool:
        return any("\u0900" <= ch <= "\u097f" for ch in text)

    assert has_devanagari(body["guidance"])
    assert has_devanagari(body["interest_guidance"])
    assert has_devanagari(body["recommendations"][0]["reason"])
    assert has_devanagari(body["recommendations"][0]["fit_label"])


def test_recommend_rejects_invalid_lang():
    res = client.post(
        "/api/recommend",
        json={
            "mains_rank": 6000,
            "gender": "male",
            "home_state": "Rajasthan",
            "goal": "coding",
            "lang": "fr",
        },
    )
    assert res.status_code == 422


def test_recommend_requires_a_rank():
    res = client.post(
        "/api/recommend",
        json={"gender": "male", "home_state": "Rajasthan", "goal": "coding"},
    )
    assert res.status_code == 422
