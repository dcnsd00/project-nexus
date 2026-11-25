"""
Message modification pentru SHA-256 cu runde reduse (NEXUS).

Doua experimente reale, masurate:

E1 (control determinist prin inversarea rundei 0):
   Alegand W[0] se controleaza EXACT starea (a1, e1) dupa runda 0
   (a1 = t1 + t2, e1 = d0 + t1, t1 = h0 + Sigma1(e0) + Ch + K0 + W0).
   => orice conditie de traseu pe biții din a1/e1 poate fi satisfacuta
   prin constructie, nu prin incercari. Masuram: P[conditie] random
   (≈2^-k) vs modificat (=1).

E2 (message modification condus de date pentru diferentiale):
   Pentru cea mai buna diferenta Δ gasita de differential_search la
   `rounds` runde, invatam prin corelatie care biti din e1 (starea
   dupa runda 0) prezic succesul (iesirea = diferenta modala Δ_out),
   apoi fortam acesti biti prin alegerea lui W[0]. Masuram factorul
   de imbunatatire pe set de VALIDARE proaspat.

Toate rezultatele sunt doar pentru runde reduse.
"""

import math
import random
import json
import time
import argparse

from .sha256_advanced import IV256, K256, MASK32, _sigma0, _sigma1
from .differential_search import compress_core, expand_W, differential_counts


def round0_target_to_W0(target_e1, state=None):
    """W[0] astfel incat e1 (starea 'e' dupa runda 0) = target_e1, exact.

    e1 = d0 + t1  =>  t1 = target_e1 - d0
    t1 = h0 + Sigma1(e0) + Ch(e0,f0,g0) + K0 + W0  =>  W0 = t1 - rest.
    """
    a, b, c, d, e, f, g, h = state if state else IV256
    t1 = (target_e1 - d) & MASK32
    rest = (h + _sigma1(e) + ((e & f) ^ (~e & g)) + K256[0]) & MASK32
    return (t1 - rest) & MASK32


def apply_modification(W, condition_bits, condition_values, state=None, rng=None):
    """Returneaza W' cu W'[0] ales astfel incat bitii din e1 sa aiba
    valorile cerute. RNG-ul poate fi injectat pentru reproductibilitate."""
    rng = rng if rng is not None else random.Random(0)
    a, b, c, d, e, f, g, h = state if state else IV256
    # t1 determina e1 complet; alegem t1 aleator apoi fixam bitii ceruti
    t1 = rng.getrandbits(32)
    mask = 0
    for bit, val in zip(condition_bits, condition_values):
        t1 = (t1 & ~(1 << bit)) | (val << bit)
        mask |= 1 << bit
    e1 = (d + t1) & MASK32
    for bit, val in zip(condition_bits, condition_values):
        e1 = (e1 & ~(1 << bit)) | (val << bit)
    # recalculam t1 din e1 (poate necesita ajustare pe biti de carry)
    t1 = (e1 - d) & MASK32
    rest = (h + _sigma1(e) + ((e & f) ^ (~e & g)) + K256[0]) & MASK32
    W0 = (t1 - rest) & MASK32
    Wp = list(W)
    Wp[0] = W0
    return Wp


# ---------------------------------------------------------------------------
# E1: control determinist
# ---------------------------------------------------------------------------

def experiment_e1(n=1000, seed=42, k_bits=8):
    """P[bitii k din e1 au valori fixate] random vs cu modificare."""
    rng = random.Random(seed)
    bits = list(range(k_bits))          # bitii 0..k-1 din e1
    vals = [rng.randint(0, 1) for _ in bits]
    hits_random = 0
    for _ in range(n):
        W = [rng.getrandbits(32) for _ in range(16)]
        st = list(IV256)
        t1 = (st[7] + _sigma1(st[4]) + ((st[4] & st[5]) ^ (~st[4] & st[6]))
              + K256[0] + W[0]) & MASK32
        e1 = (st[3] + t1) & MASK32
        if all((e1 >> b) & 1 == v for b, v in zip(bits, vals)):
            hits_random += 1
    hits_mod = 0
    for _ in range(n):
        W = [rng.getrandbits(32) for _ in range(16)]
        Wp = apply_modification(W, bits, vals, rng=rng)
        t1 = (IV256[7] + _sigma1(IV256[4])
              + ((IV256[4] & IV256[5]) ^ (~IV256[4] & IV256[6]))
              + K256[0] + Wp[0]) & MASK32
        e1 = (IV256[3] + t1) & MASK32
        if all((e1 >> b) & 1 == v for b, v in zip(bits, vals)):
            hits_mod += 1
    return {
        "experiment": "E1_control_determinist_e1",
        "k_condition_bits": k_bits, "n": n, "seed": seed,
        "p_random": hits_random / n,
        "p_random_expected": 2 ** -k_bits,
        "p_modified": hits_mod / n,
        "improvement_factor": (hits_mod / n) / max(hits_random / n, 1 / n),
        "theory": "1 cuvant de mesaj => control complet al (a1, e1); "
                  "conditiile de runda 0-1 ale unui traseu sunt gratuite",
    }


# ---------------------------------------------------------------------------
# E2: message modification condus de date
# ---------------------------------------------------------------------------

def _round0_state(W0, state=None):
    """Starea (a1, e1) dupa runda 0 pentru un W[0] dat."""
    a, b, c, d, e, f, g, h = state if state else IV256
    t1 = (h + _sigma1(e) + ((e & f) ^ (~e & g)) + K256[0] + W0) & MASK32
    t2 = (_sigma0(a) + ((a & b) ^ (a & c) ^ (b & c))) & MASK32
    return (t1 + t2) & MASK32, (d + t1) & MASK32


def _w0_for_target(target_t1, state=None):
    a, b, c, d, e, f, g, h = state if state else IV256
    rest = (h + _sigma1(e) + ((e & f) ^ (~e & g)) + K256[0]) & MASK32
    return (target_t1 - rest) & MASK32


def _t2_round0(state=None):
    a, b, c, d, e, f, g, h = state if state else IV256
    return (_sigma0(a) + ((a & b) ^ (a & c) ^ (b & c))) & MASK32


def mine_conditions_reg(rounds, delta_bits, modal_out, n_learn, seed,
                        reg="e1"):
    """Invata biti din a1 sau e1 (runda 0) care prezic succesul."""
    rng = random.Random(seed)
    delta_msg = [0] * 16
    for b in delta_bits:
        delta_msg[b >> 5] ^= 1 << (b & 31)
    modal = tuple(modal_out)
    data = []
    for _ in range(n_learn):
        M = [rng.getrandbits(32) for _ in range(16)]
        M2 = [(M[i] ^ delta_msg[i]) & MASK32 for i in range(16)]
        a1, e1 = _round0_state(M[0])
        o1 = compress_core(list(IV256), expand_W(M, rounds), rounds)
        o2 = compress_core(list(IV256), expand_W(M2, rounds), rounds)
        diff = tuple((x ^ y) & MASK32 for x, y in zip(o1, o2))
        data.append(((a1, e1), diff == modal))
    n_pos = sum(1 for _, s in data if s)
    n_neg = len(data) - n_pos
    scored = []
    for bit in range(32):
        sel = 0 if reg == "a1" else 1
        p1 = sum(1 for (st, s) in data
                 if s and (st[sel] >> bit) & 1) / max(n_pos, 1)
        p0 = sum(1 for (st, s) in data
                 if not s and (st[sel] >> bit) & 1) / max(n_neg, 1)
        scored.append((abs(p1 - p0), bit, 1 if p1 > p0 else 0))
    scored.sort(reverse=True)
    return scored, n_pos / len(data)


def experiment_e2(rounds=2, n_learn=25000, n_test=20000, seed=42,
                  delta_bits=None, modal_out=None, k_cond=8):
    """Cauta conditii pe a1 SI e1, aplica modificarea pe fiecare in parte,
    masoara pe set de validare. W[0] controleaza (a1, e1) cu legatura
    e1 - a1 = d0 - t2 (constanta), deci setam un registru odata."""
    if delta_bits is None:
        delta_bits = [31]
        delta_msg = [0] * 16
        delta_msg[0] = 1 << 31
        counts = differential_counts(delta_msg, rounds, 3000, seed + 11)
        modal_out = list(max(counts.items(), key=lambda kv: kv[1])[0])
    import time as _time
    t0 = _time.time()
    modal = tuple(modal_out)
    delta_msg = [0] * 16
    for b in delta_bits:
        delta_msg[b >> 5] ^= 1 << (b & 31)
    t2 = _t2_round0()
    d0 = IV256[3]
    results = {}
    for reg in ("a1", "e1"):
        conds, p_learn = mine_conditions_reg(rounds, delta_bits, modal,
                                             n_learn, seed, reg)
        cond_bits = [b for _, b, _ in conds[:k_cond]]
        cond_vals = [v for _, _, v in conds[:k_cond]]
        rng = random.Random(seed + 31337)
        succ_rand = succ_mod = 0
        n = n_test
        for _ in range(n):
            M = [rng.getrandbits(32) for _ in range(16)]
            M2 = [(M[i] ^ delta_msg[i]) & MASK32 for i in range(16)]
            o1 = compress_core(list(IV256), expand_W(M, rounds), rounds)
            o2 = compress_core(list(IV256), expand_W(M2, rounds), rounds)
            if tuple((x ^ y) & MASK32 for x, y in zip(o1, o2)) == modal:
                succ_rand += 1
            # varianta modificata: fortam bitii de conditie prin W[0]
            Mp = list(M)
            a1, e1 = _round0_state(M[0])
            if reg == "a1":
                new_a1 = a1
                for bit, val in zip(cond_bits, cond_vals):
                    new_a1 = (new_a1 & ~(1 << bit)) | (val << bit)
                # t1 = a1 - t2; e1 devine d0 + t1 (determinat)
                t1 = (new_a1 - t2) & MASK32
            else:
                new_e1 = e1
                for bit, val in zip(cond_bits, cond_vals):
                    new_e1 = (new_e1 & ~(1 << bit)) | (val << bit)
                t1 = (new_e1 - d0) & MASK32
            Mp[0] = _w0_for_target(t1)
            Mp2 = [(Mp[i] ^ delta_msg[i]) & MASK32 for i in range(16)]
            o1 = compress_core(list(IV256), expand_W(Mp, rounds), rounds)
            o2 = compress_core(list(IV256), expand_W(Mp2, rounds), rounds)
            if tuple((x ^ y) & MASK32 for x, y in zip(o1, o2)) == modal:
                succ_mod += 1
        p_rand = succ_rand / n
        p_mod = succ_mod / n
        results[reg] = {
            "p_success_random_validation": p_rand,
            "p_success_modified_validation": p_mod,
            "improvement_factor": p_mod / p_rand if p_rand else None,
            "condition_bits": cond_bits, "condition_values": cond_vals,
            "p_base_learn": p_learn,
        }
    return {
        "experiment": "E2_message_modification_data_driven",
        "rounds": rounds, "seed": seed, "n_learn": n_learn,
        "n_test": n_test, "delta_bits": delta_bits,
        "modal_out_diff": [hex(x) for x in modal_out],
        "by_register": results,
        "relation": "e1 - a1 = d0 - t2 (constant); W[0] seteaza (a1,e1) "
                    "constranse de aceasta relatie",
        "elapsed_s": round(_time.time() - t0, 2),
        "note": "conditii invatate pe set de invatare, evaluate pe set de "
                "validare proaspat; a1/e1 sunt singurele registre care "
                "depind de W[0] la runda 0 (b1..h1 = IV)",
    }


def run(out_json=None, seed=42):
    res = {
        "E1": experiment_e1(seed=seed),
        "E2_r2": experiment_e2(rounds=2, seed=seed),
        "E2_r3": experiment_e2(rounds=3, seed=seed),
    }
    if out_json:
        with open(out_json, "w") as fh:
            json.dump(res, fh, indent=2)
    return res


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()
    r = run(args.out, args.seed)
    print(json.dumps(r, indent=2))
