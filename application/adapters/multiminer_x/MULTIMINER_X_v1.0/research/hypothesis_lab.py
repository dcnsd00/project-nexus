"""Sandbox for unconventional hypotheses. Models are exploratory only and
cannot be plugged into consensus mining without correctness proofs and tests.
"""
from __future__ import annotations
import math, random, statistics

def run_null_hypothesis_experiment(samples: int = 100_000, seed: int = 20261107) -> dict:
    if not 100 <= samples <= 2_000_000: raise ValueError("samples must be 100..2,000,000")
    rng = random.Random(seed)
    # Null model: uniform independent 32-bit words. Test high-bit frequency and
    # serial lag-1 correlation; this is a diagnostic, not a cryptographic proof.
    xs = [rng.getrandbits(32) for _ in range(samples)]
    high = sum(x >> 31 for x in xs) / samples
    mean = statistics.fmean(xs)
    var = statistics.pvariance(xs)
    cov = sum((xs[i]-mean)*(xs[i+1]-mean) for i in range(samples-1))/(samples-1)
    corr = cov / var if var else 0.0
    se = math.sqrt(0.25 / samples)
    return {"model":"uniform-iid-32bit-null", "samples":samples, "seed":seed,
            "high_bit_frequency":high, "high_bit_z_score":(high-.5)/se,
            "lag1_correlation":corr,
            "interpretation":"Synthetic PRNG null-model diagnostic only; not evidence of SHA-256 weakness or a mining shortcut."}
