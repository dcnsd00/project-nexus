import pytest

from mining.pool_failover_simulator import (
    simulate_pool_failover,
    standard_failover_scenarios,
)


def test_primary_failure_fails_over_only_after_consecutive_bad_samples():
    events = standard_failover_scenarios()["primary_failure_secondary_healthy"]
    result = simulate_pool_failover(events)
    assert result["active_pool"] == "secondary"
    assert result["failovers"] == 1
    assert result["switch_history"][-1]["reason"] == "active_pool_unhealthy_backup_healthy"


def test_single_bad_sample_does_not_trigger_failover():
    events = [
        {"type":"sample","at_s":1,"pool":"secondary","connected":True,"authorized":True,"latency_ms":80,"job_id":"s1"},
        {"type":"sample","at_s":2,"pool":"primary","connected":False,"authorized":False,"latency_ms":0},
    ]
    result = simulate_pool_failover(events)
    assert result["active_pool"] == "primary"
    assert result["switches"] == 0


def test_both_pools_down_enters_no_active_pool_state():
    result = simulate_pool_failover(standard_failover_scenarios()["both_pools_down"])
    assert result["active_pool"] is None
    assert result["switch_history"][-1]["reason"] == "both_pools_unhealthy"


def test_primary_recovery_requires_streak_and_sticky_failback_cooldown():
    result = simulate_pool_failover(standard_failover_scenarios()["primary_recovery_sticky_failback"])
    assert result["active_pool"] == "primary"
    assert result["failovers"] == 1
    assert result["failbacks"] == 1
    assert result["switch_history"][-1]["reason"] == "primary_recovered_sticky_failback"


def test_high_latency_is_unhealthy_after_required_samples():
    result = simulate_pool_failover(standard_failover_scenarios()["latency_degradation"])
    assert result["active_pool"] == "secondary"
    assert result["failovers"] == 1


def test_old_pool_shares_rejected_and_duplicate_share_not_counted_twice():
    result = simulate_pool_failover(standard_failover_scenarios()["share_safety_after_failover"])
    assert result["active_pool"] == "secondary"
    assert result["accepted"] == 1
    assert result["stale"] == 1
    assert result["duplicates"] == 1
    assert result["rejected"] == 2


def test_flapping_does_not_cause_rapid_failback():
    result = simulate_pool_failover(standard_failover_scenarios()["repeated_flapping"])
    assert result["active_pool"] == "secondary"
    assert result["switches"] == 1
    assert result["failbacks"] == 0


@pytest.mark.parametrize("kwargs", [
    {"max_latency_ms": float("inf")},
    {"failure_samples": 0},
    {"recovery_samples": True},
    {"switch_cooldown_s": -1},
    {"failback_cooldown_s": float("nan")},
    {"primary": "same", "secondary": "same"},
])
def test_invalid_policy_configuration_rejected(kwargs):
    with pytest.raises(ValueError):
        simulate_pool_failover([], **kwargs)


def test_invalid_or_non_monotonic_samples_are_contained():
    events = [
        {"type":"sample","at_s":2,"pool":"primary","connected":True,"authorized":True,"latency_ms":20},
        {"type":"sample","at_s":1,"pool":"primary","connected":True,"authorized":True,"latency_ms":20},
        {"type":"sample","at_s":3,"pool":"primary","connected":True,"authorized":True,"latency_ms":float("inf")},
    ]
    result = simulate_pool_failover(events)
    assert result["malformed_events"] == 2
    assert result["active_pool"] == "primary"


def test_simulation_is_deterministic_and_never_executes_external_actions():
    events = standard_failover_scenarios()["share_safety_after_failover"]
    first = simulate_pool_failover(events)
    second = simulate_pool_failover(events)
    assert first == second
    assert first["execution"] == "simulation_only"
    assert first["network_accessed"] is False
    assert first["miner_started"] is False
    assert first["share_submitted"] is False
    assert first["wallet_accessed"] is False
    assert first["blockchain_accessed"] is False


def test_rejects_oversized_event_stream():
    with pytest.raises(ValueError):
        simulate_pool_failover([{}] * 10001)
