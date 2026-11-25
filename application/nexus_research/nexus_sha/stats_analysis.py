"""
Analiza statistica si spectrala pentru SHA-256 (NEXUS).

Experimente (toate cu rezultate masurate, nu presupuse):
1. Avalanche per runda: cati biti din starea interna se schimba in medie
   cand se flip-eaza 1 bit din input, pentru fiecare runda 0..64.
2. Distributia bitilor de iesire (monobit + chi-patrat) la 64 runde.
3. Corelatia bit de intrare -> bit de iesire (test de independenta
   chi-patrat pe tabel 2x2, esantion mare, corectie pentru testare
   multipla - prag Bonferroni).
4. Independentа hash-urilor de nonce consecutivi (context mining).
5. Distributia primului cuvant al iesirii vs uniform (mining).

Scop: cuantifica riguros absenta bias-urilor persistente - rezultat
negativ bine demonstrat (necesar inainte de a cauta scurtaturi).
"""

import math
import random
import json
import struct
import argparse

from .sha256_advanced import sha256, IV256, K256, MASK32, _sigma0, _sigma1


def avalanche_per_round(rounds=64, samples=256, seed=42):
    """Numarul mediu de biti schimbati din starea interna, per runda."""
    rng = random.Random(seed)
    base = bytes(rng.getrandbits(8) for _ in range(64))
    from .sha256_advanced import sha256_states
    s0 = sha256_states(base, rounds)[0]["states"]
    totals = [0.0] * (rounds + 1)
    for _ in range(samples):
        flipped = bytearray(base)
        i = rng.randrange(len(flipped))
        flipped[i] ^= 1 << rng.randrange(8)
        s1 = sha256_states(bytes(flipped), rounds)[0]["states"]
        for r in range(rounds + 1):
            totals[r] += sum(bin(x ^ y).count("1") for x, y in zip(s0[r], s1[r]))
    avg = [round(t / samples, 2) for t in totals]
    return {
        "experiment": "avalanche_per_runda",
        "samples": samples, "seed": seed, "rounds": rounds,
        "avg_flipped_bits_per_round": avg,
        "full_state_bits": 256,
        "round_reaching_half_avalanche": next(
            (r for r, v in enumerate(avg) if v >= 128), None),
        "note": "128 = jumatate din 256 biti (avalanche complet teoretic); "
                "valorile >128 la rundele finale provin din feedforward",
    }


def monobit_test(n=20000, seed=42, rounds=64):
    """Chi-patrat monobit pe bitii de iesire ai SHA-256."""
    rng = random.Random(seed)
    counts = [0] * 256  # peste toti bitii a n hash-uri
    for i in range(n):
        h = sha256(struct.pack(">I", i) + struct.pack(">Q", rng.getrandbits(64)), rounds)
        v = int.from_bytes(h, "big")
        for b in range(256):
            counts[b] += (v >> b) & 1
    # fiecare bit: binomial(n, 1/2); chi2 pe 2 celule = (c - n/2)^2 / (n/4)
    chi2 = sum((c - n / 2) ** 2 / (n / 4) for c in counts)
    # df=255, critic la 0.05 = 293.2; la 0.001 = 324.7
    return {
        "experiment": "monobit_chi2",
        "n_hashes": n, "total_bits": n * 256,
        "chi2": round(chi2, 2), "df": 255,
        "critical_0.05": 293.2, "critical_0.001": 324.7,
        "passes_randomness_at_0.001": chi2 < 324.7,
    }


def input_output_correlation(n=40000, seed=42, rounds=64, n_input_bits=32):
    """Maxima corelatie bit de intrare (primul cuvant) -> bit de iesire.

    Test chi-patrat 2x2 pentru fiecare pereche (in_bit, out_bit),
    cu prag Bonferroni pentru 32*256 = 8192 de teste.
    """
    rng = random.Random(seed)
    # esantionare contor pentru fiecare pereche
    tbl = [[[0, 0], [0, 0]] for _ in range(32 * 256)]
    for i in range(n):
        w = rng.getrandbits(32)
        h = sha256(struct.pack(">I", w) + b"\x00" * 60, rounds)
        hv = int.from_bytes(h, "big")
        for ib in range(n_input_bits):
            iv = (w >> ib) & 1
            for ob in range(256):
                ov = (hv >> ob) & 1
                tbl[ib * 256 + ob][iv][ov] += 1
    n_tests = n_input_bits * 256
    chi2s = []
    for t in tbl:
        a, b, c, d = t[0][0], t[0][1], t[1][0], t[1][1]
        n1, n2, m1, m2 = a + b, c + d, a + c, b + d
        if min(n1, n2, m1, m2) == 0:
            chi2s.append(0.0)
            continue
        chi2 = n * (a * d - b * c) ** 2 / (n1 * n2 * m1 * m2)
        chi2s.append(chi2)
    max_chi2 = max(chi2s)
    # Bonferroni: prag pentru 8192 teste la nivel de familie 0.01
    # chi2(1) critic la p=0.01/8192 ≈ 19.6
    return {
        "experiment": "corelatie_intrare_iesire",
        "n": n, "n_tests": n_tests,
        "max_chi2": round(max_chi2, 3),
        "bonferroni_threshold_family_0.01": 19.6,
        "significant_correlations": sum(1 for c in chi2s if c > 19.6),
        "conclusion": "nicio corelatie semnificativa peste pragul Bonferroni"
                      if max_chi2 <= 19.6 else "posibila bias - de investigat",
    }


def nonce_independence(n=50000, seed=42, rounds=64):
    """Sunt hash-urile nonces-urilor consecutive independente?

    Testam: P[hash(nonce=i) bit0 = hash(nonce=i+1) bit0] ≈ 0.5 si
    distributia primului cuvant vs uniform (10 bin-uri).
    """
    rng = random.Random(seed)
    same = 0
    bins = [0] * 16
    prev = None
    header = bytearray(80)
    for i in range(4, 68):
        header[i] = rng.getrandbits(8)
    header = bytes(header)
    for i in range(n):
        h = bytearray(header)
        h[76:80] = struct.pack(">I", i)
        v = int.from_bytes(sha256(bytes(h), rounds)[:4], "big")
        bins[v >> 28] += 1
        b0 = v & 1
        if prev is not None and b0 == prev:
            same += 1
        prev = b0
    exp = n / 16
    chi2 = sum((b - exp) ** 2 / exp for b in bins)
    return {
        "experiment": "independentа_nonce",
        "n": n,
        "p_same_bit_consecutive": round(same / (n - 1), 4),
        "first_word_uniform_chi2_15df": round(chi2, 2),
        "critical_chi2_15df_0.001": 37.7,
        "uniform_first_word": chi2 < 37.7,
    }


def run(out_json=None, seed=42, quick=False):
    n_corr = 8000 if quick else 40000
    res = {
        "avalanche": avalanche_per_round(seed=seed),
        "monobit": monobit_test(2000 if quick else 20000, seed),
        "correlation": input_output_correlation(n_corr, seed),
        "nonce_independence": nonce_independence(5000 if quick else 50000, seed),
    }
    if out_json:
        with open(out_json, "w") as fh:
            json.dump(res, fh, indent=2)
    return res


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--out", default=None)
    ap.add_argument("--quick", action="store_true")
    args = ap.parse_args()
    print(json.dumps(run(args.out, args.seed, args.quick), indent=2))
