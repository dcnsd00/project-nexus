"""Auditable mining math helpers. These estimate network odds; they do not mine."""
from __future__ import annotations
import math
import random
from dataclasses import dataclass


def expected_blocks(user_hashrate: float, network_hashrate: float,
                    block_time_seconds: float, period_seconds: float) -> float:
    vals = (user_hashrate, network_hashrate, block_time_seconds, period_seconds)
    if any(not math.isfinite(x) or x < 0 for x in vals):
        raise ValueError("All inputs must be finite and non-negative")
    if network_hashrate <= 0 or block_time_seconds <= 0:
        raise ValueError("Network hashrate and block time must be positive")
    return (user_hashrate / network_hashrate) * (period_seconds / block_time_seconds)


def probability_at_least_one_block(user_hashrate: float, network_hashrate: float,
                                   block_time_seconds: float, period_seconds: float) -> float:
    lam = expected_blocks(user_hashrate, network_hashrate, block_time_seconds, period_seconds)
    return -math.expm1(-lam)


def expected_wait_seconds(user_hashrate: float, network_hashrate: float,
                          block_time_seconds: float) -> float:
    if user_hashrate <= 0 or network_hashrate <= 0 or block_time_seconds <= 0:
        return math.inf
    return block_time_seconds * network_hashrate / user_hashrate


def amdahl_speedup(parallel_fraction: float, workers: int) -> float:
    if not 0.0 <= parallel_fraction <= 1.0 or workers < 1:
        raise ValueError("parallel_fraction must be 0..1 and workers >= 1")
    return 1.0 / ((1.0 - parallel_fraction) + parallel_fraction / workers)


def monte_carlo_block_probability(user_hashrate: float, network_hashrate: float,
                                  block_time_seconds: float, period_seconds: float,
                                  trials: int = 100_000, seed: int = 20261107) -> dict:
    if trials < 1 or trials > 5_000_000:
        raise ValueError("trials must be between 1 and 5,000,000")
    p = probability_at_least_one_block(user_hashrate, network_hashrate,
                                       block_time_seconds, period_seconds)
    rng = random.Random(seed)
    hits = sum(1 for _ in range(trials) if rng.random() < p)
    estimate = hits / trials
    se = math.sqrt(max(estimate * (1.0 - estimate), 0.0) / trials)
    return {"trials": trials, "seed": seed, "successes": hits,
            "estimate": estimate, "standard_error": se,
            "analytic_probability": p,
            "note": "Monte Carlo verifică probabilitatea; nu accelerează PoW și nu prezice nonce-uri."}


def energy_kwh(power_watts: float, hours: float) -> float:
    if power_watts < 0 or hours < 0 or not math.isfinite(power_watts + hours):
        raise ValueError("Power and hours must be finite and non-negative")
    return power_watts * hours / 1000.0


def electricity_cost(power_watts: float, hours: float, price_per_kwh: float) -> float:
    if price_per_kwh < 0 or not math.isfinite(price_per_kwh):
        raise ValueError("Electricity price must be finite and non-negative")
    return energy_kwh(power_watts, hours) * price_per_kwh


def split_cpu_threads(logical_threads: int, target_percent: int = 50) -> int:
    if logical_threads < 1 or not 1 <= target_percent <= 100:
        raise ValueError("logical_threads >= 1 and target_percent 1..100 required")
    return max(1, min(logical_threads, round(logical_threads * target_percent / 100)))
