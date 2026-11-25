"""Small, dependency-free statistical primitives for exploratory analysis."""
from __future__ import annotations

import math
from collections import Counter
from typing import Iterable


def _gammaincc(a: float, x: float) -> float:
    """Regularized upper incomplete gamma Q(a,x), Numerical-Recipes style."""
    if a <= 0 or x < 0:
        raise ValueError("Require a > 0 and x >= 0")
    if x == 0:
        return 1.0
    eps, tiny, max_iter = 3e-14, 1e-300, 10_000
    gln = math.lgamma(a)
    if x < a + 1.0:
        ap = a
        term = 1.0 / a
        total = term
        for _ in range(max_iter):
            ap += 1.0
            term *= x / ap
            total += term
            if abs(term) < abs(total) * eps:
                break
        p = total * math.exp(-x + a * math.log(x) - gln)
        return min(1.0, max(0.0, 1.0 - p))

    b = x + 1.0 - a
    c = 1.0 / tiny
    d = 1.0 / max(b, tiny)
    h = d
    for i in range(1, max_iter + 1):
        an = -i * (i - a)
        b += 2.0
        d = an * d + b
        if abs(d) < tiny:
            d = tiny
        c = b + an / c
        if abs(c) < tiny:
            c = tiny
        d = 1.0 / d
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < eps:
            break
    return min(1.0, max(0.0, math.exp(-x + a * math.log(x) - gln) * h))


def chi_square_upper_tail(statistic: float, degrees_freedom: int) -> float:
    if degrees_freedom <= 0:
        raise ValueError("degrees_freedom must be positive")
    return _gammaincc(degrees_freedom / 2.0, statistic / 2.0)


def nonce_nibble_tests(nonces: Iterable[int]) -> list[dict[str, float | int]]:
    """Test each of the 8 displayed hex-nibble positions against uniform 0..F."""
    values = list(nonces)
    n = len(values)
    if n == 0:
        return []
    results = []
    for position in range(8):
        counts = Counter(f"{nonce:08x}"[position] for nonce in values)
        chi2 = sum((counts.get(f"{v:x}", 0) - n / 16.0) ** 2 / (n / 16.0)
                   for v in range(16))
        p = chi_square_upper_tail(chi2, 15)
        results.append({
            "hex_position_from_left": position,
            "sample_size": n,
            "chi_square": chi2,
            "degrees_freedom": 15,
            "p_value_uncorrected": p,
            "p_value_bonferroni_8_tests": min(1.0, p * 8),
            "counts_hex_0_to_f": [counts.get(f"{v:x}", 0) for v in range(16)],
        })
    return results


def ones_probability_upto(target: int, bit_from_msb: int, width: int = 256) -> float:
    """P(bit=1) for an integer sampled uniformly from [0,target]."""
    if target < 0 or target >= 1 << width:
        raise ValueError("target outside bit width")
    bit_from_lsb = width - 1 - bit_from_msb
    half_period = 1 << bit_from_lsb
    period = half_period << 1
    count_values = target + 1
    full_cycles, remainder = divmod(count_values, period)
    ones = full_cycles * half_period + max(0, remainder - half_period)
    return ones / count_values


def conditioned_hash_bit_tests(rows: Iterable[dict]) -> list[dict[str, float | int]]:
    """Test hash-bit marginals against the correct uniform-[0,target] null.

    This explicitly accounts for proof-of-work truncation. It is not a test of
    bit independence, and each block contributes one correlated 256-bit sample.
    """
    data = [r for r in rows if r.get("pow_valid") is True and r.get("target_hex")]
    if not data:
        return []
    result = []
    for bit_pos in range(256):
        observed = 0
        expected = 0.0
        variance = 0.0
        for row in data:
            target = int(row["target_hex"], 16)
            probability = ones_probability_upto(target, bit_pos)
            hash_int = int(row["block_hash"], 16)
            bit = (hash_int >> (255 - bit_pos)) & 1
            observed += bit
            expected += probability
            variance += probability * (1.0 - probability)
        if variance == 0:
            z = 0.0 if observed == expected else math.copysign(float("inf"), observed - expected)
            p = 0.0 if math.isinf(z) else 1.0
        else:
            z = (observed - expected) / math.sqrt(variance)
            p = math.erfc(abs(z) / math.sqrt(2.0))
        result.append({
            "bit_position_from_msb": bit_pos,
            "sample_size": len(data),
            "observed_ones": observed,
            "expected_ones_under_target_conditioning": expected,
            "z_score_marginal_only": z,
            "p_value_uncorrected_normal_approx": p,
            "p_value_bonferroni_256_tests": min(1.0, p * 256),
        })
    return result
