"""Shared mining capability registry for algorithm-specific backends.

The registry separates algorithm identity, backend requirements and common NEXUS
services. Catalog presence is not proof of miner or pool compatibility.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
import json
from typing import Any


@dataclass(frozen=True)
class AlgorithmProfile:
    algorithm_id: str
    family: str
    device_classes: tuple[str, ...]
    protocol_families: tuple[str, ...]
    backend_candidates: tuple[str, ...]
    status: str
    notes: str


# Only explicit profiles are listed. "research_only" means no production mining
# claim; backend_candidates are candidates, not proof of installed executables.
ALGORITHM_PROFILES: dict[str, AlgorithmProfile] = {
    "SHA-256d": AlgorithmProfile("SHA-256d", "sha2", ("ASIC", "CPU", "ESP32"), ("stratum_v1",), ("CGMiner", "Braiins OS", "NEXUS BTC CPU", "NerdMiner"), "profiled", "GPU consumer support is not assumed."),
    "Scrypt": AlgorithmProfile("Scrypt", "scrypt", ("ASIC", "CPU", "GPU"), ("stratum_v1",), ("CGMiner", "BFGMiner", "SRBMiner-MULTI"), "profiled", "Merged mining and payout asset rules are pool-specific."),
    "RandomX": AlgorithmProfile("RandomX", "randomx", ("CPU",), ("stratum_v1",), ("XMRig", "SRBMiner-MULTI"), "profiled", "CPU-oriented; memory requirements must be checked per backend."),
    "KawPoW": AlgorithmProfile("KawPoW", "progpow", ("GPU",), ("stratum_v1",), ("T-Rex", "Gminer", "Rigel", "SRBMiner-MULTI"), "profiled", "GPU model, driver and VRAM are runtime constraints."),
    "Etchash": AlgorithmProfile("Etchash", "ethash_dag", ("GPU",), ("stratum_v1",), ("lolMiner", "Gminer", "SRBMiner-MULTI"), "profiled", "DAG/VRAM and driver compatibility must be measured."),
    "KHeavyHash": AlgorithmProfile("KHeavyHash", "kheavyhash", ("ASIC", "GPU"), ("stratum_v1",), ("IceRiver ASIC", "Bitmain ASIC", "lolMiner", "SRBMiner-MULTI"), "profiled", "GPU support varies by coin, miner build and device."),
    "Verthash": AlgorithmProfile("Verthash", "verthash", ("GPU",), ("stratum_v1",), ("VerthashMiner", "SRBMiner-MULTI", "TeamBlackMiner"), "profiled", "Algorithm dataset and VRAM are backend-specific."),
    "PearlPow": AlgorithmProfile("PearlPow", "pearlpow", ("GPU",), ("stratum_v1",), ("SRBMiner-MULTI",), "profiled", "Validate exact miner version and pool endpoint before use."),
    "SHA-512": AlgorithmProfile("SHA-512", "sha2", ("CPU",), (), ("OpenSSL", "Python hashlib"), "research_only", "Digest benchmark only; not a supported PoW pool algorithm."),
    "SHA-3": AlgorithmProfile("SHA-3", "sha3", ("CPU",), (), ("OpenSSL", "Python hashlib"), "research_only", "Digest benchmark only; not a supported PoW pool algorithm."),
    "BLAKE2": AlgorithmProfile("BLAKE2", "blake", ("CPU",), (), ("OpenSSL", "Python hashlib"), "research_only", "Digest benchmark only; not a supported PoW pool algorithm."),
}


COMMON_NEXUS_SERVICES = (
    "crypto_engine",
    "math_intelligence",
    "research_hub",
    "earnings_intelligence",
    "mining_optimization",
    "mining_switch_controller",
    "provider_registry",
    "telemetry",
    "audit_log",
    "hardware_inventory",
    "pool_registry",
    "wallet_read_only",
)


def normalize_algorithm(value: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("algorithm is required")
    raw = value.strip()
    aliases = {
        "sha256d": "SHA-256d", "sha-256d": "SHA-256d",
        "randomx": "RandomX", "rx/0": "RandomX",
        "kawpow": "KawPoW", "etchash": "Etchash",
        "kheavyhash": "KHeavyHash", "verthash": "Verthash",
        "pearlpow": "PearlPow", "pearlhash": "PearlPow",
        "scrypt": "Scrypt", "sha512": "SHA-512",
        "sha-512": "SHA-512", "sha3": "SHA-3",
        "sha-3": "SHA-3", "blake2": "BLAKE2",
    }
    return aliases.get(raw.casefold(), raw)


def algorithm_profile(algorithm: str) -> dict[str, Any]:
    key = normalize_algorithm(algorithm)
    profile = ALGORITHM_PROFILES.get(key)
    if profile is None:
        return {
            "algorithm_id": key, "status": "unknown_requires_adapter",
            "production_supported": False, "device_classes": [],
            "protocol_families": [], "backend_candidates": [],
            "notes": "No verified NEXUS algorithm profile exists yet.",
        }
    data = asdict(profile)
    data["device_classes"] = list(profile.device_classes)
    data["protocol_families"] = list(profile.protocol_families)
    data["backend_candidates"] = list(profile.backend_candidates)
    data["production_supported"] = profile.status == "profiled"
    return data


def evaluate_capability(
    algorithm: str,
    device: str,
    miner_id: str,
    pool: dict[str, Any] | None = None,
    installed_backends: list[str] | None = None,
) -> dict[str, Any]:
    profile = algorithm_profile(algorithm)
    device_key = str(device).upper()
    reasons: list[str] = []
    if not profile["production_supported"]:
        reasons.append("algorithm_not_production_profiled")
    if device_key not in profile["device_classes"]:
        reasons.append("device_class_not_supported_by_algorithm_profile")
    if pool is not None:
        pool_algo = normalize_algorithm(str(pool.get("algorithm", "")))
        if pool_algo != profile["algorithm_id"]:
            reasons.append("pool_algorithm_mismatch")
        if pool.get("selectable") is False:
            reasons.append("pool_profile_not_selectable")
        protocol = str(pool.get("stratum_protocol", "V1")).upper()
        if protocol == "V1" and "stratum_v1" not in profile["protocol_families"]:
            reasons.append("stratum_v1_not_supported_by_algorithm_profile")
    installed = set(installed_backends or [])
    candidates = set(profile["backend_candidates"])
    backend_available = bool(installed & candidates)
    if installed_backends is not None and not backend_available:
        reasons.append("no_matching_backend_detected")
    return {
        "compatible": not reasons,
        "algorithm": profile["algorithm_id"],
        "family": profile.get("family"),
        "device": device_key,
        "miner_id": miner_id,
        "pool_id": pool.get("id") if pool else None,
        "backend_candidates": profile["backend_candidates"],
        "matching_backend_detected": backend_available if installed_backends is not None else None,
        "common_nexus_services": list(COMMON_NEXUS_SERVICES),
        "reasons": reasons,
        "execution": "capability_evaluation_only",
        "does_not_start_miner": True,
    }


def catalog_coverage(pools_path: str | Path) -> dict[str, Any]:
    path = Path(pools_path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    pools = payload.get("pools", [])
    rows: dict[str, dict[str, Any]] = {}
    for pool in pools:
        algo = normalize_algorithm(str(pool.get("algorithm", "")))
        row = rows.setdefault(algo, {"algorithm": algo, "pool_profiles": 0, "pool_ids": [], "profile": algorithm_profile(algo)})
        row["pool_profiles"] += 1
        row["pool_ids"].append(pool.get("id"))
    return {
        "pool_profile_count": len(pools),
        "algorithm_count": len(rows),
        "algorithms": sorted(rows.values(), key=lambda x: x["algorithm"]),
        "catalog_is_live_validation": False,
    }
