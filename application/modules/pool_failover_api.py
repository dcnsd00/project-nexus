"""Read-only API for deterministic offline pool failover simulations."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from mining.pool_failover_simulator import simulate_pool_failover, standard_failover_scenarios

router = APIRouter(tags=["mining-pool-failover"])


class PoolFailoverSimulationRequest(BaseModel):
    events: list[dict] = Field(max_length=10000)
    primary: str = Field(default="primary", min_length=1, max_length=80)
    secondary: str = Field(default="secondary", min_length=1, max_length=80)
    max_latency_ms: float = Field(default=1500.0, gt=0, le=60000)
    failure_samples: int = Field(default=2, ge=1, le=100)
    recovery_samples: int = Field(default=3, ge=1, le=100)
    switch_cooldown_s: float = Field(default=30.0, ge=0, le=86400)
    failback_cooldown_s: float = Field(default=120.0, ge=0, le=604800)


@router.get("/api/mining/pool-failover/scenarios")
def pool_failover_scenarios():
    scenarios = standard_failover_scenarios()
    return {
        "scenario_names": sorted(scenarios),
        "scenario_count": len(scenarios),
        "execution": "simulation_only",
        "network_accessed": False,
        "miner_started": False,
    }


@router.post("/api/mining/pool-failover/simulate")
def pool_failover_simulate(req: PoolFailoverSimulationRequest):
    try:
        result = simulate_pool_failover(
            req.events,
            primary=req.primary,
            secondary=req.secondary,
            max_latency_ms=req.max_latency_ms,
            failure_samples=req.failure_samples,
            recovery_samples=req.recovery_samples,
            switch_cooldown_s=req.switch_cooldown_s,
            failback_cooldown_s=req.failback_cooldown_s,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return result
