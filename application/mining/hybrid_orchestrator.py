"""Hybrid CPU/GPU preflight planner.

This endpoint remains plan-only for backward compatibility. Actual process
execution is owned by ``HybridSupervisor`` through the /api/mining/hybrid/*
control endpoints; the legacy single-process controller remains untouched.
"""
from __future__ import annotations

from typing import Any, Callable

CPU_DEFAULTS = ("xmrig", "srbminer")
GPU_DEFAULTS = ("srbminer", "rigel", "bzminer", "lolminer", "gminer", "trex", "teamredminer")


def _pool_by_id(pools: list[dict], pool_id: str) -> dict:
    found = next((p for p in pools if p.get("id") == pool_id), None)
    if not found:
        raise ValueError(f"Pool necunoscut: {pool_id}")
    return found


def _choose_backend(pool: dict, device: str, inventory: dict, compatibility: Callable[[dict, str, str], dict]) -> dict:
    supported = CPU_DEFAULTS if device == "CPU" else GPU_DEFAULTS
    declared = str(pool.get("miner", "")).casefold()
    available = {m["id"]: m for m in inventory.get("miners", [])}
    candidates = []
    for miner_id in supported:
        item = available.get(miner_id)
        if not item or not item.get("available"):
            continue
        if miner_id not in declared and "compatible miner" not in declared and pool.get("id") != "custom":
            continue
        gate = compatibility(pool, miner_id, device)
        candidates.append({"miner_id": miner_id, "name": item.get("name"), "compatible": bool(gate.get("compatible")),
                           "reasons": gate.get("reasons", []), "binary": item.get("path")})
    valid = next((x for x in candidates if x["compatible"]), None)
    return {"selected": valid, "candidates": candidates,
            "ready": valid is not None,
            "status": "backend_ready" if valid else "no_compatible_backend"}


def build_hybrid_plan(*, pools: list[dict], inventory: dict, cpu_pool_id: str, gpu_pool_id: str,
                      compatibility: Callable[[dict, str, str], dict], hardware: dict | None = None) -> dict:
    """Build a source-backed CPU+GPU plan; does not start processes."""
    cpu_pool = _pool_by_id(pools, cpu_pool_id)
    gpu_pool = _pool_by_id(pools, gpu_pool_id)
    if cpu_pool.get("algorithm") != "RandomX":
        raise ValueError("Motorul CPU implicit este RandomX; selectează un pool RandomX pentru CPU.")
    if gpu_pool.get("algorithm") not in {"PearlHash", "PearlPow", "KawPoW", "Etchash", "KHeavyHash", "NexaPow", "Autolykos2", "FishHash", "Verthash", "XelisHashv3"}:
        raise ValueError("Algoritmul selectat nu este în lista algoritmilor GPU acceptați de orchestrator.")

    cpu = _choose_backend(cpu_pool, "CPU", inventory, compatibility)
    gpu = _choose_backend(gpu_pool, "GPU", inventory, compatibility)
    return {
        "architecture": "NEXUS hybrid CPU+GPU",
        "execution": "plan_only",
        "simultaneous_execution_enabled": False,
        "execution_blocker": "Acest endpoint este intenționat plan-only; pornește separat prin /api/mining/hybrid/start.",
        "supervisor_available": True,
        "engines": {
            "cpu": {"device": "CPU", "algorithm": cpu_pool["algorithm"], "coin": cpu_pool.get("coin"),
                    "pool_id": cpu_pool_id, "pool": cpu_pool.get("name"), **cpu},
            "gpu": {"device": "GPU", "algorithm": gpu_pool["algorithm"], "coin": gpu_pool.get("coin"),
                    "pool_id": gpu_pool_id, "pool": gpu_pool.get("name"), **gpu},
        },
        "hardware": hardware or {"available": False, "reason": "Telemetry hardware not supplied"},
        "ready_for_supervisor": bool(cpu["ready"] and gpu["ready"]),
        "switching_policy": {
            "scope": "GPU only; CPU RandomX remains independent",
            "automatic_switching": False,
            "requirements": ["backend installed", "pool algorithm match", "GPU VRAM/DAG margin", "thermal and power limits", "accepted-share validation"],
            "switch_trigger": "manual until measured profitability and stability policy is implemented",
        },
        "safety": ["No miner is launched by this endpoint.",
                   "No hashrate or profitability is inferred from algorithm labels.",
                   "A backend marked available must still pass live pool authorization and accepted-share checks."],
    }
