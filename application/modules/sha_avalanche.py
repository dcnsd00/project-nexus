"""Exact full-digest avalanche experiments for standard hash functions.

This is a statistical diagnostic, not a cryptanalytic shortcut or PoW hashrate test.
All digests are produced by Python hashlib and are compared bit-for-bit.
"""
from __future__ import annotations

import hashlib
import math
import random
import time
from typing import Callable

ALGORITHMS: dict[str, tuple[Callable, int]] = {
    "sha256": (hashlib.sha256, 256),
    "sha512": (hashlib.sha512, 512),
    "sha3_256": (hashlib.sha3_256, 256),
    "sha3_512": (hashlib.sha3_512, 512),
    "blake2b_256": (lambda data: hashlib.blake2b(data, digest_size=32), 256),
}
MAX_SAMPLES = 4096
MAX_PAYLOAD_BYTES = 4096


def _hamming_bytes(a: bytes, b: bytes) -> int:
    return sum((x ^ y).bit_count() for x, y in zip(a, b))


def avalanche_experiment(algorithm: str = "sha512", samples: int = 256,
                         payload_bytes: int = 64, seed: int = 20261109) -> dict:
    if algorithm not in ALGORITHMS:
        raise ValueError(f"Algoritm necunoscut. Alege: {', '.join(ALGORITHMS)}")
    if isinstance(samples, bool) or not isinstance(samples, int) or not 16 <= samples <= MAX_SAMPLES:
        raise ValueError(f"samples trebuie să fie între 16 și {MAX_SAMPLES}.")
    if isinstance(payload_bytes, bool) or not isinstance(payload_bytes, int) or not 1 <= payload_bytes <= MAX_PAYLOAD_BYTES:
        raise ValueError(f"payload_bytes trebuie să fie între 1 și {MAX_PAYLOAD_BYTES}.")
    if isinstance(seed, bool) or not isinstance(seed, int) or not 0 <= seed < 2**64:
        raise ValueError("seed trebuie să fie unsigned pe 64 de biți.")

    digest_fn, digest_bits = ALGORITHMS[algorithm]
    rng = random.Random(seed)
    distances: list[int] = []
    t0 = time.perf_counter()
    for _ in range(samples):
        message = bytearray(rng.getrandbits(8) for _ in range(payload_bytes))
        changed = bytearray(message)
        bit_index = rng.randrange(payload_bytes * 8)
        changed[bit_index // 8] ^= 1 << (bit_index % 8)
        base_digest = digest_fn(bytes(message)).digest()
        changed_digest = digest_fn(bytes(changed)).digest()
        if len(base_digest) * 8 != digest_bits or len(changed_digest) != len(base_digest):
            raise RuntimeError("Lungimea digestului nu corespunde algoritmului declarat.")
        distances.append(_hamming_bytes(base_digest, changed_digest))

    mean = sum(distances) / samples
    variance = sum((x - mean) ** 2 for x in distances) / (samples - 1)
    expected = digest_bits / 2
    # Under an ideal random permutation, Hamming distance is Binomial(digest_bits, 1/2).
    standard_error = math.sqrt(digest_bits / (4 * samples))
    z_score = (mean - expected) / standard_error if standard_error else 0.0
    passed = abs(z_score) <= 3.0
    return {
        "kind": "full_standard_hash_avalanche",
        "algorithm": algorithm,
        "standard_digest_bits": digest_bits,
        "samples": samples,
        "payload_bytes": payload_bytes,
        "seed": seed,
        "mean_changed_output_bits": mean,
        "expected_mean_for_ideal_random_mapping": expected,
        "sample_stddev": math.sqrt(variance),
        "z_score_vs_ideal_mean": z_score,
        "within_three_standard_errors": passed,
        "min_distance": min(distances),
        "max_distance": max(distances),
        "elapsed_seconds": time.perf_counter() - t0,
        "interpretation": (
            "Media este compatibilă cu reperul ideal de 50% în acest eșantion; testul nu demonstrează securitatea criptografică."
            if passed else
            "Media este în afara pragului statistic orientativ de 3 erori standard; repetă cu alt seed și mai multe probe înainte de concluzii."
        ),
        "not_a_pow_benchmark": True,
        "consensus_compatible": True,
    }


def avalanche_catalog() -> dict:
    return {
        "purpose": "Statistical avalanche diagnostics over complete standard digests using hashlib.",
        "algorithms": {name: bits for name, (_, bits) in ALGORITHMS.items()},
        "max_samples": MAX_SAMPLES,
        "max_payload_bytes": MAX_PAYLOAD_BYTES,
        "limits": [
            "A near-50% output-bit change rate is a necessary diagnostic, not a proof of cryptographic security.",
            "This measures CPU library behavior, not GPU mining hashrate.",
            "No reduced-round variant is substituted for a standard hash function.",
        ],
    }
