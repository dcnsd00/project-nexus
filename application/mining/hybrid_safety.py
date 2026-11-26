"""Fail-closed resource checks for CPU and GPU mining lanes.

Only measured local telemetry is accepted. Missing or malformed sensors are
never replaced with synthetic/default temperatures.
"""
from __future__ import annotations

import math
from typing import Any

DEFAULT_CPU_MAX_TEMPERATURE_C = 85.0
DEFAULT_GPU_MAX_TEMPERATURE_C = 85.0


def _finite_number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    return number if math.isfinite(number) else None


def cpu_temperature_from_telemetry(report: dict[str, Any] | None) -> float | None:
    """Return the hottest recognisable CPU sensor while excluding GPU sensors."""
    if not isinstance(report, dict) or report.get("available") is not True:
        return None
    sensors = report.get("sensors")
    if not isinstance(sensors, list):
        return None

    cpu_markers = ("cpu", "coretemp", "intelcpu", "amd cpu", "package", "tctl", "tdie")
    gpu_markers = ("gpu", "nvidia", "radeon", "graphics")
    readings: list[float] = []
    for sensor in sensors:
        if not isinstance(sensor, dict):
            continue
        label = " ".join(
            str(sensor.get(key) or "")
            for key in ("name", "sensor_group", "identifier")
        ).casefold()
        if any(marker in label for marker in gpu_markers):
            continue
        if not any(marker in label for marker in cpu_markers):
            continue
        value = _finite_number(sensor.get("temperature_c"))
        if value is not None and -20.0 <= value <= 150.0:
            readings.append(value)
    return max(readings) if readings else None


def validate_engine_resources(
    engine: str,
    hardware: dict[str, Any],
    limits: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Validate one local mining lane against explicit limits and measured sensors."""
    limits = limits or {}
    if engine not in {"cpu", "gpu"}:
        return {"allowed": False, "reasons": ["invalid_engine"], "telemetry": "invalid"}

    default_limit = (
        DEFAULT_CPU_MAX_TEMPERATURE_C if engine == "cpu"
        else DEFAULT_GPU_MAX_TEMPERATURE_C
    )
    maximum = _finite_number(limits.get("max_temperature_c", default_limit))
    if maximum is None or not 50.0 <= maximum <= 105.0:
        return {"allowed": False, "reasons": ["invalid_temperature_limit"], "telemetry": "invalid"}

    reasons: list[str] = []
    if engine == "gpu":
        total = _finite_number(hardware.get("memory_total_mb"))
        required = _finite_number(limits.get("required_vram_mb", 0))
        margin = _finite_number(limits.get("vram_margin_mb", 256))
        if hardware.get("available") is not True or total is None:
            reasons.append("gpu_telemetry_missing")
        elif required is None or margin is None or required < 0 or margin < 0:
            reasons.append("invalid_vram_limit")
        elif total < required + margin:
            reasons.append("vram_insufficient")
    elif hardware.get("available") is not True:
        reasons.append("cpu_thermal_telemetry_missing")

    temperature = _finite_number(hardware.get("temperature_c"))
    if temperature is None:
        reasons.append("temperature_telemetry_missing")
    elif temperature >= maximum:
        reasons.append("temperature_limit")

    return {
        "allowed": not reasons,
        "reasons": reasons,
        "telemetry": "measured" if not reasons else "incomplete_or_unsafe",
        "temperature_c": temperature,
        "max_temperature_c": maximum,
    }


def validate_telemetry_snapshot(
    engine: str,
    snapshot: dict[str, Any] | None,
    limits: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Adapt RuntimeTelemetry's measured CPU/GPU sensors to the resource guard."""
    snapshot = snapshot if isinstance(snapshot, dict) else {}
    if engine == "cpu":
        temperature = cpu_temperature_from_telemetry(snapshot.get("temperatures"))
        return validate_engine_resources(
            "cpu",
            {"available": temperature is not None, "temperature_c": temperature},
            limits,
        )
    if engine == "gpu":
        report = snapshot.get("gpu")
        report = report if isinstance(report, dict) else {}
        devices = report.get("devices")
        first = (
            devices[0]
            if isinstance(devices, list) and devices and isinstance(devices[0], dict)
            else {}
        )
        return validate_engine_resources(
            "gpu",
            {
                "available": report.get("available") is True,
                "memory_total_mb": first.get("memory_total_mib"),
                "temperature_c": first.get("temperature_c"),
            },
            limits,
        )
    return {"allowed": False, "reasons": ["invalid_engine"], "telemetry": "invalid"}
