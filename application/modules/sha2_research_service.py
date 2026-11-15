"""NEXUS API service for the independent SHA-256/SHA-512 research package.

All reduced-round experiments are research-only. Exact full-round primitives are
verified against hashlib. Nothing here changes or starts a miner.
"""
from __future__ import annotations

import contextlib
import io
import os
import json
import secrets
import threading
import time
import unittest
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from modules.data_paths import data_path
from research.sha2_independent import nexus_sha
from research.sha2_independent.nexus_sha import (
    benchmark as sha_benchmark,
    differential_search,
    message_modification,
    sat_smt_solver,
    sha256_advanced,
    sha512_advanced,
    stats_analysis,
    verify_results,
)

ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ROOT = ROOT / "research" / "sha2_independent"
RESULTS_ROOT = Path(os.environ.get("NEXUS_SHA2_RESULTS_DIR", str(data_path("research", "sha2", "runs"))))
VERIFICATION_RESULTS_ROOT = Path(os.environ.get("NEXUS_SHA2_VERIFICATION_RESULTS_DIR", str(data_path("research", "sha2", "verification"))))
_RUN_LOCK = threading.Lock()


class ResearchDependencyError(RuntimeError):
    pass


def _save(kind: str, result: dict[str, Any]) -> dict[str, Any]:
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S") + "_" + secrets.token_hex(5)
    payload = {
        "run_id": run_id,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "kind": kind,
        "result": result,
        "classification": "research_only" if kind in {"differential", "message_modification", "sat"} else "measurement",
        "miner_auto_apply": False,
        "network_access": False,
    }
    RESULTS_ROOT.mkdir(parents=True, exist_ok=True)
    target = RESULTS_ROOT / f"{run_id}.json"
    temporary = target.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(target)
    try:
        saved_to = str(target.relative_to(ROOT))
    except ValueError:
        saved_to = str(target)
    return {"run_id": run_id, "saved_to": saved_to, "result": result}


def status() -> dict[str, Any]:
    return {
        "package": "NEXUS independent SHA-2 research",
        "package_version": nexus_sha.__version__,
        "canonical_path": str(PACKAGE_ROOT.relative_to(ROOT)),
        "present": (PACKAGE_ROOT / "nexus_sha" / "sha256_advanced.py").is_file(),
        "modules": {
            "sha256_reference": True,
            "sha512_reference": True,
            "differential_search_reduced_round": True,
            "message_modification_reduced_round": True,
            "sat_cnf_encoder": True,
            "independent_verifier": True,
            "reproducible_benchmark": True,
            "statistical_analysis": True,
        },
        "backends": {
            "python_sat": bool(sat_smt_solver.PYSAT_AVAILABLE),
            "z3": _has_z3(),
            "gcc": _has_tool("gcc"),
            "cuda_nvcc": _has_tool("nvcc"),
        },
        "guardrails": [
            "Reduced-round results are not SHA-256/SHA-512 full-round attacks.",
            "Research candidates are never injected into consensus mining.",
            "No miner is started and no pool/network is contacted.",
            "Exact hash results are checked against hashlib.",
        ],
        "saved_runs": len(list(RESULTS_ROOT.glob("*.json"))) if RESULTS_ROOT.is_dir() else 0,
    }


def _has_tool(name: str) -> bool:
    import shutil
    return shutil.which(name) is not None


def _has_z3() -> bool:
    try:
        import z3  # noqa: F401
        return True
    except ImportError:
        return False


def run_selftest() -> dict[str, Any]:
    with _RUN_LOCK:
        suite = unittest.defaultTestLoader.loadTestsFromModule(
            __import__("research.sha2_independent.nexus_sha.tests", fromlist=["tests"])
        )
        stream = io.StringIO()
        result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
    return {
        "tests_run": result.testsRun,
        "failures": len(result.failures),
        "errors": len(result.errors),
        "skipped": len(result.skipped),
        "successful": result.wasSuccessful(),
        "output": stream.getvalue()[-12000:],
        "note": "SAT solve test is skipped when python-sat is not installed; SAT encoding remains available for export/self-check.",
    }


def run_benchmark(n_nonces: int = 2000, seed: int = 42) -> dict[str, Any]:
    if isinstance(n_nonces, bool) or not isinstance(n_nonces, int) or not 100 <= n_nonces <= 10000:
        raise ValueError("n_nonces trebuie să fie între 100 și 10000.")
    if isinstance(seed, bool) or not isinstance(seed, int) or not 0 <= seed <= 2**32 - 1:
        raise ValueError("seed invalid.")
    with _RUN_LOCK:
        start = time.perf_counter()
        result = sha_benchmark.run(n_nonces=n_nonces, seed=seed)
        result["elapsed_wall_seconds"] = round(time.perf_counter() - start, 6)
        result["scope"] = "Python CPU research benchmark; not the user's miner, not GPU, not live pool mining"
        result["nonce_serialization"] = "Bitcoin uint32 little-endian"
        result["exactness_guard"] = "naive == midstate == hashlib on sampled nonces"
    return _save("exact_midstate_benchmark", result)


def run_avalanche(seed: int = 42, samples: int = 32) -> dict[str, Any]:
    if not 1 <= samples <= 128:
        raise ValueError("samples trebuie să fie între 1 și 128.")
    if not 0 <= seed <= 2**32 - 1:
        raise ValueError("seed invalid.")
    payload = secrets.token_bytes(64) if seed is None else __import__("random").Random(seed).randbytes(64)
    with _RUN_LOCK:
        result = sha512_advanced.avalanche_comparison(payload, seed=seed, samples=samples)
    result["classification"] = "full-round internal-state diffusion comparison"
    result["does_not_imply"] = "No shortcut or mining speedup is established by avalanche measurements."
    return _save("sha256_sha512_avalanche", result)


def run_statistics(seed: int = 42, samples: int = 2000) -> dict[str, Any]:
    if not 100 <= samples <= 10000:
        raise ValueError("samples trebuie să fie între 100 și 10000.")
    if not 0 <= seed <= 2**32 - 1:
        raise ValueError("seed invalid.")
    with _RUN_LOCK:
        result = {
            "monobit": stats_analysis.monobit_test(n=samples, seed=seed),
            "input_output_correlation": stats_analysis.input_output_correlation(
                n=min(samples, 250), seed=seed, n_input_bits=32),
            "nonce_independence": stats_analysis.nonce_independence(n=samples, seed=seed),
            "avalanche_sha256": stats_analysis.avalanche_per_round(samples=min(128, max(16, samples // 16)), seed=seed),
        }
    result["interpretation"] = "Statistical tests can detect selected deviations; passing does not prove cryptographic security."
    return _save("sha2_statistics", result)


def run_differential(rounds: list[int] | None = None, seed: int = 42,
                     search_samples: int = 300, validation_samples: int = 2000,
                     time_budget_seconds: float = 8.0) -> dict[str, Any]:
    rounds = rounds or [3, 4]
    if not rounds or len(rounds) > 4 or any(isinstance(r, bool) or not isinstance(r, int) or r not in range(3, 7) for r in rounds):
        raise ValueError("Rundele admise pentru această căutare sunt 3–6, maximum 4 valori.")
    if not 50 <= search_samples <= 1000 or not 100 <= validation_samples <= 5000:
        raise ValueError("Bugetul de eșantioane este în afara limitelor NEXUS.")
    if not 0.5 <= float(time_budget_seconds) <= 20:
        raise ValueError("time_budget_seconds trebuie să fie între 0.5 și 20.")
    with _RUN_LOCK:
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            results = differential_search.run_experiment(
                rounds_list=tuple(rounds), n_search=search_samples,
                n_validation=validation_samples, seed=seed,
                time_limit_per_round=float(time_budget_seconds) / len(rounds),
            )
    return _save("differential", {
        "rounds": rounds, "seed": seed, "results": results,
        "console": out.getvalue(),
        "scope": "reduced-round compression only; no inference to full SHA-256 or mining",
    })


def run_message_modification(seed: int = 42, samples: int = 1000, k_bits: int = 8) -> dict[str, Any]:
    if not 100 <= samples <= 10000 or not 1 <= k_bits <= 16:
        raise ValueError("samples 100–10000 și k_bits 1–16 sunt admise.")
    with _RUN_LOCK:
        result = message_modification.experiment_e1(n=samples, seed=seed, k_bits=k_bits)
    result["scope"] = "deterministic state control in reduced-round SHA-256 only"
    result["mining_optimization"] = False
    return _save("message_modification", result)


def run_message_modification_e2(rounds: int = 2, seed: int = 42,
                                n_learn: int = 500, n_test: int = 500,
                                k_cond: int = 4) -> dict[str, Any]:
    if rounds not in (2, 3):
        raise ValueError("E2 este permis doar la 2 sau 3 runde.")
    if not 100 <= n_learn <= 1000 or not 100 <= n_test <= 1000 or not 1 <= k_cond <= 8:
        raise ValueError("Limite: n_learn/n_test 100–1000, k_cond 1–8.")
    with _RUN_LOCK:
        result = message_modification.experiment_e2(
            rounds=rounds, n_learn=n_learn, n_test=n_test,
            seed=seed, k_cond=k_cond,
        )
    result["scope"] = "experimental reduced-round heuristic; validation is a holdout sample"
    result["mining_optimization"] = False
    return _save("message_modification_e2", result)


def run_sat_solve(rounds: int = 6, seed: int = 42) -> dict[str, Any]:
    if not 2 <= rounds <= 16:
        raise ValueError("SAT experimental admis pentru 2–16 runde.")
    if not sat_smt_solver.PYSAT_AVAILABLE:
        raise ResearchDependencyError("python-sat nu este instalat. Instalează requirements-research.txt pentru rezolvare SAT reală; nu voi substitui solverul cu rezultate simulate.")
    with _RUN_LOCK:
        result = sat_smt_solver.solve_partial_preimage(rounds, {0: 0}, seed=seed, verbose=False)
    if result.get("status") == "SAT" and not result.get("independent_verification", {}).get("matches_target"):
        raise RuntimeError("Soluția SAT nu a trecut verificarea independentă; rezultatul a fost respins.")
    return _save("sat", result)


def run_verification() -> dict[str, Any]:
    VERIFICATION_RESULTS_ROOT.mkdir(parents=True, exist_ok=True)
    with _RUN_LOCK:
        stream = io.StringIO()
        with contextlib.redirect_stdout(stream):
            ok = verify_results.run(str(VERIFICATION_RESULTS_ROOT))
    return {
        "successful": bool(ok),
        "output": stream.getvalue()[-16000:],
        "scope": "re-verification of stored research results and fresh samples",
        "sat_solver_available": bool(sat_smt_solver.PYSAT_AVAILABLE),
    }
