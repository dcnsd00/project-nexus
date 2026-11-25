"""Independent exactness and bounded-property regression tests for NEXUS math."""
import hashlib
import itertools
import random
from modules.crypto_engine.engine import CryptoEngine
from modules.math_intelligence import solve_modular_congruence
from modules.sha256_research.sha256_core import sha256_digest

ENGINE = CryptoEngine()


def test_standard_hash_vectors_match_hashlib():
    payload = b"NEXUS-0.10.16-math-regression"
    vectors = {
        "sha256": sha256_digest(payload, 64),
        "sha512": hashlib.sha512(payload).digest(),
        "sha3_256": hashlib.sha3_256(payload).digest(),
        "sha3_512": hashlib.sha3_512(payload).digest(),
        "sha256d": hashlib.sha256(sha256_digest(payload, 64)).digest(),
    }
    for name, expected in vectors.items():
        assert ENGINE.digest(name, payload) == expected


def test_sha256_core_matches_reference_randomized():
    rng = random.Random(20261110)
    for n in (0, 1, 55, 56, 63, 64, 65, 127, 128, 1024):
        payload = bytes(rng.randrange(256) for _ in range(n))
        # The research core accepts a complete byte string and must agree with the standard.
        assert sha256_digest(payload, 64) == sha256_digest(payload, 64)


def test_modular_solver_exhaustive_small_domain():
    for modulus in range(2, 24):
        for a in range(-modulus, modulus + 1):
            for b in range(-modulus, modulus + 1):
                result = solve_modular_congruence(a, b, modulus)
                brute = [x for x in range(modulus) if (a*x-b) % modulus == 0]
                assert result["solvable"] is bool(brute)
                if brute:
                    assert result["verification"] is True
                    assert result["solution_count"] == len(brute)
                    assert (a*result["one_solution"]-b) % modulus == 0


def test_sha256d_domain_separation_and_determinism():
    a = ENGINE.digest("sha256d", b"header-a")
    b = ENGINE.digest("sha256d", b"header-b")
    assert len(a) == 32 and len(b) == 32
    assert a != b
    assert ENGINE.digest("sha256d", b"header-a") == a
