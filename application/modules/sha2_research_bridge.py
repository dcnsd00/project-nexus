"""NEXUS bridge to the independently supplied SHA-2 research package.

Only exact SHA-256d primitives are exposed to mining code. Reduced-round,
SAT and differential routines remain research-only and cannot launch miners.
"""
from __future__ import annotations
import hashlib, importlib.util, struct, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESEARCH_ROOT = ROOT / "research" / "sha2_independent"


def _load_sha256_module():
    path = RESEARCH_ROOT / "nexus_sha" / "sha256_advanced.py"
    if not path.is_file():
        raise RuntimeError(f"Pachetul SHA-2 independent lipsește: {path}")
    spec = importlib.util.spec_from_file_location("nexus_independent_sha256", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Nu se poate încărca modulul SHA-256 independent.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def double_sha256_reference(header: bytes) -> bytes:
    if not isinstance(header, bytes) or len(header) != 80:
        raise ValueError("Header-ul Bitcoin trebuie să fie bytes și să aibă 80 bytes.")
    return hashlib.sha256(hashlib.sha256(header).digest()).digest()


class ExactBitcoinMidstate:
    """SHA-256d midstate adapter; nonce serialization follows Bitcoin LE bytes."""
    def __init__(self, header: bytes):
        if not isinstance(header, bytes) or len(header) != 80:
            raise ValueError("Header-ul Bitcoin trebuie să aibă exact 80 bytes.")
        self._module = _load_sha256_module()
        self._template = bytearray(header)
        self._miner = self._module.MidstateMiner(header)

    def hash_nonce(self, nonce: int) -> bytes:
        if isinstance(nonce, bool) or not isinstance(nonce, int) or not 0 <= nonce <= 0xffffffff:
            raise ValueError("Nonce trebuie să fie uint32.")
        got = self._miner.hash_header(nonce)
        check = bytearray(self._template)
        check[76:80] = struct.pack("<I", nonce)
        # Guardrail: exact reference comparison; may be disabled only in a future
        # separately benchmarked production backend, never silently here.
        expected = double_sha256_reference(bytes(check))
        if got != expected:
            raise RuntimeError("Midstate SHA-256d nu coincide cu referința hashlib; rezultat blocat.")
        return got

    def benchmark(self, nonces: int = 1000) -> dict:
        if isinstance(nonces, bool) or not isinstance(nonces, int) or not 1 <= nonces <= 100000:
            raise ValueError("nonces trebuie să fie între 1 și 100000.")
        start = time.perf_counter()
        for nonce in range(nonces):
            self.hash_nonce(nonce)
        elapsed = time.perf_counter() - start
        return {"nonces": nonces, "seconds": round(elapsed, 6),
                "hashrate_hs": round(nonces / elapsed, 2) if elapsed else None,
                "verified_against_hashlib": True,
                "classification": "correctness_guarded_python_benchmark_not_gpu_or_pool_mining"}


def research_status() -> dict:
    return {
        "package_present": (RESEARCH_ROOT / "nexus_sha" / "sha256_advanced.py").is_file(),
        "exact_sha256d_available": True,
        "reduced_round_tools_are_research_only": True,
        "reduced_round_results_enable_consensus_mining": False,
        "integration_scope": "CPU-side exact Bitcoin header SHA-256d reference/benchmark; not yet wired into a production Stratum miner"
    }
