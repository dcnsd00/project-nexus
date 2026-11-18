"""Opt-in, offline NEXUS hardware benchmark with measured thermal telemetry.

No pool connection, wallet access, miner autostart, overclock or configuration
changes are performed. Results are tied to the real host on which this script
is run and are stored as JSON for later comparison.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import platform
import statistics
import sys
import time
from typing import Any

APP_ROOT = Path(__file__).resolve().parents[1]
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from modules.runtime_telemetry import RuntimeTelemetry
from mining.native_sha256d import native_status, scan_nonce_range_native

# Bitcoin genesis header: a public, deterministic 80-byte test vector. The
# benchmark target is 1, so each backend must exhaust the requested range.
GENESIS_HEADER = bytes.fromhex(
    "010000000000000000000000000000000000000000000000000000000000000000000000"
    "3ba3edfd7a7b12b27ac72c3e67768f617fc81bc3888a51323a9fb8aa4b1e5e4a"
    "29ab5f49ffff001d1dac2b7c"
)
NO_SHARE_TARGET = 1
DEFAULT_THREADS = (1, 2, 4)
DEFAULT_VARIANT_NAMES = {
    0: "scalar_full_sha256d",
    1: "scalar_midstate",
    2: "scalar_midstate_early_exit",
    3: "avx2_x8",
    4: "avx512_x16",
}
MINING_PROCESS_TOKENS = (
    "xmrig", "srbminer", "verus", "cpuminer", "lolminer", "nbminer",
    "teamredminer", "gminer", "bminer", "trex", "wildrig", "rigel",
    "ccminer", "nanominer", "phoenixminer", "ethminer", "nexus-worker",
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_threads(value: str, logical_cpus: int) -> list[int]:
    try:
        requested = [int(part.strip()) for part in value.split(",") if part.strip()]
    except ValueError as exc:
        raise ValueError("threads must be a comma-separated list of integers") from exc
    if not requested or len(requested) > 8 or len(set(requested)) != len(requested):
        raise ValueError("threads must contain 1 to 8 unique values")
    if any(isinstance(item, bool) or item < 1 or item > min(256, logical_cpus)
           for item in requested):
        raise ValueError(f"each thread count must be between 1 and {min(256, logical_cpus)}")
    return requested


def _mining_processes(snapshot: dict[str, Any]) -> list[str]:
    found = []
    for item in snapshot.get("processes", {}).get("top", []) + snapshot.get("processes", {}).get("mining", []):
        name = str(item.get("name") or "")
        if any(token in name.casefold() for token in MINING_PROCESS_TOKENS):
            found.append(name)
    return sorted(set(found), key=str.casefold)


def _thermal_limit_reached(snapshot: dict[str, Any]) -> bool:
    thermal = snapshot.get("temperatures", {})
    for sensor in thermal.get("sensors", []):
        current = sensor.get("temperature_c")
        high = sensor.get("high_c")
        critical = sensor.get("critical_c")
        if current is None:
            continue
        if high is not None and current >= high:
            return True
        if critical is not None and current >= critical:
            return True
        if sensor.get("thermal_state") in {
            "at_or_above_sensor_high_threshold",
            "at_or_above_sensor_critical_threshold",
        }:
            return True
    for device in snapshot.get("gpu", {}).get("devices", []):
        reasons = str(device.get("throttle_reasons_active") or "").casefold()
        if "thermal" in reasons and "not active" not in reasons:
            return True
    return False


def _profile(
    *,
    variant: int,
    threads: int,
    seconds: float,
    batch_hashes: int,
    telemetry: RuntimeTelemetry,
) -> dict[str, Any]:
    before = telemetry.sample()
    started = time.perf_counter()
    deadline = started + seconds
    start_nonce = 100_000
    total_hashes = 0
    calls = 0
    native_rates: list[float] = []
    result_state = "completed"
    thermal_stop = False

    while time.perf_counter() < deadline:
        if start_nonce + batch_hashes > 0xFFFFFFFF:
            start_nonce = 0
        result = scan_nonce_range_native(
            GENESIS_HEADER,
            start_nonce,
            batch_hashes,
            NO_SHARE_TARGET,
            NO_SHARE_TARGET,
            variant=variant,
            threads=threads,
        )
        calls += 1
        checked = int(result.get("checked", 0))
        total_hashes += checked
        rate = result.get("native_hashrate_mhs")
        if rate is not None:
            native_rates.append(float(rate))
        if result.get("status") != "range_exhausted" or checked != batch_hashes:
            result_state = "validation_failed"
            break
        start_nonce += batch_hashes
        if calls % 8 == 0:
            current = telemetry.sample()
            if _thermal_limit_reached(current):
                thermal_stop = True
                result_state = "stopped_thermal_threshold"
                break

    finished = time.perf_counter()
    after = telemetry.sample()
    if _thermal_limit_reached(after):
        thermal_stop = True
        result_state = "stopped_thermal_threshold"
    elapsed = max(0.000001, finished - started)
    return {
        "state": result_state,
        "variant_id": variant,
        "variant": DEFAULT_VARIANT_NAMES.get(variant, f"variant_{variant}"),
        "threads": threads,
        "target": "1 (no practical shares expected; full range must be exhausted)",
        "batch_hashes": batch_hashes,
        "calls": calls,
        "hashes_checked": total_hashes,
        "elapsed_seconds": round(elapsed, 6),
        "throughput_hashes_per_second": round(total_hashes / elapsed, 3),
        "throughput_mh_per_second": round(total_hashes / elapsed / 1_000_000, 6),
        "native_reported_rates_mh_s": native_rates,
        "native_rate_median_mh_s": (
            statistics.median(native_rates) if native_rates else None
        ),
        "thermal_stop": thermal_stop,
        "telemetry_before": {
            "cpu": before.get("cpu"),
            "temperatures": before.get("temperatures"),
            "gpu": before.get("gpu"),
        },
        "telemetry_after": {
            "cpu": after.get("cpu"),
            "temperatures": after.get("temperatures"),
            "gpu": after.get("gpu"),
        },
        "data_quality": {
            "throughput": "measured_local_native_sha256d",
            "temperature": after.get("data_quality", {}).get("temperatures", "unavailable"),
            "gpu": after.get("data_quality", {}).get("gpu", "unavailable"),
        },
    }


def run_hardware_benchmark(
    *,
    seconds_per_profile: float = 2.0,
    batch_hashes: int = 100_000,
    threads: str = "1,2,4",
    include_randomx: bool = False,
    randomx_timeout_seconds: int = 90,
    allow_active_miners: bool = False,
    output: str | None = None,
) -> dict[str, Any]:
    if not 0.25 <= seconds_per_profile <= 60:
        raise ValueError("seconds_per_profile must be between 0.25 and 60 seconds")
    if not 1_000 <= batch_hashes <= 5_000_000:
        raise ValueError("batch_hashes must be between 1000 and 5,000,000")
    telemetry = RuntimeTelemetry(history_size=32)
    baseline = telemetry.sample()
    active_miners = _mining_processes(baseline)
    if active_miners and not allow_active_miners:
        report = {
            "schema": "nexus.hardware.benchmark.v1",
            "created_at_utc": _utc_now(),
            "state": "blocked_active_miner_detected",
            "active_miner_processes": active_miners,
            "message": "Stop active mining workloads or explicitly pass --allow-active-miners. "
                       "Concurrent mining distorts throughput and temperature measurements.",
            "baseline_telemetry": baseline,
            "profiles": [],
        }
        if output:
            _write_report(report, output)
        return report

    status = native_status()
    logical_cpus = int(baseline.get("host", {}).get("logical_cpus") or (os.cpu_count() or 1))
    thread_counts = _parse_threads(threads, logical_cpus)
    report: dict[str, Any] = {
        "schema": "nexus.hardware.benchmark.v1",
        "created_at_utc": _utc_now(),
        "state": "completed",
        "host": baseline.get("host"),
        "os": platform.platform(),
        "python": sys.version,
        "logical_cpus": logical_cpus,
        "physical_cpus": baseline.get("host", {}).get("physical_cpus"),
        "cpu": baseline.get("cpu"),
        "memory": baseline.get("memory"),
        "disk": baseline.get("disk"),
        "network": baseline.get("network"),
        "native_sha256d": status,
        "active_miner_processes": active_miners,
        "benchmark_policy": {
            "network_access": False,
            "pool_connection": False,
            "wallet_access": False,
            "miner_autostart": False,
            "overclocking": False,
            "configuration_changes": False,
            "synthetic_workload": "public Bitcoin genesis 80-byte header; target=1",
        },
        "temperature_provider": baseline.get("temperatures"),
        "baseline_telemetry": baseline,
        "profiles": [],
        "randomx": None,
        "limitations": [],
    }

    if not status.get("available"):
        report["state"] = "native_backend_unavailable"
        report["limitations"].append(status.get("error") or "native SHA-256d backend unavailable")
    else:
        variants = status.get("variants") or []
        for variant in variants:
            for thread_count in thread_counts:
                profile = _profile(
                    variant=int(variant),
                    threads=thread_count,
                    seconds=seconds_per_profile,
                    batch_hashes=batch_hashes,
                    telemetry=telemetry,
                )
                report["profiles"].append(profile)
                if profile["thermal_stop"]:
                    report["state"] = "stopped_thermal_threshold"
                    break
                if profile["state"] != "completed":
                    report["state"] = "benchmark_validation_failed"
                    break
            if report["state"] != "completed":
                break
    if not report["temperature_provider"] or not report["temperature_provider"].get("available"):
        report["limitations"].append(
            "CPU temperatures unavailable: install/start LibreHardwareMonitor with WMI enabled on Windows, "
            "or use a platform exposing psutil temperature sensors."
        )
    if not report["native_sha256d"].get("available"):
        report["limitations"].append(
            "No native SHA-256d backend was built; no native throughput value is reported."
        )

    if include_randomx:
        try:
            from mining.randomx_benchmark import run_benchmark
            randomx_results = []
            for thread_count in thread_counts[:4]:
                randomx_results.append(run_benchmark(
                    threads=thread_count,
                    dataset="1M",
                    timeout_seconds=randomx_timeout_seconds,
                ))
            report["randomx"] = {
                "results": randomx_results,
                "network": "offline_benchmark",
                "pool_connected": False,
                "automatic_application": False,
            }
        except Exception as exc:
            report["randomx"] = {
                "state": "benchmark_error",
                "reason": f"{type(exc).__name__}: {exc}",
            }

    completed_profiles = [p for p in report["profiles"] if p["state"] == "completed"]
    report["best_sha256d_profile"] = (
        max(completed_profiles, key=lambda item: item["throughput_hashes_per_second"])
        if completed_profiles else None
    )
    report["finished_at_utc"] = _utc_now()
    if output:
        _write_report(report, output)
    return report


def _write_report(report: dict[str, Any], output: str) -> None:
    path = Path(output).expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False),
        encoding="utf-8",
    )
    os.replace(temporary, path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="NEXUS offline hardware benchmark")
    parser.add_argument("--seconds-per-profile", type=float, default=2.0)
    parser.add_argument("--batch-hashes", type=int, default=100_000)
    parser.add_argument("--threads", default="1,2,4")
    parser.add_argument("--include-randomx", action="store_true")
    parser.add_argument("--randomx-timeout-seconds", type=int, default=90)
    parser.add_argument("--allow-active-miners", action="store_true")
    parser.add_argument("--output", default=None)
    args = parser.parse_args(argv)
    try:
        report = run_hardware_benchmark(
            seconds_per_profile=args.seconds_per_profile,
            batch_hashes=args.batch_hashes,
            threads=args.threads,
            include_randomx=args.include_randomx,
            randomx_timeout_seconds=args.randomx_timeout_seconds,
            allow_active_miners=args.allow_active_miners,
            output=args.output,
        )
    except ValueError as exc:
        parser.error(str(exc))
    print(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False))
    return 0 if report["state"] in {"completed", "native_backend_unavailable"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
