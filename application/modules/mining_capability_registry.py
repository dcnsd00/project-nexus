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
    "Blake3": AlgorithmProfile("Blake3", "blake3", (), (), (), "catalog_only", "Pool catalog entry exists; device/backend/protocol contract is not yet validated."),
    "Equihash-125-4": AlgorithmProfile("Equihash-125-4", "equihash", (), (), (), "catalog_only", "Pool catalog entry exists; device/backend/protocol contract is not yet validated."),
    "Equihash": AlgorithmProfile("Equihash", "equihash", (), (), (), "catalog_only", "Pool catalog entry exists; device/backend/protocol contract is not yet validated."),
    "X11": AlgorithmProfile("X11", "x11", (), (), (), "catalog_only", "Pool catalog entry exists; device/backend/protocol contract is not yet validated."),
    "Eaglesong": AlgorithmProfile("Eaglesong", "eaglesong", (), (), (), "catalog_only", "Pool catalog entry exists; device/backend/protocol contract is not yet validated."),
    "NexaPow": AlgorithmProfile("NexaPow", "nexapow", (), (), (), "catalog_only", "Pool catalog entry exists; device/backend/protocol contract is not yet validated."),
    "Octopus": AlgorithmProfile("Octopus", "octopus", (), (), (), "catalog_only", "Pool catalog entry exists; device/backend/protocol contract is not yet validated."),
    "Ethash": AlgorithmProfile("Ethash", "ethash_dag", (), (), (), "catalog_only", "Pool catalog entry exists; device/backend/protocol contract is not yet validated."),
    "Blake2s-Kadena": AlgorithmProfile("Blake2s-Kadena", "blake2s", (), (), (), "catalog_only", "Pool catalog entry exists; device/backend/protocol contract is not yet validated."),
    "Blake2b-Sia": AlgorithmProfile("Blake2b-Sia", "blake2b", (), (), (), "catalog_only", "Pool catalog entry exists; device/backend/protocol contract is not yet validated."),
    "zkSNARK": AlgorithmProfile("zkSNARK", "proof_system", (), (), (), "catalog_only", "Not treated as a generic PoW miner algorithm; requires a coin-specific proving backend."),
    "Blake2b": AlgorithmProfile("Blake2b", "blake2b", (), (), (), "catalog_only", "Pool catalog entry exists; device/backend/protocol contract is not yet validated."),
    "XelisHash": AlgorithmProfile("XelisHash", "xelishash", (), (), (), "catalog_only", "Pool catalog entry exists; device/backend/protocol contract is not yet validated."),
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


_BACKEND_ID_ALIASES = {
    "cgminer": "cgminer", "bfgminer": "bfgminer",
    "srbminer-multi": "srbminer", "xmrig": "xmrig",
    "t-rex": "trex", "gminer": "gminer", "rigel": "rigel",
    "lolminer": "lolminer", "verthashminer": "verthashminer",
    "nerdminer": "nerdminer",
}


def compatibility_matrix(pools_path: str | Path, backend_specs: list[dict[str, Any]]) -> dict[str, Any]:
    """Build a static pool × algorithm × backend × device map; no live claims."""
    path = Path(pools_path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows = []
    for pool in payload.get("pools", []):
        algorithm = normalize_algorithm(str(pool.get("algorithm", "")))
        profile = algorithm_profile(algorithm)
        candidates = profile.get("backend_candidates", [])
        devices = profile.get("device_classes", [])
        backend_matches = []
        for candidate in candidates:
            backend_id = _BACKEND_ID_ALIASES.get(candidate.casefold())
            backend = next((item for item in backend_specs if item.get("backend_id") == backend_id), None)
            if backend is None:
                continue
            supported_devices = sorted(set(devices).intersection(backend.get("device_classes", [])))
            if supported_devices:
                backend_matches.append({
                    "backend_id": backend_id,
                    "backend_name": backend.get("display_name"),
                    "device_classes": supported_devices,
                    "match_status": "profile_match_only",
                    "executable_presence_checked": False,
                    "pool_connection_checked": False,
                })
        if profile.get("status") == "catalog_only":
            status = "catalog_only"
        elif backend_matches:
            status = "profiled_backend_candidates"
        else:
            status = "no_backend_profile_match"
        rows.append({
            "pool_id": pool.get("id"),
            "pool_name": pool.get("name") or pool.get("pool"),
            "coin": pool.get("coin"),
            "algorithm": algorithm,
            "algorithm_status": profile.get("status"),
            "device_classes": devices,
            "backend_matches": backend_matches,
            "status": status,
            "pool_reachable": None,
            "authorized": None,
            "job_received": None,
            "share_accepted": None,
            "payout_verified": None,
        })
    counts: dict[str, int] = {}
    for row in rows:
        counts[row["status"]] = counts.get(row["status"], 0) + 1
    return {
        "pool_profile_count": len(rows),
        "status_counts": counts,
        "entries": rows,
        "is_static_profile_matrix": True,
        "live_pool_checks_performed": False,
        "execution_enabled": False,
    }
