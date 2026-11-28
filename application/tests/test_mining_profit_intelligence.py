import pytest

from modules.mining_profit_intelligence import (
    ProfitIntelligenceError,
    rank_candidates,
    score_candidate,
)


def candidate(candidate_id="pool-a", **overrides):
    row = {
        "candidate_id": candidate_id,
        "reward_coin_per_day": 0.01,
        "stable_price_ron": 200000.0,
        "live_price_ron": 210000.0,
        "power_w": 120.0,
        "electricity_price_ron_kwh": 1.5,
        "pool_accuracy": 0.99,
        "accepted_shares": 990,
        "rejected_shares": 10,
        "measured_hashrate_hs": 100.0,
        "benchmark_hashrate_hs": 100.0,
        "source_age_seconds": 60.0,
    }
    row.update(overrides)
    return row


def test_profit_score_blends_stable_and_live_price_and_subtracts_energy():
    result = score_candidate(candidate())
    assert result["eligible"] is True
    assert result["price_model"]["weighted_price_ron"] == 205000.0
    assert result["electricity_cost_ron_day"] == pytest.approx(4.32)
    assert result["net_profit_ron_day"] < result["gross_revenue_ron_day"]
    assert result["currency"] == "RON"
    assert result["automatic_action"] is False


def test_missing_or_stale_evidence_is_not_eligible():
    missing = candidate()
    del missing["pool_accuracy"]
    stale = candidate("stale", source_age_seconds=901)
    assert score_candidate(missing)["eligible"] is False
    assert "missing_pool_accuracy" in score_candidate(missing)["reasons"]
    assert score_candidate(stale)["eligible"] is False
    assert "source_data_stale" in score_candidate(stale)["reasons"]


def test_invalid_units_and_ranges_fail_closed():
    with pytest.raises(ProfitIntelligenceError, match="pool_accuracy_out_of_range"):
        score_candidate(candidate(pool_accuracy=1.5))
    with pytest.raises(ProfitIntelligenceError, match="power_w_must_be_finite_nonnegative"):
        score_candidate(candidate(power_w=-120))
    with pytest.raises(ProfitIntelligenceError, match="live_price_weight_out_of_range"):
        score_candidate(candidate(), {"live_price_weight": 1.5})


def test_switch_hysteresis_returns_recommendation_never_executes():
    incumbent = candidate("incumbent", reward_coin_per_day=0.010)
    challenger = candidate(
        "challenger",
        reward_coin_per_day=0.012,
        power_w=120,
    )
    result = rank_candidates(
        [incumbent, challenger],
        current_candidate_id="incumbent",
    )
    assert result["recommendation"] == "manual_review_switch_candidate"
    assert result["challenger_candidate_id"] == "challenger"
    assert result["automatic_switching"] is False


def test_small_uplift_below_hysteresis_holds_current_candidate():
    incumbent = candidate("incumbent")
    challenger = candidate("challenger", reward_coin_per_day=0.0101)
    result = rank_candidates(
        [incumbent, challenger],
        current_candidate_id="incumbent",
        policy={"switch_hysteresis_percent": 3.0},
    )
    assert result["recommendation"] == "hold_current"
    assert result["challenger_candidate_id"] is None
    assert result["automatic_switching"] is False


def test_no_verified_incumbent_does_not_authorize_automatic_switch():
    result = rank_candidates([candidate()], current_candidate_id="missing")
    assert result["recommendation"] == "manual_review_no_verified_incumbent"
    assert result["automatic_switching"] is False


def test_profit_intelligence_api_is_recommendation_only():
    from fastapi.testclient import TestClient
    from nexus_master import app

    payload = {
        "candidates": [{
            "candidate_id": "pool-a",
            "reward_coin_per_day": 0.01,
            "stable_price_ron": 200000,
            "live_price_ron": 210000,
            "power_w": 120,
            "electricity_price_ron_kwh": 1.5,
            "pool_accuracy": 0.99,
            "accepted_shares": 990,
            "rejected_shares": 10,
            "measured_hashrate_hs": 100,
            "benchmark_hashrate_hs": 100,
            "source_age_seconds": 60,
        }],
        "current_candidate_id": "pool-a",
    }
    with TestClient(app, base_url="http://127.0.0.1",
                    client=("127.0.0.1", 51300)) as client:
        status = client.get("/api/mining/profit-intelligence/status")
        ranked = client.post("/api/mining/profit-intelligence/rank", json=payload)
    assert status.status_code == 200
    assert status.json()["automatic_switching"] is False
    assert ranked.status_code == 200
    assert ranked.json()["recommendation"] == "hold_current"
    assert ranked.json()["automatic_switching"] is False
