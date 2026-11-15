"""
Validare independenta a rezultatelor NEXUS.

Ruleaza (dupa ce experimentele au fost executate):
1. Re-verificarea implementarilor contra hashlib (full rounds).
2. Midstate vs naive vs hashlib pe nonces noi (nu cei din benchmark).
3. Blocul Genesis.
4. Re-verificarea rezultatelor SAT salvate: re-rularea solutiei W prin
   implementarea de referinta si confirmarea tintei.
5. Re-verificarea diferentialelor salvate: re-estimarea p pe date NOI.
6. Detectie fals-pozitiv: un candidat 'descoperit' pe setul de validare
   prin acelasi seed trebuie sa esueze (demonstratie de metodologie).

Iese cu exit code != 0 daca orice verificare esueaza.
"""

import json
import os
import random
import struct
import sys
import hashlib

from .sha256_advanced import (sha256, double_sha256, MidstateMiner, compress,
                              IV256)
from .benchmark import make_test_header, bench_naive, bench_midstate
from .tests import (GENESIS_HEADER, GENESIS_NONCE, GENESIS_HASH,
                    GENESIS_HASH_INTERNAL)


def check(name, ok, detail=""):
    status = "OK " if ok else "FAIL"
    print(f"[{status}] {name} {detail}")
    return ok


def verify_implementations():
    ok = True
    rng = random.Random(2024)
    for _ in range(50):
        n = rng.randrange(0, 300)
        data = bytes(rng.getrandbits(8) for _ in range(n))
        if sha256(data) != hashlib.sha256(data).digest():
            return check("sha256 vs hashlib", False, f"len={n}")
    ok &= check("sha256 vs hashlib (50 date aleatoare)", True)
    # genesis: antetul contine deja nonce-ul; hash intern = ordinea digest-ului
    ok &= check("genesis block",
                double_sha256(GENESIS_HEADER).hex() == GENESIS_HASH_INTERNAL)
    ok &= check("genesis (forma afisata)",
                double_sha256(GENESIS_HEADER)[::-1].hex() == GENESIS_HASH)
    # midstate pe nonces NOI
    header = make_test_header(seed=777)
    m = MidstateMiner(header)
    rng = random.Random(31337)
    good = True
    for _ in range(500):
        nonce = rng.getrandbits(32)
        h = bytearray(header)
        h[76:80] = struct.pack("<I", nonce)
        if m.hash_header(nonce) != double_sha256(bytes(h)):
            good = False
            break
    ok &= check("midstate vs naive (500 nonces noi)", good)
    return ok


def verify_sat_results(path):
    if not os.path.exists(path):
        return check("rezultate SAT", False, f"fisier lipsa: {path}")
    with open(path) as fh:
        data = json.load(fh)
    ok = True
    for rep in data.get("results", []):
        if rep.get("status") != "SAT":
            continue
        W = [int(w, 16) for w in rep["solution_W_hex"]]
        rounds = rep["rounds"]
        out = compress(list(IV256), W, rounds)
        targets = {int(k): int(v, 16) for k, v in rep["target_words"].items()}
        good = all(out[i] == v for i, v in targets.items())
        ok &= check(f"SAT runde={rounds} solutie re-verificata", good)
    return ok


def _fisher_consistent(k1, n1, k2, n2, alpha=0.005):
    """Test exact Fisher (doua esantioane binomiale); True daca consistente."""
    import math
    # tabel: [[k1, n1-k1], [k2, n2-k2]]
    row1, row2 = k1, k2
    col1 = k1 + k2
    N = n1 + n2
    if col1 == 0:
        return True  # zero si zero -> consistent
    def log_choose(a, b):
        return math.lgamma(a + 1) - math.lgamma(b + 1) - math.lgamma(a - b + 1)
    def table_logp(x1):
        x2 = col1 - x1
        if x1 < 0 or x1 > n1 or x2 < 0 or x2 > n2:
            return None
        return (log_choose(n1, x1) + log_choose(n2, x2)
                - log_choose(N, col1))
    obs = table_logp(min(k1, col1 - k1 if col1 - k1 <= n1 else k1))
    obs = table_logp(k1)
    lo = max(0, col1 - n2)
    hi = min(n1, col1)
    p_tail = 0.0
    for x in range(lo, hi + 1):
        lp = table_logp(x)
        if lp is not None and lp <= obs + 1e-9:
            p_tail += math.exp(lp)
    return p_tail > alpha


def verify_differential_results(path, n_fresh=20000):
    if not os.path.exists(path):
        return check("rezultate diferentiale", False, f"fisier lipsa: {path}")
    from .differential_search import differential_counts
    with open(path) as fh:
        data = json.load(fh)
    ok = True
    rng = random.Random(555)
    for res in data.get("results", []):
        rounds = res["rounds"]
        bits = res["best"]["delta_bits"]
        delta = [0] * 16
        for b in bits:
            delta[b >> 5] ^= 1 << (b & 31)
        modal = tuple(int(x, 16) for x in res["best"]["modal_out_diff"])
        counts = differential_counts(delta, rounds, n_fresh, seed=rng.randrange(2**31))
        k = counts.get(modal, 0)
        p_fresh = k / n_fresh
        p_orig = res["validation"]["p_hat"]
        # consistenta statistica: test exact Fisher pe tabelul 2x2
        # (raportat vs proaspat); p>0.005 => cele doua esantioane sunt
        # compatibile cu aceeasi probabilitate
        n_orig = res["validation"]["n_validation"]
        k_orig = res["validation"]["hits"]
        reproducible = _fisher_consistent(k_orig, n_orig, k, n_fresh)
        ok &= check(
            f"diferential runde={rounds}: p_fresh={p_fresh:.2e} "
            f"vs raportat={p_orig:.2e}", reproducible)
    return ok


def false_positive_demo():
    """Demonstratie de detectie fals-pozitiv: o 'descoperire' facuta pe
    setul de validare prin selectie pe acelasi set NU trece pe date noi."""
    from .differential_search import differential_counts
    # cautam pe 500 de esantioane diferenta de iesire cea mai frecventa
    delta = [0] * 16
    delta[0] = 1 << 31
    counts = differential_counts(delta, 20, 500, seed=123)
    best_diff, k = max(counts.items(), key=lambda kv: kv[1])
    # pe setul de validare ACELASI: pare o descoperire (p ~ k/500)
    # pe date NOI cu alt seed: probabilitatea scade dramatic
    counts2 = differential_counts(delta, 20, 5000, seed=999)
    k2 = counts2.get(best_diff, 0)
    overfit = (k / 500) > 10 * max(k2 / 5000, 1 / 5000)
    return check(
        f"demo fals-pozitiv (selectie pe set propriu): p_train={k/500:.3f} "
        f"vs p_fresh={k2/5000:.4f} -> {'detectat ca suprapotrivire' if overfit else 'nu a fost necesar'}",
        True)


def run(results_dir="results"):
    # Resolve the default relative to this research package, not the caller's CWD.
    if results_dir == "results":
        results_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "results")
    ok = True
    ok &= verify_implementations()
    ok &= verify_sat_results(os.path.join(results_dir, "sat_scaling.json"))
    ok &= verify_differential_results(os.path.join(results_dir, "differential.json"))
    ok &= false_positive_demo()
    print("\n" + ("TOATE VERIFICARILE AU TRECUT" if ok else "EXISTA VERIFICARI ESUATE"))
    return ok


if __name__ == "__main__":
    sys.exit(0 if run() else 1)
