from modules.mining_switch_controller import evaluate_candidate


def _candidate(now=10_000):
    return {
        "coin": "COIN-B", "algorithm": "Algo-B",
        "evidence_status": "verified", "source_checked_unix": now - 30,
        "hardware_compatible": True, "miner_supported": True,
        "pool_reachable": True, "pool_authorized": True,
        "windows": [
            {"duration_seconds": 600, "net_profit_ron_day": 14.0,
             "reject_ratio": 0.01, "temperature_c": 65, "shares_accepted": True},
            {"duration_seconds": 600, "net_profit_ron_day": 15.0,
             "reject_ratio": 0.01, "temperature_c": 66, "shares_accepted": True},
            {"duration_seconds": 600, "net_profit_ron_day": 16.0,
             "reject_ratio": 0.02, "temperature_c": 67, "shares_accepted": True},
        ],
    }


def _current():
    return {"coin": "COIN-A", "algorithm": "Algo-A", "net_profit_ron_day": 10.0}


def _state(now=10_000):
    return {"current_started_unix": now - 3600, "last_switch_unix": now - 3600,
            "switches_last_24h": []}


def test_candidate_needs_multiple_verified_profitable_windows():
    result = evaluate_candidate(_current(), _candidate(), _state(), {}, now=10_000)
    assert result["eligible"] is True
    assert result["should_switch"] is False
    assert "automatic_switch_disabled" in result["reasons"]


def test_automatic_switch_requires_opt_in_and_sufficient_profit_uplift():
    result = evaluate_candidate(_current(), _candidate(), _state(),
                                {"auto_switch_enabled": True}, now=10_000)
    assert result["eligible"] is True
    assert result["should_switch"] is True
    assert result["net_improvement_percent"] >= 15


def test_stale_unverified_or_incompatible_candidate_is_rejected():
    candidate = _candidate()
    candidate["source_checked_unix"] = 1
    candidate["hardware_compatible"] = False
    result = evaluate_candidate(_current(), candidate, _state(),
                                {"auto_switch_enabled": True}, now=10_000)
    assert result["should_switch"] is False
    assert "candidate_source_stale" in result["reasons"]
    assert "hardware_compatibility_unconfirmed" in result["reasons"]


def test_switch_cooldown_and_daily_limit_prevent_repeated_switching():
    candidate = _candidate()
    state = {"current_started_unix": 1, "last_switch_unix": 9_900,
             "switches_last_24h": [9_000, 9_100, 9_200]}
    result = evaluate_candidate(_current(), candidate, state,
                                {"auto_switch_enabled": True}, now=10_000)
    assert result["should_switch"] is False
    assert "switch_cooldown_active" in result["reasons"]
    assert "daily_switch_limit_reached" in result["reasons"]


def test_hot_or_high_reject_candidate_is_rejected():
    candidate = _candidate()
    candidate["windows"][0]["temperature_c"] = 90
    candidate["windows"][1]["reject_ratio"] = 0.2
    result = evaluate_candidate(_current(), candidate, _state(),
                                {"auto_switch_enabled": True}, now=10_000)
    assert result["should_switch"] is False
    assert "temperature_limit" in result["reasons"]
    assert "reject_ratio_exceeds_limit" in result["reasons"]


def test_policy_cannot_be_weakened_by_request():
    candidate = _candidate()
    result = evaluate_candidate(
        _current(), candidate, _state(),
        {"auto_switch_enabled": True, "minimum_net_improvement_percent": 0,
         "minimum_windows": 1, "minimum_window_seconds": 1,
         "maximum_source_age_seconds": 999999, "cooldown_seconds": 0,
         "minimum_dwell_seconds": 0, "maximum_switches_per_24h": 100,
         "maximum_reject_ratio": 1.0, "maximum_temperature_c": 150},
        now=10_000,
    )
    assert result["policy"]["minimum_net_improvement_percent"] == 15
    assert result["policy"]["minimum_windows"] == 3
    assert result["policy"]["minimum_window_seconds"] == 300
    assert result["policy"]["maximum_source_age_seconds"] == 900
    assert result["policy"]["cooldown_seconds"] == 1800
    assert result["policy"]["maximum_switches_per_24h"] == 3
    assert result["policy"]["maximum_reject_ratio"] == 0.03
    assert result["policy"]["maximum_temperature_c"] == 85


def test_future_timestamp_and_non_finite_measurements_are_rejected():
    candidate = _candidate(now=10_000)
    candidate["source_checked_unix"] = 20_000
    candidate["windows"][0]["net_profit_ron_day"] = float("nan")
    result = evaluate_candidate(_current(), candidate, _state(), {"auto_switch_enabled": True}, now=10_000)
    assert result["should_switch"] is False
    assert "invalid_source_timestamp" in result["reasons"]
    assert "invalid_measurement_window" in result["reasons"]
