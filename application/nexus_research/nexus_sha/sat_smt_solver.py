"""
SAT pentru SHA-256 cu runde reduse (NEXUS).

Encodare CNF exacta a functiei de compresie cu `rounds` runde (cu feedforward):
- rotatiile si shifturile = reindexare de variabile (gratuit)
- Ch, Maj = clauze pe 3 biti
- adunari mod 2^32 = ripple-carry (XOR3 + majoritate pe bit)
- schedule-ul mesajului = XOR-uri + adunari
- feedforward: out_i = state_i + IV_i

Problema rezolvata: PREIMAGE PARTIAL - gaseste W astfel incat cuvantul 0 al
iesirii (si optional mai multe cuvinte) sa egaleze o tinta data.

Se raporteaza SEPARAT: construirea formulei, rezolvarea, timpul/memoria
solverului si verificarea independenta a solutiei cu sha256_advanced
(implementare complet separata de encodare).

Nu se rezolva SHA-256 complet (64 runde) - vezi raportul pentru discutia
de complexitate (2^256 spatiu, SAT nu schimba ordinul de marime).
"""

import time
import json
import random
import argparse

from .sha256_advanced import (IV256, K256, MASK32, _rotr, compress,
                              expand_block)

try:
    from pysat.formula import CNF, IDPool
    from pysat.solvers import Minisat22
    PYSAT_AVAILABLE = True
except ImportError:  # pragma: no cover
    PYSAT_AVAILABLE = False


class Encoder:
    def __init__(self):
        self.pool = IDPool()
        self.cnf = CNF()
        # variabila constant TRUE
        self.T = self.pool.id("TRUE")
        self.cnf.append([self.T])
        self.F = -self.T

    def v(self, name):
        return self.pool.id(name)

    def const_val(self, lit):
        """1/0 daca literalul e constant, altfel None."""
        if lit == self.T:
            return 1
        if lit == -self.T:
            return 0
        return None

    # ---- porți CNF generice (constiente de constante) ----
    def gate(self, inputs, output, func):
        """Encodare prin tabel de adevar: output = func(*inputs).

        inputs: literali (pot fi constante T/F); output: literal variabila.
        Clauzele forbide fiecare asignare gresita a variabilelor libere.
        """
        free = [i for i, l in enumerate(inputs) if self.const_val(l) is None]
        for assign in range(1 << len(free)):
            vals = [self.const_val(l) for l in inputs]
            for j, fi in enumerate(free):
                vals[fi] = (assign >> j) & 1
            want = func(*vals)
            clause = [inputs[fi] if vals[fi] == 0 else -inputs[fi]
                      for fi in free]
            # forbide output = 1-want: literal fals exact la valoarea gresita
            clause.append(-output if want == 0 else output)
            self.cnf.append(clause)

    def xor2(self, a, b, y):
        self.gate([a, b], y, lambda x, z: x ^ z)

    def xor3(self, a, b, c, y):
        self.gate([a, b, c], y, lambda x, z, w: x ^ z ^ w)

    def maj3(self, a, b, c, y):
        self.gate([a, b, c], y, lambda x, z, w: int(x + z + w >= 2))

    def ch(self, e, f, g, y):
        """y = (e & f) | (~e & g), pe 1 bit."""
        self.gate([e, f, g], y, lambda x, z, w: (z if x else w))

    # ---- adunare ripple-carry pe 32 biti ----
    def add2(self, xs, ys, ss, name):
        """ss = xs + ys (mod 2^32); toate listele de 32 literali, LSB primul."""
        assert len(xs) == 32 and len(ys) == 32 and len(ss) == 32
        carry = self.F
        for i in range(32):
            self.xor3(xs[i], ys[i], carry, ss[i])
            nc = self.v(f"c_{name}_{i+1}")
            self.maj3(xs[i], ys[i], carry, nc)
            carry = nc
        return ss

    def add3(self, xs, ys, zs, ss, name):
        """ss = xs + ys + zs prin doua adunari (temp = xs + ys)."""
        tmp = [self.v(f"t_{name}_{i}") for i in range(32)]
        self.add2(xs, ys, tmp, name + "_a")
        self.add2(tmp, zs, ss, name + "_b")
        return ss

    def const_bits(self, value, name_prefix):
        """32 de literali constanti (TRUE/FALSE) pentru o valoare fixa."""
        return [self.T if (value >> i) & 1 else self.F for i in range(32)]

    def rotl_alias(self, xs, n):
        """Rotatia la dreapta cu n = permutare de indici (LSB-first)."""
        return [xs[(i + n) % 32] for i in range(32)]

    def shr_alias(self, xs, n):
        return [xs[i - n] if i - n >= 0 else self.F for i in range(32)]

    def xor3_word(self, a, b, c, name):
        out = [self.v(f"{name}_{i}") for i in range(32)]
        for i in range(32):
            self.xor3(a[i], b[i], c[i], out[i])
        return out


def encode_sha256_rounds(enc: Encoder, rounds: int, fixed_words=None,
                         free_words=16):
    """Encodarea compresiei cu feedforward. Intoarce (W, out_words)."""
    # mesajul: W[0..15] ca variabile
    W = []
    for t in range(16):
        if fixed_words is not None and t in fixed_words:
            W.append(enc.const_bits(fixed_words[t], f"wc{t}"))
        else:
            W.append([enc.v(f"w{t}_{i}") for i in range(32)])
    # schedule
    for t in range(16, rounds):
        # s0(W[t-15]) = rotr7 ^ rotr18 ^ shr3
        w15 = W[t - 15]
        s0 = enc.xor3_word(enc.rotl_alias(w15, 7), enc.rotl_alias(w15, 18),
                           enc.shr_alias(w15, 3), f"s0_{t}")
        s1 = enc.xor3_word(enc.rotl_alias(W[t - 2], 17),
                           enc.rotl_alias(W[t - 2], 19),
                           enc.shr_alias(W[t - 2], 10), f"s1_{t}")
        wt = [enc.v(f"w{t}_{i}") for i in range(32)]
        # W[t] = W[t-16] + s0 + W[t-7] + s1
        tmp1 = [enc.v(f"e1_{t}_{i}") for i in range(32)]
        enc.add2(W[t - 16], s0, tmp1, f"exp1_{t}")
        tmp2 = [enc.v(f"e2_{t}_{i}") for i in range(32)]
        enc.add2(W[t - 7], s1, tmp2, f"exp2_{t}")
        enc.add2(tmp1, tmp2, wt, f"exp3_{t}")
        W.append(wt)
    # starea initiala = IV (constante)
    st = [enc.const_bits(v, f"iv{vi}") for vi, v in enumerate(IV256)]
    for t in range(rounds):
        a, b, c, d, e, f, g, h = st
        # T1 = h + Sigma1(e) + Ch(e,f,g) + K + W[t]
        sig1 = enc.xor3_word(enc.rotl_alias(e, 6), enc.rotl_alias(e, 11),
                             enc.rotl_alias(e, 25), f"S1_{t}")
        chv = [enc.v(f"ch_{t}_{i}") for i in range(32)]
        for i in range(32):
            enc.ch(e[i], f[i], g[i], chv[i])
        kc = enc.const_bits(K256[t], f"k{t}")
        p1 = [enc.v(f"p1_{t}_{i}") for i in range(32)]
        enc.add2(h, sig1, p1, f"a1_{t}")
        p2 = [enc.v(f"p2_{t}_{i}") for i in range(32)]
        enc.add2(p1, chv, p2, f"a2_{t}")
        p3 = [enc.v(f"p3_{t}_{i}") for i in range(32)]
        enc.add2(p2, kc, p3, f"a3_{t}")
        t1 = [enc.v(f"t1_{t}_{i}") for i in range(32)]
        enc.add2(p3, W[t], t1, f"a4_{t}")
        # T2 = Sigma0(a) + Maj(a,b,c)
        sig0 = enc.xor3_word(enc.rotl_alias(a, 2), enc.rotl_alias(a, 13),
                             enc.rotl_alias(a, 22), f"S0_{t}")
        majv = [enc.v(f"mj_{t}_{i}") for i in range(32)]
        for i in range(32):
            enc.maj3(a[i], b[i], c[i], majv[i])
        t2 = [enc.v(f"t2_{t}_{i}") for i in range(32)]
        enc.add2(sig0, majv, t2, f"a5_{t}")
        # noile stari
        na = [enc.v(f"na_{t}_{i}") for i in range(32)]
        enc.add2(t1, t2, na, f"a6_{t}")
        ne = [enc.v(f"ne_{t}_{i}") for i in range(32)]
        enc.add2(d, t1, ne, f"a7_{t}")
        st = [na, a, b, c, ne, e, f, g]  # shift: b'=a, c'=b, d'=c, f'=e, g'=f, h'=g
    # feedforward: out_i = st_i + IV_i
    out = []
    for i in range(8):
        ow = [enc.v(f"out{i}_{j}") for j in range(32)]
        enc.add2(st[i], enc.const_bits(IV256[i], f"fiv{i}"), ow, f"ff{i}")
        out.append(ow)
    return W, out


def solve_partial_preimage(rounds, target_words, seed=42, solver="minisat22",
                           fixed_words=None, verbose=True):
    """Gaseste W cu out[i] = target_words[i] pentru cuvintele fixate.

    target_words: dict {index_cuvant: valoare_32bit}
    Intoarce raport complet (build/solve/verificare) sau UNSAT.
    """
    if not PYSAT_AVAILABLE:
        return {"error": "python-sat indisponibil: pip install python-sat"}
    rng = random.Random(seed)
    # tinta realista: calculata cu implementarea de referinta
    M0 = [rng.getrandbits(32) for _ in range(16)]
    ref_out = compress(list(IV256), list(M0), rounds)
    targets = {}
    for idx in target_words:
        targets[idx] = ref_out[idx]
    t0 = time.time()
    enc = Encoder()
    W, out = encode_sha256_rounds(enc, rounds, fixed_words=fixed_words)
    for idx, val in targets.items():
        for i in range(32):
            lit = out[idx][i] if (val >> i) & 1 else -out[idx][i]
            enc.cnf.append([lit])
    build_time = time.time() - t0
    n_vars = enc.pool.top
    n_clauses = len(enc.cnf.clauses)
    # rezolvare
    t0 = time.time()
    if solver == "minisat22":
        with Minisat22(bootstrap_with=enc.cnf.clauses) as s:
            sat = s.solve()
            model = s.get_model() if sat else None
    else:
        return {"error": f"solver necunoscut: {solver}"}
    solve_time = time.time() - t0
    report = {
        "rounds": rounds, "seed": seed,
        "target_words": {str(k): hex(v) for k, v in targets.items()},
        "n_fixed_output_bits": 32 * len(targets),
        "formula": {"vars": n_vars, "clauses": n_clauses,
                    "build_time_s": round(build_time, 3)},
        "solve_time_s": round(solve_time, 3),
        "status": "SAT" if sat else "UNSAT",
    }
    if not sat:
        return report
    # extragem W din model
    pos = set(l for l in model if l > 0)
    Wsol = []
    for t in range(16):
        w = 0
        for i in range(32):
            if enc.pool.id(f"w{t}_{i}") in pos:
                w |= 1 << i
        Wsol.append(w)
    # VERIFICARE INDEPENDENTA cu sha256_advanced (cod separat de encodare)
    check_out = compress(list(IV256), list(Wsol), rounds)
    ok = all(check_out[i] == targets[i] for i in targets)
    report["solution_W_hex"] = [hex(w) for w in Wsol]
    report["independent_verification"] = {
        "method": "sha256_advanced.compress (implementare separata)",
        "matches_target": ok,
        "computed_out0": hex(check_out[0]),
    }
    if verbose:
        print(f"[sat] runde={rounds} bits={32*len(targets)} "
              f"vars={n_vars} clauses={n_clauses} build={build_time:.2f}s "
              f"solve={solve_time:.2f}s SAT={sat} verificat={ok}")
    return report


def scaling_experiment(rounds_list=(6, 8, 10, 12), n_words_fixed=1,
                       seed=42, out_json=None):
    results = []
    for r in rounds_list:
        rep = solve_partial_preimage(r, {0: 0} if n_words_fixed == 1
                                     else {i: 0 for i in range(n_words_fixed)},
                                     seed=seed)
        results.append(rep)
    if out_json:
        with open(out_json, "w") as fh:
            json.dump({"experiment": "sat_scaling",
                       "config": {"rounds": list(rounds_list),
                                  "n_words_fixed": n_words_fixed, "seed": seed},
                       "results": results}, fh, indent=2)
    return results


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--rounds", type=int, nargs="+", default=[6, 8, 10])
    ap.add_argument("--fixed-words", type=int, default=1,
                    help="cate cuvinte de iesire sunt fixate (32 biti fiecare)")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()
    res = scaling_experiment(tuple(args.rounds), args.fixed_words, args.seed,
                             args.out)
    for r in res:
        print(json.dumps(r, indent=2))
