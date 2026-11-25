"""Offline deterministic pool failover policy simulator.

Evaluation-only state machine. No sockets, miners, credentials, pool connections,
share submissions, wallet access, or blockchain interaction.
"""
from __future__ import annotations

import math
from typing import Any


def simulate_pool_failover(
    events: list[dict[str, Any]],
    *,
    primary: str = "primary",
    secondary: str = "secondary",
    max_latency_ms: float = 1500.0,
    failure_samples: int = 2,
    recovery_samples: int = 3,
    switch_cooldown_s: float = 30.0,
    failback_cooldown_s: float = 120.0,
) -> dict[str, Any]:
    """Simulate health hysteresis, failover, sticky recovery and stale-share rejection.

    Event formats:
      {"type":"sample","at_s":1,"pool":"primary","connected":true,
       "authorized":true,"latency_ms":80,"job_id":"p-job"}
      {"type":"share","pool":"primary","job_id":"p-job","share_id":"s1"}
    """
    if not isinstance(events, list) or len(events) > 10000:
        raise ValueError("events must be a list with at most 10000 entries")
    if not isinstance(primary, str) or not primary or not isinstance(secondary, str) or not secondary or primary == secondary:
        raise ValueError("primary and secondary must be distinct non-empty names")
    if isinstance(max_latency_ms, bool) or not isinstance(max_latency_ms, (int, float)) or not math.isfinite(max_latency_ms) or max_latency_ms <= 0:
        raise ValueError("max_latency_ms must be positive and finite")
    if isinstance(failure_samples, bool) or not isinstance(failure_samples, int) or failure_samples < 1:
        raise ValueError("failure_samples must be a positive integer")
    if isinstance(recovery_samples, bool) or not isinstance(recovery_samples, int) or recovery_samples < 1:
        raise ValueError("recovery_samples must be a positive integer")
    for name, value in (("switch_cooldown_s", switch_cooldown_s), ("failback_cooldown_s", failback_cooldown_s)):
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
            raise ValueError(f"{name} must be finite and non-negative")

    pools = (primary, secondary)
    health = {
        name: {"connected": False, "authorized": False, "latency_ms": None,
               "job_id": None, "healthy": False, "bad_streak": 0,
               "good_streak": 0, "last_sample_s": None}
        for name in pools
    }
    active_pool: str | None = primary
    now_s = 0.0
    last_switch_s = -math.inf
    last_failover_s: float | None = None
    switches = 0
    failovers = 0
    failbacks = 0
    accepted = rejected = stale = duplicates = malformed = 0
    warnings: list[dict[str, Any]] = []
    history: list[dict[str, Any]] = []
    seen_shares: set[tuple[str, str, str]] = set()

    def is_healthy(row: dict[str, Any]) -> bool:
        latency = row["latency_ms"]
        return bool(row["connected"] and row["authorized"] and latency is not None and latency <= max_latency_ms)

    def switch(target: str | None, reason: str) -> None:
        nonlocal active_pool, switches, failovers, failbacks, last_switch_s, last_failover_s
        if target == active_pool:
            return
        previous = active_pool
        active_pool = target
        switches += 1
        last_switch_s = now_s
        if previous == primary and target == secondary:
            failovers += 1
            last_failover_s = now_s
        elif previous == secondary and target == primary:
            failbacks += 1
        history.append({"at_s": now_s, "from": previous, "to": target, "reason": reason})

    for index, event in enumerate(events):
        if not isinstance(event, dict) or not isinstance(event.get("type"), str):
            malformed += 1
            warnings.append({"index": index, "code": "malformed_event"})
            continue
        kind = event["type"]
        if kind == "sample":
            pool = event.get("pool")
            at_s = event.get("at_s")
            if pool not in pools or isinstance(at_s, bool) or not isinstance(at_s, (int, float)) or not math.isfinite(at_s) or at_s < now_s:
                malformed += 1
                warnings.append({"index": index, "code": "invalid_sample_identity_or_time"})
                continue
            connected, authorized = event.get("connected"), event.get("authorized")
            latency = event.get("latency_ms")
            if not isinstance(connected, bool) or not isinstance(authorized, bool) or isinstance(latency, bool) or not isinstance(latency, (int, float)) or not math.isfinite(latency) or latency < 0:
                malformed += 1
                warnings.append({"index": index, "code": "invalid_sample_metrics"})
                continue
            now_s = float(at_s)
            row = health[pool]
            row.update({"connected": connected, "authorized": authorized,
                        "latency_ms": float(latency), "last_sample_s": now_s})
            if "job_id" in event:
                job = event["job_id"]
                if job is not None and (not isinstance(job, str) or not job or len(job) > 128):
                    malformed += 1
                    warnings.append({"index": index, "code": "invalid_job_id"})
                    continue
                row["job_id"] = job
            good = is_healthy(row)
            row["healthy"] = good
            row["good_streak"] = row["good_streak"] + 1 if good else 0
            row["bad_streak"] = 0 if good else row["bad_streak"] + 1

            if active_pool == pool and not good and row["bad_streak"] >= failure_samples:
                other = secondary if pool == primary else primary
                if health[other]["healthy"] and now_s - last_switch_s >= switch_cooldown_s:
                    switch(other, "active_pool_unhealthy_backup_healthy")
                elif not health[other]["healthy"]:
                    switch(None, "both_pools_unhealthy")
            elif active_pool is None:
                candidates = [p for p in pools if health[p]["healthy"] and health[p]["good_streak"] >= 1]
                if candidates and now_s - last_switch_s >= switch_cooldown_s:
                    # Preserve configured priority when both are available.
                    switch(primary if primary in candidates else candidates[0], "pool_recovered")
            elif active_pool == secondary and pool == primary and good:
                cooldown_elapsed = last_failover_s is not None and now_s - last_failover_s >= failback_cooldown_s
                if row["good_streak"] >= recovery_samples and cooldown_elapsed and now_s - last_switch_s >= switch_cooldown_s:
                    switch(primary, "primary_recovered_sticky_failback")
            elif active_pool == secondary and pool == secondary and not good and row["bad_streak"] >= failure_samples:
                if health[primary]["healthy"] and now_s - last_switch_s >= switch_cooldown_s:
                    switch(primary, "secondary_unhealthy_primary_healthy")
                elif not health[primary]["healthy"]:
                    switch(None, "both_pools_unhealthy")

        elif kind == "share":
            pool, job_id, share_id = event.get("pool"), event.get("job_id"), event.get("share_id")
            if pool not in pools or not isinstance(job_id, str) or not isinstance(share_id, str) or not share_id:
                malformed += 1
                rejected += 1
                warnings.append({"index": index, "code": "malformed_share"})
            elif pool != active_pool:
                stale += 1
                rejected += 1
                warnings.append({"index": index, "code": "share_from_inactive_pool"})
            elif job_id != health[pool]["job_id"]:
                stale += 1
                rejected += 1
                warnings.append({"index": index, "code": "share_for_invalidated_job"})
            elif not health[pool]["healthy"]:
                rejected += 1
                warnings.append({"index": index, "code": "share_while_pool_unhealthy"})
            elif (pool, job_id, share_id) in seen_shares:
                duplicates += 1
                rejected += 1
                warnings.append({"index": index, "code": "duplicate_share"})
            else:
                seen_shares.add((pool, job_id, share_id))
                accepted += 1
        else:
            malformed += 1
            warnings.append({"index": index, "code": "unknown_event_type"})

    return {
        "active_pool": active_pool,
        "pool_health": health,
        "switches": switches,
        "failovers": failovers,
        "failbacks": failbacks,
        "accepted": accepted,
        "rejected": rejected,
        "stale": stale,
        "duplicates": duplicates,
        "malformed_events": malformed,
        "warnings": warnings,
        "switch_history": history,
        "no_oscillation_guarantee": "thresholds and cooldown constrain switching; results depend on supplied samples",
        "execution": "simulation_only",
        "network_accessed": False,
        "miner_started": False,
        "share_submitted": False,
        "wallet_accessed": False,
        "blockchain_accessed": False,
    }


def standard_failover_scenarios() -> dict[str, list[dict[str, Any]]]:
    """Deterministic scenarios for failover, recovery, flapping and share safety."""
    return {
        "primary_failure_secondary_healthy": [
            {"type":"sample","at_s":1,"pool":"secondary","connected":True,"authorized":True,"latency_ms":80,"job_id":"s1"},
            {"type":"sample","at_s":2,"pool":"primary","connected":False,"authorized":False,"latency_ms":0},
            {"type":"sample","at_s":3,"pool":"primary","connected":False,"authorized":False,"latency_ms":0},
        ],
        "both_pools_down": [
            {"type":"sample","at_s":1,"pool":"primary","connected":False,"authorized":False,"latency_ms":0},
            {"type":"sample","at_s":2,"pool":"primary","connected":False,"authorized":False,"latency_ms":0},
            {"type":"sample","at_s":3,"pool":"secondary","connected":False,"authorized":False,"latency_ms":0},
            {"type":"sample","at_s":4,"pool":"secondary","connected":False,"authorized":False,"latency_ms":0},
        ],
        "primary_recovery_sticky_failback": [
            {"type":"sample","at_s":1,"pool":"secondary","connected":True,"authorized":True,"latency_ms":80,"job_id":"s1"},
            {"type":"sample","at_s":2,"pool":"primary","connected":False,"authorized":False,"latency_ms":0},
            {"type":"sample","at_s":3,"pool":"primary","connected":False,"authorized":False,"latency_ms":0},
            {"type":"sample","at_s":130,"pool":"primary","connected":True,"authorized":True,"latency_ms":60,"job_id":"p2"},
            {"type":"sample","at_s":131,"pool":"primary","connected":True,"authorized":True,"latency_ms":60},
            {"type":"sample","at_s":132,"pool":"primary","connected":True,"authorized":True,"latency_ms":60},
        ],
        "latency_degradation": [
            {"type":"sample","at_s":1,"pool":"secondary","connected":True,"authorized":True,"latency_ms":90,"job_id":"s1"},
            {"type":"sample","at_s":2,"pool":"primary","connected":True,"authorized":True,"latency_ms":2000,"job_id":"p1"},
            {"type":"sample","at_s":3,"pool":"primary","connected":True,"authorized":True,"latency_ms":2100},
        ],
        "share_safety_after_failover": [
            {"type":"sample","at_s":1,"pool":"secondary","connected":True,"authorized":True,"latency_ms":70,"job_id":"s1"},
            {"type":"sample","at_s":2,"pool":"primary","connected":False,"authorized":False,"latency_ms":0,"job_id":"p1"},
            {"type":"sample","at_s":3,"pool":"primary","connected":False,"authorized":False,"latency_ms":0},
            {"type":"share","pool":"primary","job_id":"p1","share_id":"old"},
            {"type":"share","pool":"secondary","job_id":"s1","share_id":"new"},
            {"type":"share","pool":"secondary","job_id":"s1","share_id":"new"},
        ],
        "repeated_flapping": [
            {"type":"sample","at_s":1,"pool":"secondary","connected":True,"authorized":True,"latency_ms":90,"job_id":"s1"},
            {"type":"sample","at_s":2,"pool":"primary","connected":False,"authorized":False,"latency_ms":0},
            {"type":"sample","at_s":3,"pool":"primary","connected":False,"authorized":False,"latency_ms":0},
            {"type":"sample","at_s":4,"pool":"primary","connected":True,"authorized":True,"latency_ms":50,"job_id":"p2"},
            {"type":"sample","at_s":5,"pool":"primary","connected":False,"authorized":False,"latency_ms":0},
            {"type":"sample","at_s":6,"pool":"primary","connected":False,"authorized":False,"latency_ms":0},
        ],
    }
