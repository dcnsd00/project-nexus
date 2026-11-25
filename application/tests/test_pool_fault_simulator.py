import pytest

from mining.pool_fault_simulator import simulate_pool_conditions, standard_fault_scenarios


def test_variable_difficulty_and_valid_share():
    result = simulate_pool_conditions(standard_fault_scenarios()["variable_difficulty"])
    assert result["difficulty"] == 128.0
    assert result["difficulty_changes"] == 2
    assert result["accepted"] == 1
    assert result["pool_health"] == "healthy_simulated"


def test_disconnect_invalidates_authorization_and_reconnect_requires_auth():
    result = simulate_pool_conditions(standard_fault_scenarios()["pool_disconnect_mid_job"])
    assert result["disconnects"] == 1
    assert result["reconnects"] == 1
    assert result["rejected"] == 1
    assert result["accepted"] == 1


def test_tip_change_invalidates_old_job_and_accepts_new_job():
    result = simulate_pool_conditions(standard_fault_scenarios()["chain_reorg_or_tip_change"])
    assert result["stale"] == 1
    assert result["accepted"] == 1
    assert any(x["code"] == "chain_tip_changed_jobs_invalidated" for x in result["warnings"])


def test_high_latency_is_reported_without_fabricating_rejection():
    result = simulate_pool_conditions(standard_fault_scenarios()["high_latency"])
    assert result["latency_ms"] == 2500
    assert result["accepted"] == 1
    assert any(x["code"] == "high_latency" for x in result["warnings"])


def test_duplicate_and_stale_shares_are_separated():
    result = simulate_pool_conditions(standard_fault_scenarios()["duplicate_and_stale_shares"])
    assert result["duplicates"] == 1
    assert result["stale"] == 1
    assert result["accepted"] == 1
    assert result["rejected"] == 2


def test_malformed_and_extreme_inputs_are_contained():
    result = simulate_pool_conditions(standard_fault_scenarios()["malformed_extreme_inputs"])
    assert result["malformed_events"] == 6
    assert result["accepted"] == 0
    assert result["pool_health"] == "degraded"


def test_rejects_oversized_event_stream_and_invalid_threshold():
    with pytest.raises(ValueError):
        simulate_pool_conditions([{}] * 10001)
    with pytest.raises(ValueError):
        simulate_pool_conditions([], max_latency_ms=float("nan"))


def test_simulation_is_deterministic_and_explicitly_offline():
    scenarios = standard_fault_scenarios()
    for events in scenarios.values():
        a = simulate_pool_conditions(events)
        b = simulate_pool_conditions(events)
        assert a == b
        assert "no network" in a["scope"]
