"""Measured host telemetry for the NEXUS MASTER control plane.

All values are local observations. Missing hardware/provider telemetry is
reported as unavailable, never replaced with estimates.
"""
from __future__ import annotations

from collections import deque
from datetime import datetime, timezone
import csv
import io
import json
import os
import platform
import subprocess
import threading
import time
from typing import Any

import psutil


_MINER_NAMES = (
    "xmrig", "srbminer", "verus", "miner", "nexus-worker", "cpuminer",
    "lolminer", "nbminer", "teamredminer", "gminer", "bminer", "trex",
    "wildrig", "rigel", "ccminer", "nanominer", "phoenixminer", "ethminer",
)


def _rounded(value: Any, digits: int = 3) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number != number or number in (float("inf"), float("-inf")):
        return None
    return round(number, digits)


def _number(value: str) -> float | None:
    value = value.strip()
    if not value or value.upper() in {"N/A", "[NOT SUPPORTED]"}:
        return None
    try:
        return float(value)
    except ValueError:
        return None


class RuntimeTelemetry:
    """Thread-safe bounded telemetry sampler for the local MASTER host."""

    def __init__(self, history_size: int = 300) -> None:
        self._history: deque[dict[str, Any]] = deque(maxlen=max(2, history_size))
        self._lock = threading.RLock()
        self._last_network: tuple[float, int, int] | None = None

    def _gpu(self) -> dict[str, Any]:
        from shutil import which

        executable = which("nvidia-smi") or which("nvidia-smi.exe")
        if not executable:
            return {"available": False, "source": "nvidia-smi", "devices": [],
                    "reason": "nvidia-smi unavailable"}
        query = [
            executable,
            "--query-gpu=name,utilization.gpu,memory.used,memory.total,temperature.gpu,power.draw",
            "--format=csv,noheader,nounits",
        ]
        try:
            result = subprocess.run(query, capture_output=True, text=True,
                                    timeout=3, check=True)
            devices = []
            for row in csv.reader(io.StringIO(result.stdout)):
                values = [item.strip() for item in row]
                if len(values) < 6:
                    continue
                util, used, total, temp, power = (_number(x) for x in values[1:6])
                devices.append({
                    "name": values[0],
                    "utilization_percent": _rounded(util),
                    "memory_used_mib": _rounded(used),
                    "memory_total_mib": _rounded(total),
                    "memory_percent": _rounded(used / total * 100) if used is not None and total else None,
                    "temperature_c": _rounded(temp),
                    "power_w": _rounded(power),
                    "graphics_clock_mhz": None,
                    "sm_clock_mhz": None,
                    "memory_clock_mhz": None,
                    "power_limit_w": None,
                    "throttle_reasons_active": None,
                })
            if not devices:
                return {"available": False, "source": "nvidia-smi", "devices": [],
                        "reason": "no GPU rows returned"}

            # Optional diagnostics are queried separately: older GPUs/drivers may
            # not implement every field. Missing fields remain None.
            diagnostics = [
                executable,
                "--query-gpu=clocks.current.graphics,clocks.current.sm,clocks.current.memory,power.limit,clocks_throttle_reasons.active",
                "--format=csv,noheader,nounits",
            ]
            try:
                detail = subprocess.run(
                    diagnostics, capture_output=True, text=True, timeout=3, check=True
                )
                for index, row in enumerate(csv.reader(io.StringIO(detail.stdout))):
                    if index >= len(devices):
                        break
                    values = [item.strip() for item in row]
                    if len(values) >= 4:
                        devices[index].update({
                            "graphics_clock_mhz": _rounded(_number(values[0])),
                            "sm_clock_mhz": _rounded(_number(values[1])),
                            "memory_clock_mhz": _rounded(_number(values[2])),
                            "power_limit_w": _rounded(_number(values[3])),
                        })
                    if len(values) >= 5:
                        devices[index]["throttle_reasons_active"] = values[4] or None
            except Exception:
                pass

            return {"available": True, "source": "nvidia-smi", "devices": devices,
                    "reason": None}
        except Exception as exc:
            return {"available": False, "source": "nvidia-smi", "devices": [],
                    "reason": type(exc).__name__}

    @staticmethod
    def _thermal_state(current: float | None, high: float | None,
                       critical: float | None) -> str:
        if current is None:
            return "unavailable"
        if critical is not None and current >= critical:
            return "at_or_above_sensor_critical_threshold"
        if high is not None and current >= high:
            return "at_or_above_sensor_high_threshold"
        if high is not None or critical is not None:
            return "below_reported_sensor_thresholds"
        return "thresholds_unavailable"

    def _temperatures(self) -> dict[str, Any]:
        """Read actual OS/provider temperature sensors; never estimate values."""
        system = platform.system()
        errors: list[str] = []

        if system == "Windows":
            # LibreHardwareMonitor exposes sensor instances in this WMI namespace
            # when the application is running and its WMI interface is available.
            script = (
                "$ErrorActionPreference='Stop'; "
                "$s=Get-CimInstance -Namespace 'root\\LibreHardwareMonitor' "
                "-ClassName Sensor | Where-Object { $_.SensorType -eq 'Temperature' "
                "-and $null -ne $_.Value } | "
                "Select-Object Name,SensorType,Value,Identifier; "
                "if ($null -eq $s) { '[]' } else { ConvertTo-Json -InputObject @($s) -Compress -Depth 4 }"
            )
            try:
                result = subprocess.run(
                    ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script],
                    capture_output=True, text=True, timeout=3, check=True,
                )
                rows = json.loads(result.stdout.strip() or "[]")
                if isinstance(rows, dict):
                    rows = [rows]
                sensors = []
                for row in rows if isinstance(rows, list) else []:
                    value = _rounded(row.get("Value"), 1)
                    if value is None:
                        continue
                    sensors.append({
                        "name": str(row.get("Name") or "unknown"),
                        "identifier": str(row.get("Identifier") or ""),
                        "temperature_c": value,
                        "high_c": None,
                        "critical_c": None,
                        "thermal_state": "thresholds_unavailable",
                    })
                if sensors:
                    return {"available": True, "source": "LibreHardwareMonitor WMI",
                            "sensors": sensors, "reason": None}
            except Exception as exc:
                errors.append(f"LibreHardwareMonitor WMI: {type(exc).__name__}")

        try:
            raw = psutil.sensors_temperatures()
            sensors = []
            for group, readings in (raw or {}).items():
                for reading in readings:
                    current = _rounded(getattr(reading, "current", None), 1)
                    high = _rounded(getattr(reading, "high", None), 1)
                    critical = _rounded(getattr(reading, "critical", None), 1)
                    if current is None:
                        continue
                    sensors.append({
                        "name": str(getattr(reading, "label", "") or group),
                        "sensor_group": str(group),
                        "temperature_c": current,
                        "high_c": high,
                        "critical_c": critical,
                        "thermal_state": self._thermal_state(current, high, critical),
                    })
            if sensors:
                return {"available": True, "source": "psutil", "sensors": sensors,
                        "reason": None}
        except Exception as exc:
            errors.append(f"psutil: {type(exc).__name__}")

        reason = (
            "No temperature provider available; on Windows run LibreHardwareMonitor "
            "with its WMI namespace enabled"
            if system == "Windows" else "OS or hardware does not expose temperature sensors"
        )
        return {"available": False, "source": None, "sensors": [],
                "reason": reason, "provider_errors": errors}

    def _processes(self) -> dict[str, list[dict[str, Any]]]:
        observed = []
        miners = []
        for proc in psutil.process_iter(["pid", "name", "memory_info", "status"]):
            try:
                info = proc.info
                name = str(info.get("name") or "unknown")
                cpu = _rounded(proc.cpu_percent(interval=None))
                mem = info.get("memory_info")
                item = {
                    "pid": info.get("pid"),
                    "name": name,
                    "cpu_percent": cpu,
                    "memory_rss_bytes": getattr(mem, "rss", None),
                    "status": info.get("status"),
                }
                observed.append(item)
                if any(token in name.casefold() for token in _MINER_NAMES):
                    miners.append(item)
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue
        observed.sort(key=lambda item: item["cpu_percent"] or 0, reverse=True)
        miners.sort(key=lambda item: item["cpu_percent"] or 0, reverse=True)
        return {"top": observed[:12], "mining": miners[:24]}

    def sample(self) -> dict[str, Any]:
        now = time.monotonic()
        cpu_per_core = psutil.cpu_percent(interval=None, percpu=True)
        cpu_total = _rounded(sum(cpu_per_core) / len(cpu_per_core)) if cpu_per_core else None
        memory = psutil.virtual_memory()
        disk_path = os.environ.get("SystemDrive", "C:") + "\\" if os.name == "nt" else "/"
        try:
            disk = psutil.disk_usage(disk_path)
        except (OSError, ValueError):
            disk = None
        net = psutil.net_io_counters()
        tx_mbps = rx_mbps = None
        interval = None
        if self._last_network:
            previous_time, previous_sent, previous_recv = self._last_network
            interval = max(0.001, now - previous_time)
            tx_mbps = max(0, net.bytes_sent - previous_sent) * 8 / interval / 1_000_000
            rx_mbps = max(0, net.bytes_recv - previous_recv) * 8 / interval / 1_000_000
        self._last_network = (now, net.bytes_sent, net.bytes_recv)
        frequency = psutil.cpu_freq()
        processes = self._processes()
        gpu = self._gpu()
        temperatures = self._temperatures()
        snapshot = {
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "sample_interval_seconds": _rounded(interval),
            "host": {"os": platform.platform(), "hostname": platform.node(),
                     "processor": platform.processor() or None,
                     "architecture": platform.machine(),
                     "logical_cpus": psutil.cpu_count(logical=True),
                     "physical_cpus": psutil.cpu_count(logical=False)},
            "cpu": {
                "utilization_percent": cpu_total,
                "per_core_percent": [_rounded(value) for value in cpu_per_core],
                "frequency_mhz": _rounded(frequency.current) if frequency else None,
            },
            "memory": {
                "total_bytes": memory.total, "used_bytes": memory.used,
                "available_bytes": memory.available,
                "utilization_percent": _rounded(memory.percent),
            },
            "disk": None if disk is None else {
                "path": disk_path, "total_bytes": disk.total, "used_bytes": disk.used,
                "free_bytes": disk.free, "utilization_percent": _rounded(disk.percent),
            },
            "network": {
                "bytes_sent_total": net.bytes_sent, "bytes_received_total": net.bytes_recv,
                "tx_mbps": _rounded(tx_mbps), "rx_mbps": _rounded(rx_mbps),
            },
            "gpu": gpu,
            "temperatures": temperatures,
            "processes": processes,
            "data_quality": {
                "cpu": "measured_local",
                "memory": "measured_local",
                "disk": "measured_local" if disk is not None else "unavailable",
                "network_rate": "measured_delta" if interval is not None else "warming_up",
                "gpu": "measured_local" if gpu["available"] else "unavailable",
                "temperatures": "measured_local" if temperatures["available"] else "unavailable",
                "temperature_source": temperatures["source"],
                "gpu_clocks_and_power_limit": (
                    "measured_local" if gpu["available"] and any(
                        device.get("power_limit_w") is not None
                        for device in gpu["devices"]
                    ) else "unavailable_or_unsupported"
                ),
                "mining_processes": "process_name_detection_only",
            },
        }
        with self._lock:
            self._history.append(snapshot)
        return snapshot

    def history(self, limit: int = 120) -> list[dict[str, Any]]:
        bounded = max(1, min(int(limit), 300))
        with self._lock:
            return list(self._history)[-bounded:]

    def snapshot_with_history(self, limit: int = 120, *, sample: bool = True) -> dict[str, Any]:
        """Return telemetry and history; optionally reuse the latest measured sample.

        The dashboard owns the sampling cadence. Aggregated read-only reports can
        reuse that sample so they do not trigger duplicate process/GPU probes.
        """
        if sample:
            current = self.sample()
        else:
            with self._lock:
                current = self._history[-1] if self._history else None
            if current is None:
                current = self.sample()
        return {"snapshot": current, "history": self.history(limit),
                "history_capacity": self._history.maxlen,
                "sampling_contract": "dashboard samples every 2.5 seconds; aggregate reports reuse latest sample"}
