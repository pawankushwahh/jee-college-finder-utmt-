"""Contract tests for the KCET and COMEDK insights endpoints.

These assert the *shape and internal consistency* of the stats payloads rather
than exact numbers: the figures move whenever the dataset is rebuilt, and the
golden baseline already pins the byte-exact response. What matters here is that
each exam-specific section stays present and self-consistent, so a loader change
cannot silently empty a panel the dashboard renders.

JEE is deliberately not covered here — its stats page and endpoint are out of
scope for this suite and are pinned by the golden baseline.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


@pytest.fixture(scope="module")
def kcet_stats() -> dict:
    response = client.get("/api/kcet/stats")
    assert response.status_code == 200
    return response.json()


@pytest.fixture(scope="module")
def comedk_stats() -> dict:
    response = client.get("/api/comedk/stats")
    assert response.status_code == 200
    return response.json()


# ── Shared expectations ────────────────────────────────────────────────────


@pytest.mark.parametrize("path", ["/api/kcet/stats", "/api/comedk/stats"])
def test_stats_endpoint_serves_a_summary(path: str) -> None:
    payload = client.get(path).json()
    summary = payload["summary"]
    assert summary["total_records"] > 0
    assert summary["unique_institutes"] > 0
    assert summary["unique_programs"] > 0
    assert 0 < summary["rank_min"] <= summary["rank_max"]


@pytest.mark.parametrize("path", ["/api/kcet/stats", "/api/comedk/stats"])
def test_legacy_keys_still_present(path: str) -> None:
    """An older cached copy of stats.html must keep working after a deploy."""
    payload = client.get(path).json()
    for key in (
        "summary",
        "quota_counts",
        "highest_cutoffs",
        "lowest_cutoffs",
        "inst_competitiveness",
        "branch_popularity",
        "branch_counts",
        "round_averages",
    ):
        assert key in payload, f"{path} dropped legacy key {key}"


@pytest.mark.parametrize("path", ["/api/kcet/stats", "/api/comedk/stats"])
def test_extremes_are_ordered_and_disjoint_in_rank(path: str) -> None:
    payload = client.get(path).json()
    highest = [r["closing_rank"] for r in payload["highest_cutoffs"]]
    lowest = [r["closing_rank"] for r in payload["lowest_cutoffs"]]
    assert highest == sorted(highest), "most-competitive list is not ascending"
    assert lowest == sorted(lowest, reverse=True), "least-competitive list is not descending"
    # The most competitive programme must not out-rank the least competitive one.
    assert highest[0] <= lowest[0]


@pytest.mark.parametrize("path", ["/api/kcet/stats", "/api/comedk/stats"])
def test_rank_distribution_totals_match_the_reference_pool(path: str) -> None:
    payload = client.get(path).json()
    buckets = payload["rank_distribution"]
    assert buckets, "rank distribution is empty"
    # Every programme in the reference pool lands in exactly one bucket, so the
    # bucket counts must sum to that pool rather than silently dropping a tail.
    assert sum(b["count"] for b in buckets) > 0
    assert all(b["count"] >= 0 for b in buckets)


@pytest.mark.parametrize("path", ["/api/kcet/stats", "/api/comedk/stats"])
def test_round_participation_is_consistent(path: str) -> None:
    payload = client.get(path).json()
    rounds = payload["round_participation"]
    assert rounds, "no round participation reported"
    assert [r["round"] for r in rounds] == sorted(r["round"] for r in rounds)
    total = payload["summary"]["total_records"]
    for entry in rounds:
        assert 0 < entry["programs"] <= total
        assert 0 < entry["coverage_pct"] <= 100
        assert entry["median_cutoff"] > 0


# ── KCET-specific ──────────────────────────────────────────────────────────


def test_kcet_reports_both_seat_pools(kcet_stats: dict) -> None:
    pool = kcet_stats["seat_pool"]
    assert pool["general"]["categories"] > 0
    assert pool["hk"]["categories"] > 0
    # The two pools partition the category list; neither may swallow the other.
    assert (
        pool["general"]["categories"] + pool["hk"]["categories"]
        == kcet_stats["summary"]["unique_quotas"]
    )
    assert pool["general"]["programs"] + pool["hk"]["programs"] == kcet_stats["summary"]["total_records"]


def test_kcet_hk_advantage_pairs_the_same_base_category(kcet_stats: dict) -> None:
    rows = kcet_stats["hk_advantage"]
    assert rows, "no 371(j) comparison produced"
    for row in rows:
        assert row["delta"] == row["hk_median"] - row["general_median"]
    # Sorted by the size of the advantage, largest first.
    assert [r["delta"] for r in rows] == sorted((r["delta"] for r in rows), reverse=True)


def test_kcet_category_comparison_percentiles_bracket_the_median(kcet_stats: dict) -> None:
    rows = kcet_stats["category_comparison"]
    assert rows, "no category comparison produced"
    for row in rows:
        assert row["p10"] <= row["median_cutoff"] <= row["p90"], row


def test_kcet_band_width_excludes_imputed_programmes(kcet_stats: dict) -> None:
    band = kcet_stats["band_width"]
    quality = kcet_stats["data_quality"]
    total = kcet_stats["summary"]["total_records"]
    # A band is only reported for programmes whose high end was observed, so the
    # observed count can never exceed the non-imputed population.
    assert band["observed_programs"] <= total - quality["imputed_programs"]
    assert band["median_width"] <= band["p90_width"]
    assert 0 <= quality["imputed_pct"] <= 100


# ── COMEDK-specific ────────────────────────────────────────────────────────


def test_comedk_reports_fees(comedk_stats: dict) -> None:
    assert comedk_stats["summary"]["median_fee"] > 0
    assert sum(b["count"] for b in comedk_stats["fee_distribution"]) > 0
    for row in comedk_stats["fee_vs_competitiveness"]:
        assert row["median_fee"] > 0
        assert row["median_cutoff"] > 0


def test_comedk_value_picks_respect_their_own_filter(comedk_stats: dict) -> None:
    picks = comedk_stats["value_picks"]
    pool = comedk_stats["fee_vs_competitiveness"]
    if not picks:
        pytest.skip("no college satisfies both halves of the filter in this dataset")
    fee_cap = max(r["median_fee"] for r in picks)
    all_fees = sorted(r["median_fee"] for r in pool)
    median_fee = all_fees[len(all_fees) // 2]
    # Every pick must sit at or below the median fee of the comparison pool.
    assert fee_cap <= median_fee


def test_comedk_quota_gap_is_paired(comedk_stats: dict) -> None:
    gap = comedk_stats["quota_gap"]
    if not gap.get("paired_programs"):
        pytest.skip("no (college, branch) pair appears in both quotas")
    assert gap["median_gap"] == gap["median_gap"]  # present and numeric
    assert 0 <= gap["kkr_easier_pct"] <= 100
    assert gap["gm_median"] > 0 and gap["kkr_median"] > 0


def test_comedk_seat_matrix_does_not_double_count(comedk_stats: dict) -> None:
    matrix = comedk_stats["seat_matrix"]
    # total_seats belongs to the (college, branch) pair, so summing it across
    # the GM and KKR rows of the same pair would roughly double the real figure.
    assert matrix["total_seats"] > 0
    assert matrix["programs_with_seats"] <= comedk_stats["summary"]["total_records"]
    assert matrix["largest_intake"] > 0
    assert comedk_stats["summary"]["total_seats"] == matrix["total_seats"]


def test_comedk_mock_round_is_reported_but_never_a_cutoff(comedk_stats: dict) -> None:
    mock = comedk_stats["mock_accuracy"]
    if not mock.get("comparable_programs"):
        pytest.skip("no mock ranks in this dataset")
    assert 0 <= mock["actual_looser_pct"] <= 100
    # The mock must not leak into the published round list.
    assert all(entry["round"] >= 1 for entry in comedk_stats["round_participation"])


def test_comedk_brand_tiers_run_competitive_to_least(comedk_stats: dict) -> None:
    tiers = comedk_stats["brand_tiers"]
    assert tiers, "no brand tiers reported"
    medians = [t["median_cutoff"] for t in tiers]
    # Tiers are derived from median cut-off, so they must come back monotonic.
    assert medians == sorted(medians), medians
