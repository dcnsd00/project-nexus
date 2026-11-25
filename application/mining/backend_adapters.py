"""Algorithm-specific miner backend contracts.

This layer describes backend identity, executable discovery, launch-plan validation
and telemetry normalization. It does not launch processes, contact pools, or persist
credentials. A discovered executable is not proof of pool or share compatibility.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import math
import os
import shutil
from typing import Any, Callable


@dataclass(frozen=True)
class BackendSpec:
    backend_id: str
    display_name: str
    algorithms: tuple[str, ...]
    device_classes: tuple[str, ...]
    executable_names: tuple[str, ...]
    integration_kind: str = "external_process"
    config_format: str = "argv"
    notes: str = ""


BACKENDS: dict[str, BackendSpec] = {
    "xmrig": BackendSpec("xmrig", "XMRig", ("RandomX",), ("CPU",), ("xmrig", "xmrig.exe"), notes="CPU RandomX backend; memory and huge-page requirements remain runtime checks."),
    "srbminer": BackendSpec("srbminer", "SRBMiner-MULTI", ("RandomX", "Scrypt", "KawPoW", "Etchash", "KHeavyHash", "Verthash", "PearlPow"), ("CPU", "GPU"), ("SRBMiner-MULTI", "SRBMiner-MULTI.exe"), notes="Algorithm and device support must be checked against the installed release."),
    "cgminer": BackendSpec("cgminer", "CGMiner", ("SHA-256d", "Scrypt"), ("ASIC",), ("cgminer", "cgminer.exe"), notes="ASIC support is device/firmware-specific."),
    "bfgminer": BackendSpec("bfgminer", "BFGMiner", ("SHA-256d", "Scrypt"), ("ASIC",), ("bfgminer", "bfgminer.exe"), notes="ASIC support is device/firmware-specific."),
    "trex": BackendSpec("trex", "T-Rex", ("KawPoW",), ("GPU",), ("t-rex", "t-rex.exe"), notes="NVIDIA and driver compatibility must be checked."),
    "gminer": BackendSpec("gminer", "Gminer", ("KawPoW", "Etchash"), ("GPU",), ("miner", "miner.exe"), notes="Executable name may collide; operator must confirm the resolved binary."),
    "rigel": BackendSpec("rigel", "Rigel", ("KawPoW",), ("GPU",), ("rigel", "rigel.exe")),
    "lolminer": BackendSpec("lolminer", "lolMiner", ("Etchash", "KHeavyHash"), ("GPU",), ("lolMiner", "lolMiner.exe")),
    "verthashminer": BackendSpec("verthashminer", "VerthashMiner", ("Verthash",), ("GPU",), ("verthashminer", "verthashminer.exe")),
    "nerdminer": BackendSpec("nerdminer", "NerdMiner", ("SHA-256d",), ("ESP32",), (), integration_kind="device_protocol", config_format="device_profile", notes="External ESP32 firmware/device integration; no local executable assumed."),
    "asic_firmware": BackendSpec("asic_firmware", "ASIC firmware interface", ("SHA-256d", "Scrypt", "KHeavyHash"), ("ASIC",), (), integration_kind="device_protocol", config_format="device_profile", notes="Requires a device-specific API adapter and explicit authorization."),
}


def backend_catalog() -> list[dict[str, Any]]:
    return [asdict(BACKENDS[key]) for key in sorted(BACKENDS)]


def discover_backends(which: Callable[[str], str | None] = shutil.which) -> list[dict[str, Any]]:
    """Discover candidate binaries. Discovery is not execution or compatibility proof."""
    found = []
    for spec in BACKENDS.values():
        resolved = None
        matched_name = None
        for name in spec.executable_names:
            candidate = which(name)
            if candidate:
                resolved, matched_name = os.path.abspath(candidate), name
                break
        found.append({
            "backend_id": spec.backend_id,
            "display_name": spec.display_name,
            "integration_kind": spec.integration_kind,
            "available": bool(resolved) if spec.executable_names else False,
            "resolved_executable": resolved,
            "matched_name": matched_name,
            "discovery_status": "executable_found" if resolved else (
                "device_adapter_required" if spec.integration_kind == "device_protocol" else "executable_missing"
            ),
            "operationally_validated": False,
        })
    return found


def evaluate_backend(backend_id: str, algorithm: str, device_class: str) -> dict[str, Any]:
    spec = BACKENDS.get(str(backend_id).casefold())
    if spec is None:
        return {"compatible": False, "status": "unknown_backend", "reasons": ["backend_not_registered"]}
    reasons = []
    if algorithm not in spec.algorithms:
        reasons.append("algorithm_not_supported_by_backend_profile")
    device = str(device_class).upper()
    if device not in spec.device_classes:
        reasons.append("device_class_not_supported_by_backend_profile")
    return {
        "compatible": not reasons,
        "backend_id": spec.backend_id,
        "algorithm": algorithm,
        "device_class": device,
        "integration_kind": spec.integration_kind,
        "config_format": spec.config_format,
        "reasons": reasons,
        "execution": "evaluation_only",
        "does_not_start_miner": True,
    }


def validate_launch_plan(backend_id: str, executable: str, argv: list[str]) -> dict[str, Any]:
    """Validate a proposed argv plan without executing it."""
    spec = BACKENDS.get(str(backend_id).casefold())
    reasons = []
    if spec is None:
        reasons.append("backend_not_registered")
    if not isinstance(executable, str) or not executable or not os.path.isabs(executable):
        reasons.append("executable_must_be_absolute_path")
    elif not os.path.isfile(executable):
        reasons.append("executable_file_missing")
    if spec is not None and spec.executable_names and os.path.basename(executable).casefold() not in {
        name.casefold() for name in spec.executable_names
    }:
        reasons.append("executable_name_not_allowlisted")
    if not isinstance(argv, list) or not argv or any(not isinstance(x, str) or "\x00" in x for x in argv):
        reasons.append("argv_must_be_nonempty_string_list")
    elif argv and os.path.abspath(argv[0]) != os.path.abspath(executable):
        reasons.append("argv_executable_mismatch")
    return {
        "valid": not reasons,
        "backend_id": spec.backend_id if spec else None,
        "executable": executable if isinstance(executable, str) else None,
        "argv_count": len(argv) if isinstance(argv, list) else 0,
        "shell": False,
        "secrets_persisted": False,
        "reasons": reasons,
        "execution": "validation_only",
    }


def normalize_telemetry(backend_id: str, raw: dict[str, Any]) -> dict[str, Any]:
    """Map common backend metric aliases into a bounded NEXUS telemetry shape."""
    if backend_id not in BACKENDS:
        raise ValueError("unknown backend")
    def number(*keys: str) -> float | None:
        for key in keys:
            value = raw.get(key)
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                try:
                    numeric = float(value)
                except (OverflowError, ValueError):
                    continue
                if math.isfinite(numeric) and numeric >= 0:
                    return numeric
        return None
    def count(*keys: str) -> int | None:
        value = number(*keys)
        return int(value) if value is not None else None
    return {
        "backend_id": backend_id,
        "hashrate_hs": number("hashrate_hs", "hashrate", "hash_rate"),
        "accepted_shares": count("accepted_shares", "accepted", "shares_accepted"),
        "rejected_shares": count("rejected_shares", "rejected", "shares_rejected"),
        "temperature_c": number("temperature_c", "temperature", "temp"),
        "power_w": number("power_w", "power", "watts"),
        "pool_connected": raw.get("pool_connected") if isinstance(raw.get("pool_connected"), bool) else None,
        "authorized": raw.get("authorized") if isinstance(raw.get("authorized"), bool) else None,
        "source_backend": backend_id,
    }
