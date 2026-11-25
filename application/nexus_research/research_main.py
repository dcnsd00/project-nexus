#!/usr/bin/env python3
"""
NEXUS - orchestratorul cercetarii SHA-256 / SHA-512.

Rulare completa (toate experimentele, ~30-60 min):
    python research_main.py all

Subcomenzi: test, avalanche, stats, differential, msgmod, sat, benchmark, verify
Optiuni: --seed, --time-budget, --out-dir, --quick
"""

import argparse
import json
import os
import sys
import time
import unittest


def run_tests():
    loader = unittest.TestLoader()
    from nexus_sha import tests
    suite = loader.loadTestsFromModule(tests)
    runner = unittest.TextTestRunner(verbosity=2)
    res = runner.run(suite)
    return res.wasSuccessful()


def cmd_test(args):
    return run_tests()


def cmd_stats(args):
    from nexus_sha import stats_analysis
    res = stats_analysis.run(out_json=os.path.join(args.out_dir, "stats.json"),
                             seed=args.seed, quick=args.quick)
    print(json.dumps({k: (v if k != "avalanche" else
                          {kk: vv for kk, vv in v.items()
                           if kk != "avg_flipped_bits_per_round"})
                      for k, v in res.items()}, indent=2)[:2000])
    return True


def cmd_avalanche(args):
    from nexus_sha import stats_analysis
    res = stats_analysis.avalanche_per_round(seed=args.seed)
    print("biti schimbati/medie per runda (256 = stare completa):")
    for r, v in enumerate(res["avg_flipped_bits_per_round"]):
        bar = "#" * int(v / 2)
        print(f"  runda {r:2d}: {v:6.1f} {bar}")
    with open(os.path.join(args.out_dir, "avalanche.json"), "w") as fh:
        json.dump(res, fh, indent=2)
    return True


def cmd_differential(args):
    from nexus_sha import differential_search
    rounds = [3, 4, 5, 6] if not args.quick else [3, 4]
    differential_search.run_experiment(
        rounds_list=rounds,
        n_search=800 if args.quick else 1500,
        n_validation=5000 if args.quick else 20000,
        seed=args.seed,
        time_limit_per_round=args.time_budget / len(rounds),
        out_json=os.path.join(args.out_dir, "differential.json"))
    return True


def cmd_msgmod(args):
    from nexus_sha import message_modification
    res = message_modification.run(
        out_json=os.path.join(args.out_dir, "message_modification.json"),
        seed=args.seed)
    print(json.dumps(res, indent=2))
    return True


def cmd_sat(args):
    from nexus_sha import sat_smt_solver
    rounds = [6, 8, 10] if args.quick else [6, 8, 10, 12]
    sat_smt_solver.scaling_experiment(
        rounds_list=rounds, n_words_fixed=1, seed=args.seed,
        out_json=os.path.join(args.out_dir, "sat_scaling.json"))
    return True


def cmd_benchmark(args):
    from nexus_sha import benchmark
    res = benchmark.run(
        n_nonces=2000 if args.quick else 20000,
        seed=args.seed,
        out_json=os.path.join(args.out_dir, "benchmark.json"))
    print(json.dumps(res, indent=2))
    return True


def cmd_verify(args):
    from nexus_sha import verify_results
    return verify_results.run(args.out_dir)


def cmd_all(args):
    ok = True
    for fn in (cmd_test, cmd_stats, cmd_avalanche, cmd_differential,
               cmd_msgmod, cmd_sat, cmd_benchmark, cmd_verify):
        print(f"\n{'='*70}\n>>> {fn.__name__}\n{'='*70}")
        try:
            ok &= bool(fn(args))
        except Exception as e:
            print(f"EROARE in {fn.__name__}: {e}")
            ok = False
    return ok


def main():
    ap = argparse.ArgumentParser(description="NEXUS research orchestrator")
    ap.add_argument("command", choices=["test", "stats", "avalanche",
                                       "differential", "msgmod", "sat",
                                       "benchmark", "verify", "all"])
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--time-budget", type=float, default=180.0,
                    help="buzet total (s) pentru cautari")
    ap.add_argument("--out-dir", default="results")
    ap.add_argument("--quick", action="store_true", help="versiune rapida")
    args = ap.parse_args()
    os.makedirs(args.out_dir, exist_ok=True)
    t0 = time.time()
    cmds = {"test": cmd_test, "stats": cmd_stats, "avalanche": cmd_avalanche,
            "differential": cmd_differential, "msgmod": cmd_msgmod,
            "sat": cmd_sat, "benchmark": cmd_benchmark,
            "verify": cmd_verify, "all": cmd_all}
    ok = cmds[args.command](args)
    print(f"\nFinal: {'OK' if ok else 'ESUARI PREZENTE'} "
          f"({time.time()-t0:.1f}s, seed={args.seed})")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
