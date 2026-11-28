"""NEXUS Mining Profit Intelligence.

Independent, recommendation-only implementation of stable/live price blending,
pool-confidence weighting, electricity cost and switch hysteresis. This module
does not execute miners, change pools, or call external providers.
"""
from __future__ import annotations

import math
from typing import Any, Iterable

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/mining/profit-intelligence", tags=["Mining Profit Intelligence"])


DEFAULT_POLICY: dict[str, float] = {
    # RainbowMiner documents 10-minute live and one-week stable averages. The
    # blend weight is an explicit NEXUS policy input, not a copied RB default.
    "live_price_weight": 0.5,
    "switch_hysteresis_percent": 3.0,
    "maximum_source_age_seconds": 900.0,
    "fixed_cost_per_day_ron": 0.0,
}


class ProfitIntelligenceError(ValueError):
    """Raised when candidate economics contain invalid or ambiguous units."""


def _finite_nonnegative(value: Any, field: str) -> float:
    if isinstance(value, bool):
        raise ProfitIntelligenceError(f"{field}_must_be_numeric")
    try:
        result = float(value)
    except (TypeError, ValueError):
        raise ProfitIntelligenceError(f"{field}_must_be_numeric") from None
    if not math.isfinite(result) or result < 0:
        raise ProfitIntelligenceError(f"{field}_must_be_finite_nonnegative")
    return result


def _required_positive(value: Any, field: str) -> float:
    result = _finite_nonnegative(value, field)
    if result <= 0:
        raise ProfitIntelligenceError(f"{field}_must_be_positive")
    return result


def score_candidate(candidate: dict[str, Any],
                    policy: dict[str, float] | None = None) -> dict[str, Any]:
    """Score one candidate with explicitly unit-labelled RON/day inputs.

    Required inputs:
      reward_coin_per_day, stable_price_ron, live_price_ron, power_w,
      electricity_price_ron_kwh, pool_accuracy, accepted_shares,
      rejected_shares, measured_hashrate_hs, benchmark_hashrate_hs,
      source_age_seconds.

    The stable/live averages and pool accuracy must come from independently
    verified sources. Missing evidence makes the candidate ineligible.
    """
    if not isinstance(candidate, dict):
        raise ProfitIntelligenceError("candidate_must_be_object")
    cfg = {**DEFAULT_POLICY, **(policy or {})}
    weight = _finite_nonnegative(cfg["live_price_weight"], "live_price_weight")
    if weight > 1:
        raise ProfitIntelligenceError("live_price_weight_out_of_range")
    hysteresis = _finite_nonnegative(
        cfg["switch_hysteresis_percent"], "switch_hysteresis_percent"
    )
    max_age = _required_positive(
        cfg["maximum_source_age_seconds"], "maximum_source_age_seconds"
    )
    fixed_cost = _finite_nonnegative(
        cfg["fixed_cost_per_day_ron"], "fixed_cost_per_day_ron"
    )

    required = (
        "reward_coin_per_day", "stable_price_ron", "live_price_ron", "power_w",
        "electricity_price_ron_kwh", "pool_accuracy", "accepted_shares",
        "rejected_shares", "measured_hashrate_hs", "benchmark_hashrate_hs",
        "source_age_seconds",
    )
    missing = [name for name in required if name not in candidate or candidate[name] is None]
    if missing:
        return {
            "candidate_id": candidate.get("candidate_id"),
            "eligible": False,
            "classification": "unverified",
            "reasons": [f"missing_{name}" for name in missing],
            "automatic_action": False,
        }

    reward = _finite_nonnegative(candidate["reward_coin_per_day"], "reward_coin_per_day")
    stable_price = _required_positive(candidate["stable_price_ron"], "stable_price_ron")
    live_price = _required_positive(candidate["live_price_ron"], "live_price_ron")
    power_w = _finite_nonnegative(candidate["power_w"], "power_w")
    electricity = _finite_nonnegative(
        candidate["electricity_price_ron_kwh"], "electricity_price_ron_kwh"
    )
    accuracy = _finite_nonnegative(candidate["pool_accuracy"], "pool_accuracy")
    if accuracy > 1:
        raise ProfitIntelligenceError("pool_accuracy_out_of_range")
    accepted = _finite_nonnegative(candidate["accepted_shares"], "accepted_shares")
    rejected = _finite_nonnegative(candidate["rejected_shares"], "rejected_shares")
    measured_hashrate = _required_positive(
        candidate["measured_hashrate_hs"], "measured_hashrate_hs"
    )
    benchmark_hashrate = _required_positive(
        candidate["benchmark_hashrate_hs"], "benchmark_hashrate_hs"
    )
    age = _finite_nonnegative(candidate["source_age_seconds"], "source_age_seconds")

    reasons: list[str] = []
    total_shares = accepted + rejected
    if reward <= 0:
        reasons.append("no_reward_rate")
    if power_w <= 0:
        reasons.append("power_measurement_missing_or_zero")
    if total_shares <= 0:
        reasons.append("share_evidence_missing")
    if age > max_age:
        reasons.append("source_data_stale")

    reject_ratio = rejected / total_shares if total_shares > 0 else None
    hashrate_ratio = min(measured_hashrate / benchmark_hashrate, 1.0)
    weighted_price = stable_price * (1.0 - weight) + live_price * weight
    gross_before_confidence = reward * weighted_price
    confidence = accuracy * (1.0 - (reject_ratio or 0.0)) * hashrate_ratio
    freshness = max(0.0, 1.0 - (age / max_age))
    confidence *= freshness
    gross = gross_before_confidence * confidence
    electricity_cost = (power_w / 1000.0) * 24.0 * electricity
    total_cost = electricity_cost + fixed_cost
    net = gross - total_cost
    eligible = not reasons

    return {
        "candidate_id": candidate.get("candidate_id"),
        "eligible": eligible,
        "classification": "scored" if eligible else "research_only",
        "reasons": reasons,
        "currency": "RON",
        "period": "day",
        "price_model": {
            "stable_price_ron": stable_price,
            "live_price_ron": live_price,
            "live_price_weight": weight,
            "weighted_price_ron": weighted_price,
        },
        "confidence": round(confidence, 8),
        "pool_accuracy": accuracy,
        "reject_ratio": round(reject_ratio, 8) if reject_ratio is not None else None,
        "hashrate_ratio_capped": round(hashrate_ratio, 8),
        "source_age_seconds": age,
        "gross_revenue_before_confidence_ron_day": round(gross_before_confidence, 8),
        "gross_revenue_ron_day": round(gross, 8),
        "electricity_cost_ron_day": round(electricity_cost, 8),
        "fixed_cost_ron_day": fixed_cost,
        "net_profit_ron_day": round(net, 8),
        "automatic_action": False,
    }


def rank_candidates(candidates: Iterable[dict[str, Any]], *,
                    current_candidate_id: str | None = None,
                    policy: dict[str, float] | None = None) -> dict[str, Any]:
    """Rank eligible candidates and propose a hysteresis-gated change only."""
    cfg = {**DEFAULT_POLICY, **(policy or {})}
    scores = [score_candidate(row, cfg) for row in candidates]
    eligible = sorted(
        (row for row in scores if row.get("eligible")),
        key=lambda row: row["net_profit_ron_day"],
        reverse=True,
    )
    current = next(
        (row for row in eligible if row.get("candidate_id") == current_candidate_id),
        None,
    )
    best = eligible[0] if eligible else None
    recommendation = "insufficient_verified_candidates"
    improvement_percent = None
    challenger_id = None

    if current is not None and best is not None and best["candidate_id"] == current_candidate_id:
        recommendation = "hold_current"
    elif best is not None and current is None:
        recommendation = "manual_review_no_verified_incumbent"
        challenger_id = best["candidate_id"]
    elif best is not None and current is not None:
        delta = best["net_profit_ron_day"] - current["net_profit_ron_day"]
        denominator = max(abs(current["net_profit_ron_day"]), 0.01)
        improvement_percent = (delta / denominator) * 100.0
        challenger_id = best["candidate_id"] if best["candidate_id"] != current_candidate_id else None
        if (challenger_id is not None and delta > 0
                and improvement_percent >= float(cfg["switch_hysteresis_percent"])):
            recommendation = "manual_review_switch_candidate"
        else:
            recommendation = "hold_current"

    return {
        "candidates": scores,
        "eligible_count": len(eligible),
        "current_candidate_id": current_candidate_id,
        "best_candidate_id": best["candidate_id"] if best else None,
        "challenger_candidate_id": challenger_id,
        "improvement_percent": round(improvement_percent, 4) if improvement_percent is not None else None,
        "recommendation": recommendation,
        "automatic_switching": False,
        "policy": cfg,
        "evidence_note": (
            "Stable/live prices, reward rate, pool accuracy, share counts and hashrate "
            "must be independently measured. This engine does not fetch prices or control miners."
        ),
    }


class ProfitRankingRequest(BaseModel):
    candidates: list[dict[str, Any]] = Field(min_length=1, max_length=64)
    current_candidate_id: str | None = Field(default=None, max_length=128)
    live_price_weight: float = Field(default=0.5, ge=0.0, le=1.0)
    switch_hysteresis_percent: float = Field(default=3.0, ge=0.0, le=1000.0)
    maximum_source_age_seconds: float = Field(default=900.0, gt=0.0, le=86400.0)
    fixed_cost_per_day_ron: float = Field(default=0.0, ge=0.0, le=1_000_000.0)


@router.get("/status")
def profit_intelligence_status() -> dict[str, Any]:
    return {
        "state": "available",
        "mode": "recommendation_only",
        "currency": "RON",
        "period": "day",
        "automatic_switching": False,
        "external_data_fetch": False,
        "miner_control": False,
    }


@router.post("/rank")
def profit_intelligence_rank(request: ProfitRankingRequest) -> dict[str, Any]:
    policy = {
        "live_price_weight": request.live_price_weight,
        "switch_hysteresis_percent": request.switch_hysteresis_percent,
        "maximum_source_age_seconds": request.maximum_source_age_seconds,
        "fixed_cost_per_day_ron": request.fixed_cost_per_day_ron,
    }
    try:
        return rank_candidates(
            request.candidates,
            current_candidate_id=request.current_candidate_id,
            policy=policy,
        )
    except ProfitIntelligenceError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
