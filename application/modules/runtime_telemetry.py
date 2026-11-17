"""Measured host telemetry for the NEXUS MASTER control plane.

All values are local observations. Missing hardware/provider telemetry is
reported as unavailable, never replaced with estimates.
"""
from __future__ import annotations

from collections import deque
from datetime import datetime, timezone
import csv
import io
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
        executable = None
        for candidate in ("nvidia-smi", "nvidia-smi.exe"):
            from shutil import which
            executable = which(candidate)
            if executable:
                break
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
                })
            return {"available": bool(devices), "source": "nvidia-smi",
                    "devices": devices, "reason": None if devices else "no GPU rows returned"}
        except Exception as exc:
            return {"available": False, "source": "nvidia-smi", "devices": [],
                    "reason": type(exc).__name__}

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
        snapshot = {
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "sample_interval_seconds": _rounded(interval),
            "host": {"os": platform.platform(), "hostname": platform.node(),
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
            "processes": processes,
            "data_quality": {
                "cpu": "measured_local",
                "memory": "measured_local",
                "disk": "measured_local" if disk is not None else "unavailable",
                "network_rate": "measured_delta" if interval is not None else "warming_up",
                "gpu": "measured_local" if gpu["available"] else "unavailable",
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

    def snapshot_with_history(self, limit: int = 120) -> dict[str, Any]:
        current = self.sample()
        return {"snapshot": current, "history": self.history(limit),
                "history_capacity": self._history.maxlen,
                "sampling_contract": "one sample per API call; dashboard polls every 2.5 seconds"}
