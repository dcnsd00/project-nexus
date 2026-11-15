"""Engineering estimates for laptop power/thermal limits; parameters must be measured."""
from __future__ import annotations
import math
import random


def joules_per_hash(power_watts: float, hashes_per_second: float) -> float:
    if power_watts < 0 or hashes_per_second <= 0:
        raise ValueError("Power must be >= 0 and hashrate > 0")
    return power_watts / hashes_per_second


def thermal_rc_temperature(ambient_c: float, power_watts: float,
                            thermal_resistance_c_per_w: float,
                            thermal_capacity_j_per_c: float,
                            elapsed_seconds: float) -> float:
    """First-order lumped RC model. Approximation, not a laptop sensor reading."""
    if thermal_resistance_c_per_w <= 0 or thermal_capacity_j_per_c <= 0:
        raise ValueError("Thermal resistance and capacity must be positive")
    if power_watts < 0 or elapsed_seconds < 0:
        raise ValueError("Power and elapsed time must be non-negative")
    tau = thermal_resistance_c_per_w * thermal_capacity_j_per_c
    steady_rise = power_watts * thermal_resistance_c_per_w
    return ambient_c + steady_rise * (1.0 - math.exp(-elapsed_seconds / tau))


def monte_carlo_thermal_risk(ambient_c: float, power_range_w: tuple[float, float],
                             rth_range: tuple[float, float], capacity_range: tuple[float, float],
                             elapsed_seconds: float, limit_c: float,
                             trials: int = 50_000, seed: int = 20261107) -> dict:
    """Sensitivity analysis for uncertain thermal parameters, not an exact prediction."""
    if trials < 1 or trials > 1_000_000:
        raise ValueError("trials must be 1..1,000,000")
    for lo, hi in (power_range_w, rth_range, capacity_range):
        if lo <= 0 or hi < lo:
            raise ValueError("Ranges must be positive and ordered")
    rng = random.Random(seed)
    over = 0
    temps = []
    for _ in range(trials):
        p = rng.uniform(*power_range_w)
        r = rng.uniform(*rth_range)
        c = rng.uniform(*capacity_range)
        t = thermal_rc_temperature(ambient_c, p, r, c, elapsed_seconds)
        temps.append(t)
        over += (t >= limit_c)
    temps.sort()
    return {"trials": trials, "probability_at_or_above_limit": over / trials,
            "p50_c": temps[trials // 2], "p95_c": temps[min(trials - 1, int(trials * .95))],
            "seed": seed,
            "note": "Rezultat sensibil la Rth/Cth; folosește temperaturile măsurate, nu trata modelul ca telemetrie."}
