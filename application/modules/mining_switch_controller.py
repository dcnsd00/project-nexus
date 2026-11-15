"""Evidence-gated mining coin/configuration switching.

Candidate discovery is external to this policy. Only a source-verified candidate
with compatible miner/pool/hardware and repeated profitable measurements can
reach the supervisor. Automatic switching is opt-in and rate-limited.
"""
from __future__ import annotations

import json
import math
import os
import threading
import time
from pathlib import Path

from modules.data_paths import data_path
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


_STATE_PATH = Path(os.getenv("NEXUS_MINING_SWITCH_STATE", str(data_path("mining", "switch_state.json")))).expanduser().resolve()
_STATE_LOCK = threading.RLock()


def load_switch_state(engine: str) -> dict[str, Any]:
    if engine not in {"cpu", "gpu"}:
        raise ValueError("engine must be cpu or gpu")
    with _STATE_LOCK:
        try:
            raw = json.loads(_STATE_PATH.read_text(encoding="utf-8"))
            row = raw.get(engine, {}) if isinstance(raw, dict) else {}
            return row if isinstance(row, dict) else {}
        except (OSError, ValueError, AttributeError):
            return {}


def record_active_configuration(engine: str, coin: str | None, algorithm: str | None,
                                now: float | None = None) -> dict[str, Any]:
    if engine not in {"cpu", "gpu"}:
        raise ValueError("engine must be cpu or gpu")
    now = time.time() if now is None else float(now)
    with _STATE_LOCK:
        try:
            raw = json.loads(_STATE_PATH.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                raw = {}
        except (OSError, ValueError):
            raw = {}
        previous = raw.get(engine, {}) if isinstance(raw.get(engine), dict) else {}
        same = previous.get("current_coin") == coin and previous.get("current_algorithm") == algorithm
        if not same:
            previous["current_started_unix"] = now
        previous["current_coin"] = coin
        previous["current_algorithm"] = algorithm
        raw[engine] = previous
        _STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        temporary = _STATE_PATH.with_suffix(_STATE_PATH.suffix + ".tmp")
        temporary.write_text(json.dumps(raw, ensure_ascii=False, sort_keys=True), encoding="utf-8")
        os.replace(temporary, _STATE_PATH)
        return dict(previous)


def record_successful_switch(engine: str, coin: str | None, algorithm: str | None,
                             now: float | None = None) -> dict[str, Any]:
    if engine not in {"cpu", "gpu"}:
        raise ValueError("engine must be cpu or gpu")
    now = time.time() if now is None else float(now)
    with _STATE_LOCK:
        try:
            raw = json.loads(_STATE_PATH.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                raw = {}
        except (OSError, ValueError):
            raw = {}
        previous = raw.get(engine, {}) if isinstance(raw.get(engine), dict) else {}
        history = [float(x) for x in previous.get("switches_last_24h", [])
                   if now - float(x) < 86400]
        history.append(now)
        previous.update({"current_coin": coin, "current_algorithm": algorithm,
                         "current_started_unix": now, "last_switch_unix": now,
                         "switches_last_24h": history})
        raw[engine] = previous
        _STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        temporary = _STATE_PATH.with_suffix(_STATE_PATH.suffix + ".tmp")
        temporary.write_text(json.dumps(raw, ensure_ascii=False, sort_keys=True), encoding="utf-8")
        os.replace(temporary, _STATE_PATH)
        return dict(previous)


def _effective_policy(policy: dict[str, Any] | None) -> dict[str, Any]:
    supplied = policy or {}
    cfg = {**DEFAULT_POLICY, **supplied}
    # User configuration may tighten safety, never weaken the hard minimums.
    cfg["minimum_net_improvement_percent"] = max(15.0, float(cfg["minimum_net_improvement_percent"]))
    cfg["minimum_windows"] = max(3, int(cfg["minimum_windows"]))
    cfg["minimum_window_seconds"] = max(300, float(cfg["minimum_window_seconds"]))
    cfg["maximum_source_age_seconds"] = min(900, float(cfg["maximum_source_age_seconds"]))
    cfg["minimum_dwell_seconds"] = max(900, float(cfg["minimum_dwell_seconds"]))
    cfg["cooldown_seconds"] = max(1800, float(cfg["cooldown_seconds"]))
    cfg["maximum_switches_per_24h"] = min(3, int(cfg["maximum_switches_per_24h"]))
    cfg["maximum_reject_ratio"] = min(0.03, float(cfg["maximum_reject_ratio"]))
    cfg["maximum_temperature_c"] = min(85.0, float(cfg["maximum_temperature_c"]))
    cfg["auto_switch_enabled"] = bool(supplied.get("auto_switch_enabled", False))
    return cfg


def evaluate_candidate(current: dict[str, Any], candidate: dict[str, Any],
                       state: dict[str, Any] | None = None,
                       policy: dict[str, Any] | None = None,
                       now: float | None = None) -> dict[str, Any]:
    """Evaluate a discovered coin/config; never starts or stops a miner."""
    cfg = _effective_policy(policy)
    state = state or {}
    now = time.time() if now is None else float(now)
    reasons: list[str] = []

    if candidate.get("evidence_status") != "verified":
        reasons.append("candidate_evidence_not_verified")
    if candidate.get("source_checked_unix") is None:
        reasons.append("missing_source_timestamp")
    else:
        try:
            source_time = float(candidate["source_checked_unix"])
            if not math.isfinite(source_time) or source_time > now + 60:
                reasons.append("invalid_source_timestamp")
            elif now - source_time > cfg["maximum_source_age_seconds"]:
                reasons.append("candidate_source_stale")
        except (TypeError, ValueError):
            reasons.append("invalid_source_timestamp")
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
        if not all(math.isfinite(x) for x in (duration, net, reject, temp)) or duration <= 0 or net < 0 or not 0 <= reject <= 1 or temp < -20 or temp > 150:
            reasons.append("invalid_measurement_window")
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
