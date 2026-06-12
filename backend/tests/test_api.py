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


def test_recommend_requires_a_rank():
    res = client.post(
        "/api/recommend",
        json={"gender": "male", "home_state": "Rajasthan", "goal": "coding"},
    )
    assert res.status_code == 422
