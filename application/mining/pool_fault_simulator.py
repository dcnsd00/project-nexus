"""Deterministic pool/network fault simulator.

Pure local state-machine tests for pool instability and extreme conditions.
No sockets, public pools, miner processes, wallets, or blockchain writes.
"""
from __future__ import annotations

import math
from typing import Any


def simulate_pool_conditions(events: list[dict[str, Any]], *, max_latency_ms: float = 1500.0) -> dict[str, Any]:
    if not isinstance(events, list) or len(events) > 10000:
        raise ValueError("events must be a list with at most 10000 entries")
    if not isinstance(max_latency_ms, (int, float)) or not math.isfinite(max_latency_ms) or max_latency_ms <= 0:
        raise ValueError("max_latency_ms must be a positive finite number")

    state = {
        "connected": True, "authorized": True, "difficulty": None,
        "active_job": None, "tip_epoch": 0, "latency_ms": None,
        "accepted": 0, "rejected": 0, "stale": 0, "duplicates": 0,
        "disconnects": 0, "reconnects": 0, "difficulty_changes": 0,
        "jobs_received": 0, "clean_job_resets": 0, "malformed_events": 0,
        "warnings": [], "events_processed": 0,
    }
    seen_shares: set[tuple[str, str]] = set()

    for index, event in enumerate(events):
        if not isinstance(event, dict) or not isinstance(event.get("type"), str):
            state["malformed_events"] += 1
            state["warnings"].append({"index": index, "code": "malformed_event"})
            continue
        kind = event["type"]
        state["events_processed"] += 1

        if kind == "difficulty":
            value = event.get("value")
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
                state["malformed_events"] += 1
                state["warnings"].append({"index": index, "code": "invalid_difficulty"})
            else:
                if state["difficulty"] is not None and value != state["difficulty"]:
                    state["difficulty_changes"] += 1
                state["difficulty"] = float(value)

        elif kind == "job":
            job_id = event.get("job_id")
            clean = event.get("clean_jobs", False)
            if not isinstance(job_id, str) or not job_id or len(job_id) > 128 or not isinstance(clean, bool):
                state["malformed_events"] += 1
                state["warnings"].append({"index": index, "code": "invalid_job"})
                continue
            if clean:
                state["active_job"] = None
                state["clean_job_resets"] += 1
            state["active_job"] = job_id
            state["jobs_received"] += 1

        elif kind == "latency":
            value = event.get("ms")
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
                state["malformed_events"] += 1
                state["warnings"].append({"index": index, "code": "invalid_latency"})
            else:
                state["latency_ms"] = float(value)
                if value > max_latency_ms:
                    state["warnings"].append({"index": index, "code": "high_latency"})

        elif kind == "disconnect":
            if state["connected"]:
                state["disconnects"] += 1
            state["connected"] = False
            state["authorized"] = False

        elif kind == "reconnect":
            state["connected"] = True
            state["authorized"] = bool(event.get("authorized", False))
            if state["authorized"]:
                state["reconnects"] += 1

        elif kind == "tip_change":
            state["tip_epoch"] += 1
            state["active_job"] = None
            state["warnings"].append({"index": index, "code": "chain_tip_changed_jobs_invalidated"})

        elif kind == "share":
            job_id, share_id = event.get("job_id"), event.get("share_id")
            if not state["connected"] or not state["authorized"]:
                state["rejected"] += 1
                state["warnings"].append({"index": index, "code": "share_while_disconnected_or_unauthorized"})
            elif not isinstance(job_id, str) or job_id != state["active_job"]:
                state["stale"] += 1
                state["rejected"] += 1
                state["warnings"].append({"index": index, "code": "stale_job_share"})
            elif not isinstance(share_id, str) or not share_id:
                state["malformed_events"] += 1
                state["rejected"] += 1
                state["warnings"].append({"index": index, "code": "invalid_share_id"})
            elif (job_id, share_id) in seen_shares:
                state["duplicates"] += 1
                state["rejected"] += 1
                state["warnings"].append({"index": index, "code": "duplicate_share"})
            else:
                seen_shares.add((job_id, share_id))
                state["accepted"] += 1

        else:
            state["malformed_events"] += 1
            state["warnings"].append({"index": index, "code": "unknown_event_type"})

    total = state["accepted"] + state["rejected"]
    state["reject_rate"] = (state["rejected"] / total) if total else None
    state["pool_health"] = (
        "disconnected" if not state["connected"] else
        "unauthorized" if not state["authorized"] else
        "degraded" if state["warnings"] or state["reject_rate"] not in (None, 0.0) else
        "healthy_simulated"
    )
    state["scope"] = "deterministic local simulation; no network, miner, wallet, or blockchain interaction"
    return state


def standard_fault_scenarios() -> dict[str, list[dict[str, Any]]]:
    """Named failure scenarios used by regression tests and future CI matrices."""
    return {
        "variable_difficulty": [
            {"type": "difficulty", "value": 1},
            {"type": "difficulty", "value": 0.25},
            {"type": "difficulty", "value": 128},
            {"type": "job", "job_id": "vardiff-1", "clean_jobs": True},
            {"type": "share", "job_id": "vardiff-1", "share_id": "s1"},
        ],
        "pool_disconnect_mid_job": [
            {"type": "job", "job_id": "job-a", "clean_jobs": True},
            {"type": "disconnect"},
            {"type": "share", "job_id": "job-a", "share_id": "s1"},
            {"type": "reconnect", "authorized": True},
            {"type": "job", "job_id": "job-b", "clean_jobs": True},
            {"type": "share", "job_id": "job-b", "share_id": "s2"},
        ],
        "chain_reorg_or_tip_change": [
            {"type": "job", "job_id": "tip-a", "clean_jobs": True},
            {"type": "tip_change"},
            {"type": "share", "job_id": "tip-a", "share_id": "old"},
            {"type": "job", "job_id": "tip-b", "clean_jobs": True},
            {"type": "share", "job_id": "tip-b", "share_id": "new"},
        ],
        "high_latency": [
            {"type": "latency", "ms": 40},
            {"type": "latency", "ms": 2500},
            {"type": "job", "job_id": "slow-pool", "clean_jobs": True},
            {"type": "share", "job_id": "slow-pool", "share_id": "s1"},
        ],
        "duplicate_and_stale_shares": [
            {"type": "job", "job_id": "job-1", "clean_jobs": True},
            {"type": "share", "job_id": "job-1", "share_id": "same"},
            {"type": "share", "job_id": "job-1", "share_id": "same"},
            {"type": "job", "job_id": "job-2", "clean_jobs": True},
            {"type": "share", "job_id": "job-1", "share_id": "late"},
        ],
        "malformed_extreme_inputs": [
            {"type": "difficulty", "value": 0},
            {"type": "difficulty", "value": -1},
            {"type": "difficulty", "value": float("inf")},
            {"type": "latency", "ms": -10},
            {"type": "job", "job_id": "", "clean_jobs": True},
            {"type": "unknown"},
        ],
    }
