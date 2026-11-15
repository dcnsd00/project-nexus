"""
Cautare diferentiala multi-bit pentru SHA-256 cu runde reduse (NEXUS).

Metoda:
- Diferente XOR in cuvintele mesajului (W[0..15]) si/sau in starea initiala.
- Scor: -log2(p) unde p = probabilitatea empirica a celei mai probabile
  diferente de iesire dupa `rounds` runde (fara feedforward - "core").
- Cautare: hill-climbing cu mutatii 1-bit (adaugare/stergere) si
  simulated annealing, cu buget de timp configurabil.
- Separare stricta: set de DESCOPERIRE (cautarea) si set de VALIDARE
  (estimare finala cu intervale de incredere Wilson).

Rezultatele sunt doar pentru runde reduse; NU se extrapoleaza la SHA-256
complet (64 runde). Vezi raport pentru discutia teoretica.
"""

import math
import random
import time
import json
import argparse

from .sha256_advanced import (IV256, K256, MASK32, _rotr, _sigma0, _sigma1,
                              _small_sigma0, _small_sigma1)


def compress_core(state, W, rounds):
    """Rundele 0..rounds-1 fara feedforward (starea interna dupa ultima runda)."""
    a, b, c, d, e, f, g, h = state
    for t in range(rounds):
        t1 = (h + _sigma1(e) + ((e & f) ^ (~e & g)) + K256[t] + W[t]) & MASK32
        t2 = (_sigma0(a) + ((a & b) ^ (a & c) ^ (b & c))) & MASK32
        h, g, f, e, d, c, b, a = g, f, e, (d + t1) & MASK32, c, b, a, (t1 + t2) & MASK32
    return (a, b, c, d, e, f, g, h)


def expand_W(W0, rounds):
    W = list(W0)
    for t in range(16, rounds):
        W.append((W[t - 16] + _small_sigma0(W[t - 15]) + W[t - 7]
                  + _small_sigma1(W[t - 2])) & MASK32)
    return W


def differential_counts(delta_msg, rounds, n, seed, delta_iv=None):
    """Returneaza Counter al diferentelor de iesire pentru n mesaje aleatoare.

    delta_msg: lista de 16 int (XOR in W[0..15]); delta_iv: lista de 8 int sau None.
    """
    rng = random.Random(seed)
    Wd = expand_W(list(delta_msg), rounds) if any(delta_msg) else None
    counts = {}
    base_iv = list(IV256)
    for _ in range(n):
        M = [rng.getrandbits(32) for _ in range(16)]
        if Wd is not None:
            W2 = [(M[i] ^ Wd[i]) & MASK32 for i in range(16)]
            W2 = expand_W(W2, rounds)
        else:
            W2 = M
        iv = base_iv if delta_iv is None else [
            (base_iv[i] ^ delta_iv[i]) & MASK32 for i in range(8)]
        out1 = compress_core(base_iv, expand_W(M, rounds), rounds)
        out2 = compress_core(iv, W2, rounds)
        diff = tuple((x ^ y) & MASK32 for x, y in zip(out1, out2))
        counts[diff] = counts.get(diff, 0) + 1
    return counts


def bits_to_words(delta_bits):
    """Lista de indici de biti (0..511) -> 16 cuvinte XOR."""
    w = [0] * 16
    for b in delta_bits:
        w[b >> 5] ^= 1 << (b & 31)
    return w


def score_delta(delta_bits, rounds, n, seed, delta_iv=None):
    """Scor = -log2(p_max); intoarce (score, p_hat, modal_diff, counts)."""
    delta_msg = bits_to_words(delta_bits)
    counts = differential_counts(delta_msg, rounds, n, seed, delta_iv)
    best_diff, best = max(counts.items(), key=lambda kv: kv[1])
    p = best / n
    score = -math.log2(p) if p > 0 else float("inf")
    return score, p, best_diff, counts


def neighbors(delta_words, rng, max_bits=6, n_active_words=None):
    """Mutatii 1-bit: adauga, sterge sau muta un bit in diferenta de mesaj.

    IMPORTANT: cuvantul W[t] nu afecteaza iesirea inainte de runda t
    (si schedule-ul), asa ca diferentele se restrang la cuvintele ACTIVE:
    words 0..min(rounds-1, 15). Altfel cautarea gaseste trivial p=1
    (diferenta in cuvant nefolosit -> iesiri identice).
    """
    limit = (n_active_words * 32) if n_active_words else 512
    d = [0] * 16
    for w in delta_words:
        d[w >> 5] ^= 1 << (w & 31)
    bits = [w for w in range(512) if d[w >> 5] >> (w & 31) & 1]
    ops = ["add", "del", "move"] if bits else ["add"]
    op = rng.choice(ops)
    if op == "add" and len(bits) < max_bits:
        cand = rng.randrange(limit)
        if cand not in bits:
            bits.append(cand)
    elif op == "del" and bits:
        bits.pop(rng.randrange(len(bits)))
    elif op == "move" and bits:
        i = rng.randrange(len(bits))
        bits[i] = rng.randrange(limit)
        bits = list(set(bits))
    return bits


def hill_climb(rounds, n_eval, seed, time_limit=60.0, start_delta=None):
    """Hill-climbing: porneste de la 1 bit, accepta doar imbunatatiri."""
    rng = random.Random(seed)
    t0 = time.time()
    n_active = min(max(rounds - 1, 1), 16)
    cur = start_delta if start_delta else [rng.randrange(n_active * 32)]
    cur_score, cur_p, cur_out, _ = score_delta(
        [b for b in cur], rounds, n_eval, seed + 1)
    history = [cur_score]
    n_steps = 0
    while time.time() - t0 < time_limit:
        cand = neighbors(cur, rng, n_active_words=n_active)
        if not cand:
            continue
        s, p, out, _ = score_delta(cand, rounds, n_eval, seed + 1000 + n_steps)
        n_steps += 1
        if s < cur_score:
            cur, cur_score, cur_p, cur_out = cand, s, p, out
            history.append(cur_score)
    return {
        "delta_bits": sorted(cur), "score": round(cur_score, 3),
        "p_hat": cur_p, "modal_out_diff": [hex(x) for x in cur_out],
        "steps": n_steps, "history": [round(x, 3) for x in history],
    }


def anneal(rounds, n_eval, seed, time_limit=60.0, t0_temp=2.0):
    """Simulated annealing peste aceeasi spatiu de mutatii."""
    rng = random.Random(seed)
    start = time.time()
    n_active = min(max(rounds - 1, 1), 16)
    cur = [rng.randrange(n_active * 32)]
    cur_score, _, cur_out, _ = score_delta(cur, rounds, n_eval, seed + 1)
    best, best_score, best_out = list(cur), cur_score, cur_out
    n_steps, n_accept = 0, 0
    while time.time() - start < time_limit:
        cand = neighbors(cur, rng, n_active_words=n_active)
        if not cand:
            continue
        s, _, out, _ = score_delta(cand, rounds, n_eval, seed + 5000 + n_steps)
        temp = max(0.05, t0_temp * (1 - (time.time() - start) / time_limit))
        n_steps += 1
        if s < cur_score or rng.random() < math.exp((cur_score - s) / temp):
            cur, cur_score = cand, s
            n_accept += 1
            if s < best_score:
                best, best_score, best_out = list(cand), s, out
    return {"delta_bits": sorted(best), "score": round(best_score, 3),
            "modal_out_diff": [hex(x) for x in best_out],
            "steps": n_steps, "accepted": n_accept}


def wilson_ci(k, n, z=1.96):
    """Interval de incredere Wilson pentru o proportie binomiala."""
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    denom = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    half = (z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))) / denom
    return (max(0.0, center - half), min(1.0, center + half))


def validate(rounds, delta_bits, n, seed, modal_out_diff=None):
    """Validare independenta: estimare p pe set proaspat de esantioane."""
    delta_msg = [0] * 16
    for b in delta_bits:
        delta_msg[b >> 5] ^= 1 << (b & 31)
    counts = differential_counts(delta_msg, rounds, n, seed)
    if modal_out_diff is not None:
        target = tuple(modal_out_diff)
        k = counts.get(target, 0)
    else:
        _, k = max(counts.items(), key=lambda kv: kv[1])
    lo, hi = wilson_ci(k, n)
    return {
        "rounds": rounds, "n_validation": n, "hits": k,
        "p_hat": k / n, "ci95": [lo, hi],
        "log2_p_hat": round(-math.log2(k / n), 3) if k else None,
        "log2_ci95": [round(-math.log2(hi), 3) if hi > 0 else None,
                      round(-math.log2(lo), 3) if lo > 0 else None],
        "uniform_baseline_log2": -32.0,
        "above_uniform": k / n > (2 ** -32) * 10,
    }


def run_experiment(rounds_list, n_search=1500, n_validation=20000,
                   seed=42, time_limit_per_round=45.0, out_json=None):
    results = []
    for rounds in rounds_list:
        t0 = time.time()
        hc = hill_climb(rounds, n_search, seed, time_limit_per_round)
        an = anneal(rounds, n_search, seed + 7, time_limit_per_round / 3)
        best = hc if hc["score"] <= an["score"] else an
        modal = [int(x, 16) for x in best.get("modal_out_diff", [])]
        val = validate(rounds, best["delta_bits"], n_validation, seed + 999, modal)
        res = {
            "rounds": rounds, "seed": seed,
            "hill_climb": hc, "annealing": an,
            "best": best, "validation": val,
            "elapsed_s": round(time.time() - t0, 2),
        }
        results.append(res)
        print(f"[diff] runde={rounds} scor={best['score']} "
              f"p_valid={val['p_hat']:.2e} ({val['hits']}/{val['n_validation']}) "
              f"t={res['elapsed_s']}s")
    if out_json:
        with open(out_json, "w") as fh:
            json.dump({"experiment": "differential_search",
                       "config": {"n_search": n_search,
                                  "n_validation": n_validation,
                                  "seed": seed,
                                  "time_limit_per_round_s": time_limit_per_round},
                       "results": results}, fh, indent=2)
    return results


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--rounds", type=int, nargs="+", default=[3, 4, 5, 6])
    ap.add_argument("--n-search", type=int, default=1500)
    ap.add_argument("--n-validation", type=int, default=20000)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--time-limit", type=float, default=45.0)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()
    run_experiment(args.rounds, args.n_search, args.n_validation,
                   args.seed, args.time_limit, args.out)
