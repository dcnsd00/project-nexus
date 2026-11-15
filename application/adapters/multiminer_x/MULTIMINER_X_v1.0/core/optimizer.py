"""Small deterministic optimizer for CPU thread budget and benchmark comparisons."""
from __future__ import annotations
from .mining_math import split_cpu_threads, amdahl_speedup


def cpu_thread_plan(logical_threads: int, target_percent: int = 50,
                    parallel_fraction: float = 0.95) -> dict:
    workers = split_cpu_threads(logical_threads, target_percent)
    return {"logical_threads": logical_threads, "target_percent": target_percent,
            "worker_threads": workers,
            "amdahl_speedup_vs_one_worker": amdahl_speedup(parallel_fraction, workers),
            "note": "Estimare teoretică Amdahl; XMRig max-threads-hint este doar un indiciu pentru auto-config, nu limitator de putere exact."}
