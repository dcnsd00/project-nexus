"""Evidence-gated mining coin/configuration switching.

Candidate discovery is external to this policy. Only a source-verified candidate
with compatible miner/pool/hardware and repeated profitable measurements can
reach the supervisor. Automatic switching is opt-in and rate-limited.
"""
from __future__ import annotations

import time
from typing import Any


DEFAULT_POLICY = {
    "auto_switch_enabled": False,
    "minimum_net_improvement_percent": 15.0,
    "minimum_windows": 3,
    "minimum_window_seconds": 300,
    "maximum_source_age_seconds": 900,
    "minimum_dwell_seconds": 900,
    "cooldown_seconds": 1800,
    "maximum_switches_per_24h": 3,
    "maximum_reject_ratio": 0.03,
    "maximum_temperature_c": 85.0,
}


def evaluate_candidate(current: dict[str, Any], candidate: dict[str, Any],
                       state: dict[str, Any] | None = None,
                       policy: dict[str, Any] | None = None,
                       now: float | None = None) -> dict[str, Any]:
    """Evaluate a discovered coin/config; never starts or stops a miner."""
    cfg = {**DEFAULT_POLICY, **(policy or {})}
    state = state or {}
    now = time.time() if now is None else float(now)
    reasons: list[str] = []

    if candidate.get("evidence_status") != "verified":
        reasons.append("candidate_evidence_not_verified")
    if candidate.get("source_checked_unix") is None:
        reasons.append("missing_source_timestamp")
    elif now - float(candidate["source_checked_unix"]) > cfg["maximum_source_age_seconds"]:
        reasons.append("candidate_source_stale")
    if candidate.get("hardware_compatible") is not True:
        reasons.append("hardware_compatibility_unconfirmed")
    if candidate.get("miner_supported") is not True:
        reasons.append("miner_support_unconfirmed")
    if candidate.get("pool_reachable") is not True or candidate.get("pool_authorized") is not True:
        reasons.append("pool_not_verified_and_authorized")

    windows = candidate.get("windows")
    if not isinstance(windows, list) or len(windows) < int(cfg["minimum_windows"]):
        reasons.append("insufficient_measurement_windows")
        windows = []
    values = []
    for window in windows:
        try:
            duration = float(window["duration_seconds"])
            net = float(window["net_profit_ron_day"])
            reject = float(window["reject_ratio"])
            temp = float(window["temperature_c"])
        except (KeyError, TypeError, ValueError):
            reasons.append("incomplete_measurement_window")
            continue
        if duration < float(cfg["minimum_window_seconds"]):
            reasons.append("measurement_window_too_short")
        if reject > float(cfg["maximum_reject_ratio"]):
            reasons.append("reject_ratio_exceeds_limit")
        if temp >= float(cfg["maximum_temperature_c"]):
            reasons.append("temperature_limit")
        if not window.get("shares_accepted"):
            reasons.append("no_accepted_shares")
        values.append(net)

    if len(values) < int(cfg["minimum_windows"]):
        reasons.append("insufficient_valid_windows")
    current_net = current.get("net_profit_ron_day")
    if not isinstance(current_net, (int, float)) or current_net <= 0:
        reasons.append("current_profitability_not_measured")
        improvement = None
    elif len(values) >= int(cfg["minimum_windows"]):
        baseline = float(current_net)
        candidate_median = sorted(values)[len(values) // 2]
        improvement = (candidate_median / baseline - 1.0) * 100.0
        if improvement < float(cfg["minimum_net_improvement_percent"]):
            reasons.append("net_improvement_below_threshold")
    else:
        improvement = None

    last_switch = float(state.get("last_switch_unix", 0) or 0)
    if last_switch and now - last_switch < float(cfg["cooldown_seconds"]):
        reasons.append("switch_cooldown_active")
    current_started = float(state.get("current_started_unix", now) or now)
    if now - current_started < float(cfg["minimum_dwell_seconds"]):
        reasons.append("minimum_dwell_not_reached")
    recent_switches = [float(x) for x in state.get("switches_last_24h", []) if now - float(x) < 86400]
    if len(recent_switches) >= int(cfg["maximum_switches_per_24h"]):
        reasons.append("daily_switch_limit_reached")
    if current.get("coin") == candidate.get("coin") and current.get("algorithm") == candidate.get("algorithm"):
        reasons.append("candidate_matches_current_configuration")

    eligible = not reasons
    if eligible and not cfg["auto_switch_enabled"]:
        reasons.append("automatic_switch_disabled")
    return {
        "eligible": eligible,
        "automatic_switch_enabled": bool(cfg["auto_switch_enabled"]),
        "should_switch": eligible and bool(cfg["auto_switch_enabled"]),
        "candidate_coin": candidate.get("coin"),
        "candidate_algorithm": candidate.get("algorithm"),
        "net_improvement_percent": round(improvement, 3) if improvement is not None else None,
        "valid_windows": len(values),
        "reasons": reasons,
        "policy": cfg,
        "action": "switch" if eligible and cfg["auto_switch_enabled"] else "hold",
    }


def switch_if_approved(supervisor: Any, engine: str, current: dict[str, Any],
                       candidate: dict[str, Any], state: dict[str, Any] | None = None,
                       policy: dict[str, Any] | None = None,
                       now: float | None = None) -> dict[str, Any]:
    """Run the real supervisor reconfiguration only after the evidence gate passes."""
    decision = evaluate_candidate(current, candidate, state, policy, now)
    if not decision["should_switch"]:
        return {"decision": decision, "executed": False, "result": None}
    request = candidate.get("worker_request")
    if not isinstance(request, dict):
        decision["should_switch"] = False
        decision["action"] = "hold"
        decision["reasons"].append("worker_request_missing")
        return {"decision": decision, "executed": False, "result": None}
    result = supervisor.switch_engine(engine, request)
    return {"decision": decision, "executed": bool(result.get("switched")),
            "result": result}
