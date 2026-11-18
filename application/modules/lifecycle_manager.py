"""Dependency-aware lifecycle orchestration for NEXUS services.

This manager is deliberately synchronous: service adapters expose initialize,
start, health_check, stop and shutdown methods. It fails closed, starts in
 topological order and rolls back already-started services after a startup error.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import os
import time
from typing import Any, Callable, Iterable


class ServiceState(str, Enum):
    REGISTERED = "registered"
    INITIALIZED = "initialized"
    RUNNING = "running"
    DEGRADED = "degraded"
    BLOCKED = "blocked"
    STOPPED = "stopped"
    FAILED = "failed"


@dataclass
class ServiceSpec:
    name: str
    factory: Callable[[], Any]
    dependencies: tuple[str, ...] = ()
    critical: bool = True


@dataclass
class ServiceRecord:
    spec: ServiceSpec
    instance: Any = None
    state: ServiceState = ServiceState.REGISTERED
    error: str | None = None
    health: Any = None
    started_at_utc: str | None = None
    stopped_at_utc: str | None = None
    started_monotonic: float | None = None
    last_uptime_seconds: float | None = None
    startup_duration_seconds: float | None = None


class LifecycleError(RuntimeError):
    pass


class LifecycleManager:
    def __init__(self) -> None:
        self._records: dict[str, ServiceRecord] = {}
        self._order: list[str] = []

    def register(self, spec: ServiceSpec) -> None:
        if not spec.name or spec.name in self._records:
            raise LifecycleError(f"duplicate or empty service name: {spec.name!r}")
        self._records[spec.name] = ServiceRecord(spec=spec)
        self._order = []

    def _topological_order(self) -> list[str]:
        temporary: set[str] = set()
        permanent: set[str] = set()
        result: list[str] = []

        def visit(name: str) -> None:
            if name in permanent:
                return
            if name in temporary:
                raise LifecycleError(f"dependency cycle detected at {name}")
            if name not in self._records:
                raise LifecycleError(f"unknown dependency: {name}")
            temporary.add(name)
            for dep in self._records[name].spec.dependencies:
                visit(dep)
            temporary.remove(name)
            permanent.add(name)
            result.append(name)

        for name in self._records:
            visit(name)
        return result

    @staticmethod
    def _call(instance: Any, method: str, default: Any = None) -> Any:
        fn = getattr(instance, method, None)
        return fn() if callable(fn) else default

    def start_all(self) -> dict[str, Any]:
        """Start services in dependency order with isolation for optional failures.

        A failed critical service aborts startup and rolls back services that
        started earlier. A failed optional service is recorded as FAILED while
        independent services continue. Dependents of a failed service are
        BLOCKED; a critical dependent still makes the overall startup fail.
        """
        self._order = self._topological_order()
        started: list[str] = []

        for name in self._order:
            rec = self._records[name]
            failed_deps = [
                dep for dep in rec.spec.dependencies
                if self._records[dep].state != ServiceState.RUNNING
            ]
            if failed_deps:
                rec.state = ServiceState.BLOCKED
                rec.error = f"blocked by dependencies that are not running: {failed_deps}"
                if rec.spec.critical:
                    self._rollback_started(started)
                    raise LifecycleError(
                        f"critical service {name} blocked by dependencies: {failed_deps}"
                    )
                continue

            attempt_started = time.monotonic()
            try:
                rec.instance = rec.spec.factory()
                self._call(rec.instance, "initialize")
                rec.state = ServiceState.INITIALIZED
                self._call(rec.instance, "start")
                rec.health = self._call(rec.instance, "health_check", True)
                healthy = (
                    rec.health is not False
                    and not (
                        isinstance(rec.health, dict)
                        and rec.health.get("ok") is False
                    )
                )
                if not healthy:
                    raise LifecycleError(
                        f"health check failed for {name}: {rec.health!r}"
                    )
                rec.state = ServiceState.RUNNING
                rec.error = None
                rec.started_at_utc = datetime.now(timezone.utc).isoformat()
                rec.stopped_at_utc = None
                rec.started_monotonic = time.monotonic()
                rec.last_uptime_seconds = None
                rec.startup_duration_seconds = round(rec.started_monotonic - attempt_started, 6)
                started.append(name)
            except Exception as exc:
                rec.startup_duration_seconds = round(time.monotonic() - attempt_started, 6)
                rec.state = ServiceState.FAILED
                rec.error = f"{type(exc).__name__}: {exc}"
                self._cleanup_failed_record(rec)
                if rec.spec.critical:
                    self._rollback_started(started)
                    raise LifecycleError(
                        f"startup failed at critical service {name}: {exc}"
                    ) from exc
                # Optional failure is visible in the snapshot, but does not
                # take down already-running critical or independent services.
                continue

        return self.snapshot()

    def _cleanup_failed_record(self, rec: ServiceRecord) -> None:
        """Best-effort cleanup for an instance that failed during startup."""
        if rec.instance is None:
            return
        cleanup_errors: list[str] = []
        for method in ("stop", "shutdown"):
            try:
                self._call(rec.instance, method)
            except Exception as exc:
                cleanup_errors.append(f"{method}: {type(exc).__name__}: {exc}")
        if cleanup_errors:
            suffix = "; cleanup errors: " + "; ".join(cleanup_errors)
            rec.error = (rec.error or "startup failed") + suffix

    def _rollback_started(self, started: list[str]) -> None:
        for started_name in reversed(started):
            self._stop_record(self._records[started_name])

    def _stop_record(self, rec: ServiceRecord) -> None:
        if rec.started_monotonic is not None:
            rec.last_uptime_seconds = round(max(0.0, time.monotonic() - rec.started_monotonic), 6)
            rec.stopped_at_utc = datetime.now(timezone.utc).isoformat()
            rec.started_monotonic = None
        if rec.instance is not None:
            cleanup_errors: list[str] = []
            for method in ("stop", "shutdown"):
                try:
                    self._call(rec.instance, method)
                except Exception as exc:
                    cleanup_errors.append(f"{method}: {type(exc).__name__}: {exc}")
            if cleanup_errors:
                rec.error = "; ".join(cleanup_errors)
        rec.state = ServiceState.STOPPED

    def stop_all(self) -> dict[str, Any]:
        order = self._order or list(self._records)
        for name in reversed(order):
            rec = self._records[name]
            if rec.state in (ServiceState.RUNNING, ServiceState.DEGRADED, ServiceState.INITIALIZED):
                self._stop_record(rec)
        return self.snapshot()

    def health_check_all(self) -> dict[str, Any]:
        for rec in self._records.values():
            if rec.state == ServiceState.RUNNING:
                try:
                    rec.health = self._call(rec.instance, "health_check", True)
                    if rec.health is False or (isinstance(rec.health, dict) and rec.health.get("ok") is False):
                        rec.state = ServiceState.DEGRADED
                except Exception as exc:
                    rec.state = ServiceState.DEGRADED
                    rec.error = f"{type(exc).__name__}: {exc}"
        return self.snapshot()

    def snapshot(self) -> dict[str, Any]:
        services = []
        for name, rec in self._records.items():
            active = rec.started_monotonic is not None and rec.state in (
                ServiceState.RUNNING, ServiceState.DEGRADED
            )
            uptime = (
                round(max(0.0, time.monotonic() - rec.started_monotonic), 6)
                if active else rec.last_uptime_seconds
            )
            services.append({
                "name": name,
                "state": rec.state.value,
                "dependencies": list(rec.spec.dependencies),
                "critical": rec.spec.critical,
                "health": rec.health,
                "error": rec.error,
                "started_at_utc": rec.started_at_utc,
                "stopped_at_utc": rec.stopped_at_utc,
                "startup_duration_seconds": rec.startup_duration_seconds,
                "uptime_seconds": uptime,
                "execution_model": "in_process",
                "shared_process_pid": os.getpid() if active else None,
                "individual_process_pid": None,
            })
        critical = [r for r in self._records.values() if r.spec.critical]
        all_critical_running = bool(critical) and all(r.state == ServiceState.RUNNING for r in critical)
        return {"services": services, "total": len(services),
                "running": sum(r.state == ServiceState.RUNNING for r in self._records.values()),
                "system_ready": all_critical_running,
                "lifecycle_order": list(self._order)}
