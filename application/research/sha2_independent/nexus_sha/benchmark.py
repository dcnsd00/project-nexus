"""
Benchmark exact pentru mining Bitcoin CPU (NEXUS).

Compara, pe ACELEASI date si cu rezultate IDENTICE (verificate contra hashlib):
1. baseline: double-SHA256 naiv pe antet complet, per nonce.
2. midstate: prima compresie precalculata (33% din compresii salvate).
3. midstate + precompute nonce-invariant: runde 0-2 si W[16..17] ale blocului 2
   al primei hash nu depind de nonce -> precalculate.
4. hashlib (referinta C, doar pentru context de viteza).

Masoara si costul real al 'early-exit' (compararea doar a primului cuvant):
aratam onest daca castigul e neglijabil (in Python este), pentru ca
hash-ul complet trebuie oricum calculat - nu exista iesire timpurie reala
inainte de finalul celor 64 runde (demonstrat in raport).

Fiecare varianta produce bit-cu-bit acelasi rezultat ca referinta.
"""

import time
import struct
import json
import random
import argparse
import hashlib

from .sha256_advanced import (sha256, double_sha256, MidstateMiner,
                              reference_double_sha256)


def make_test_header(seed=42):
    """Antet de 80 de octeti valid structural (nu trebuie sa fie un bloc real)."""
    rng = random.Random(seed)
    h = bytearray(80)
    h[0] = 0x01  # version
    # prev block hash (32 bytes) - aleator
    for i in range(4, 36):
        h[i] = rng.getrandbits(8)
    # merkle root (32 bytes) - aleator
    for i in range(36, 68):
        h[i] = rng.getrandbits(8)
    h[68:72] = struct.pack(">I", 0x12345678)  # time
    h[72:76] = struct.pack(">I", 0x1FFFFFFF)  # difficulty bits
    # nonce la bytes 76..79, setat de bench
    return bytes(h)


def bench_naive(header, nonces):
    out = []
    for n in nonces:
        h = bytearray(header)
        h[76:80] = struct.pack("<I", n)
        out.append(double_sha256(bytes(h)))
    return out


def bench_hashlib(header, nonces):
    out = []
    for n in nonces:
        h = bytearray(header)
        h[76:80] = struct.pack("<I", n)
        out.append(reference_double_sha256(bytes(h)))
    return out


def bench_midstate(header, nonces):
    m = MidstateMiner(header)
    return [m.hash_header(n) for n in nonces]


def bench_early_exit(header, nonces, target_word):
    """Midstate + comparare doar primul cuvant al hash-ului final.

    ATENTIE (masurat onest): hash-ul complet se calculeaza oricum;
    'early-exit' economiseste doar compararea celorlalte cuvinte.
    """
    m = MidstateMiner(header)
    hits = 0
    for n in nonces:
        if m.first_output_word(n) <= target_word:
            hits += 1
    return hits


def run(n_nonces=20000, seed=42, out_json=None):
    header = make_test_header(seed)
    rng = random.Random(seed)
    nonces = [rng.getrandbits(32) for _ in range(n_nonces)]
    res = {"config": {"n_nonces": n_nonces, "seed": seed}}
    # corectitudine pe un esantion (100 nonces) inainte de benchmark
    sample = nonces[:100]
    a = bench_naive(header, sample)
    b = bench_midstate(header, sample)
    c = bench_hashlib(header, sample)
    assert a == b == c, "EROARE: rezultate diferite intre variante!"
    res["correctness"] = {"checked_nonces": len(sample),
                          "all_variants_identical": True,
                          "verified_against": "hashlib (implementare independenta)"}
    # Use a monotonic high-resolution clock. Keep raw durations for rates and
    # ratios: rounded display values can become 0.000 on short Windows runs.
    durations = {}
    for name, fn in (("naive", bench_naive), ("midstate", bench_midstate)):
        t0 = time.perf_counter_ns()
        fn(header, nonces)
        dt = max((time.perf_counter_ns() - t0) / 1_000_000_000, 1e-9)
        durations[name] = dt
        res[name] = {"time_s": round(dt, 6),
                     "hashes_per_s": round(n_nonces / dt, 1)}
    t0 = time.perf_counter_ns()
    bench_hashlib(header, nonces)
    dt_hashlib = max((time.perf_counter_ns() - t0) / 1_000_000_000, 1e-9)
    res["hashlib_reference"] = {"time_s": round(dt_hashlib, 6),
                                "hashes_per_s": round(n_nonces / dt_hashlib, 1),
                                "note": "C, doar pentru context"}
    res["speedup_midstate_vs_naive"] = round(
        durations["naive"] / durations["midstate"], 3)
    # early-exit: masuram costul compararii
    m = MidstateMiner(header)
    t0 = time.perf_counter_ns()
    full = [m.hash_header(n) for n in nonces[:2000]]
    t_full = max((time.perf_counter_ns() - t0) / 1_000_000_000, 1e-9)
    t0 = time.perf_counter_ns()
    for n in nonces[:2000]:
        _ = m.first_output_word(n)
    t_first = max((time.perf_counter_ns() - t0) / 1_000_000_000, 1e-9)
    res["early_exit_check"] = {
        "time_full_hash_s": round(t_full, 6),
        "time_hash_plus_first_word_compare_s": round(t_first, 6),
        "overhead_ratio": round(t_first / t_full, 4),
        "conclusion": "hash-ul complet se calculeaza oricum; castigul "
                      "early-exit este doar compararea (neglijabil). Nu exista "
                      "iesire timpurie matematica inainte de runda 63.",
    }
    if out_json:
        with open(out_json, "w") as fh:
            json.dump(res, fh, indent=2)
    return res


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=20000)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()
    r = run(args.n, args.seed, args.out)
    print(json.dumps(r, indent=2))
