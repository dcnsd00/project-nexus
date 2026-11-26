"""Runtime thermal guard for explicitly started NEXUS mining workers.

No miner is started here. This monitor samples only while a NEXUS-managed
CPU/GPU worker is active and stops the affected lane if required sensor data
disappears or a configured temperature ceiling is reached.
"""
from __future__ import annotations

from collections import deque
from datetime import datetime, timezone
import threading
from typing import Any

from mining.hybrid_safety import validate_telemetry_snapshot


class MiningSafetyMonitor:
    def __init__(
        self,
        supervisor: Any,
        controller: Any,
        telemetry: Any,
        *,
        interval_seconds: float = 5.0,
        cpu_max_temperature_c: float = 85.0,
        gpu_max_temperature_c: float = 85.0,
    ):
        self.supervisor = supervisor
        self.controller = controller
        self.telemetry = telemetry
        self.interval_seconds = max(1.0, min(float(interval_seconds), 30.0))
        self.limits = {
            "cpu": {"max_temperature_c": float(cpu_max_temperature_c)},
            "gpu": {"max_temperature_c": float(gpu_max_temperature_c),
                    "required_vram_mb": 0, "vram_margin_mb": 256},
        }
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._lock = threading.RLock()
        self._events: deque[dict[str, Any]] = deque(maxlen=50)
        self._last_check: dict[str, Any] | None = None
        self._checks = 0
        self._stops = 0

    def start(self) -> None:
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                return
            self._stop_event.clear()
            self._thread = threading.Thread(
                target=self._run, name="NEXUS-Mining-Safety", daemon=True
            )
            self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        thread = self._thread
        if thread is not None and thread.is_alive():
            thread.join(timeout=max(2.0, self.interval_seconds + 1.0))
        with self._lock:
            if thread is None or not thread.is_alive():
                self._thread = None

    def shutdown(self) -> None:
        self.stop()

    def _hybrid_active_lanes(self) -> set[str]:
        try:
            status = self.supervisor.status(read_only=True)
        except Exception:
            return set()
        engines = status.get("engines", {}) if isinstance(status, dict) else {}
        return {
            lane for lane in ("cpu", "gpu")
            if isinstance(engines.get(lane), dict)
            and engines[lane].get("state") in {"starting", "running"}
        }

    def _direct_active_lanes(self) -> set[str]:
        try:
            status = self.controller.status()
        except Exception:
            return set()
        if not isinstance(status, dict) or status.get("status") not in {"starting", "running"}:
            return set()
        device = str(status.get("device") or "").upper()
        if not device:
            miner_id = status.get("miner_id")
            spec = getattr(self.controller, "MINERS", {}).get(miner_id, {})
            devices = spec.get("device", [])
            device = "BOTH" if set(devices) >= {"CPU", "GPU"} else (devices[0] if devices else "")
        if device == "BOTH":
            return {"cpu", "gpu"}
        if device in {"CPU", "GPU"}:
            return {device.lower()}
        return set()

    def _stop_direct_once(self) -> dict[str, Any]:
        try:
            return self.controller.stop()
        except Exception as exc:
            return {"error": type(exc).__name__}

    def check_once(self) -> dict[str, Any]:
        """Run one deterministic monitoring pass, also used by simulation tests."""
        hybrid_lanes = self._hybrid_active_lanes()
        direct_lanes = self._direct_active_lanes()
        active_lanes = sorted(hybrid_lanes | direct_lanes)
        if not active_lanes:
            result = {
                "active": False, "active_lanes": [], "telemetry_sampled": False,
                "events": [], "checks": self._checks, "stops": self._stops,
            }
            with self._lock:
                self._last_check = result
            return result

        telemetry_error = None
        try:
            snapshot = self.telemetry.sample()
            if not isinstance(snapshot, dict):
                snapshot = {}
                telemetry_error = "invalid_telemetry_snapshot"
        except Exception as exc:
            snapshot = {}
            telemetry_error = type(exc).__name__

        events: list[dict[str, Any]] = []
        direct_stopped = False
        for lane in active_lanes:
            guard = validate_telemetry_snapshot(lane, snapshot, self.limits[lane])
            if telemetry_error:
                guard = {
                    **guard, "allowed": False,
                    "reasons": list(dict.fromkeys([
                        *guard.get("reasons", []), "telemetry_probe_failed"
                    ])),
                }
            if guard.get("allowed"):
                continue

            event: dict[str, Any] = {
                "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                "engine": lane,
                "reason": guard.get("reasons", []),
                "temperature_c": guard.get("temperature_c"),
                "max_temperature_c": guard.get("max_temperature_c"),
                "telemetry_error": telemetry_error,
                "targets": [],
                "actions": [],
            }
            if lane in hybrid_lanes:
                try:
                    event["actions"].append(self.supervisor.stop(lane))
                except Exception as exc:
                    event["actions"].append({"error": type(exc).__name__})
                event["targets"].append("hybrid_supervisor")
            if lane in direct_lanes and not direct_stopped:
                event["actions"].append(self._stop_direct_once())
                event["targets"].append("direct_controller")
                direct_stopped = True
            events.append(event)

        with self._lock:
            self._checks += 1
            self._stops += len(events)
            self._events.extend(events)
            result = {
                "active": True, "active_lanes": active_lanes,
                "telemetry_sampled": telemetry_error is None,
                "telemetry_error": telemetry_error, "events": events,
                "checks": self._checks, "stops": self._stops,
            }
            self._last_check = result
        return result

    def _emergency_stop(self) -> None:
        hybrid_lanes = self._hybrid_active_lanes()
        direct_lanes = self._direct_active_lanes()
        for lane in sorted(hybrid_lanes):
            try:
                self.supervisor.stop(lane)
            except Exception:
                pass
        if direct_lanes:
            self._stop_direct_once()

    def _run(self) -> None:
        while not self._stop_event.is_set():
            try:
                self.check_once()
            except Exception as exc:
                self._emergency_stop()
                with self._lock:
                    self._events.append({
                        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                        "engine": "monitor",
                        "reason": ["monitor_internal_error"],
                        "action": {"error": type(exc).__name__},
                    })
            self._stop_event.wait(self.interval_seconds)

    def status(self) -> dict[str, Any]:
        with self._lock:
            return {
                "ok": True,
                "running": self._thread is not None and self._thread.is_alive(),
                "interval_seconds": self.interval_seconds,
                "limits": {key: dict(value) for key, value in self.limits.items()},
                "checks": self._checks, "stops": self._stops,
                "last_check": dict(self._last_check) if self._last_check else None,
                "recent_events": list(self._events),
                "miner_autostart_enabled": False,
                "external_network_access": False,
            }
