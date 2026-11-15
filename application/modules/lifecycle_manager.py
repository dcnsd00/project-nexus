"""Dependency-aware lifecycle orchestration for NEXUS services.

This manager is deliberately synchronous: service adapters expose initialize,
start, health_check, stop and shutdown methods. It fails closed, starts in
 topological order and rolls back already-started services after a startup error.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Iterable


class ServiceState(str, Enum):
    REGISTERED = "registered"
    INITIALIZED = "initialized"
    RUNNING = "running"
    DEGRADED = "degraded"
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
        self._order = self._topological_order()
        started: list[str] = []
        try:
            for name in self._order:
                rec = self._records[name]
                failed_deps = [d for d in rec.spec.dependencies
                               if self._records[d].state != ServiceState.RUNNING]
                if failed_deps:
                    raise LifecycleError(f"{name} blocked by dependencies: {failed_deps}")
                rec.instance = rec.spec.factory()
                self._call(rec.instance, "initialize")
                rec.state = ServiceState.INITIALIZED
                self._call(rec.instance, "start")
                rec.health = self._call(rec.instance, "health_check", True)
                healthy = rec.health is not False and not (isinstance(rec.health, dict) and rec.health.get("ok") is False)
                if not healthy:
                    raise LifecycleError(f"health check failed for {name}: {rec.health!r}")
                rec.state = ServiceState.RUNNING
                rec.error = None
                started.append(name)
        except Exception as exc:
            failed_name = name
            rec = self._records[failed_name]
            rec.state = ServiceState.FAILED
            rec.error = f"{type(exc).__name__}: {exc}"
            for started_name in reversed(started):
                self._stop_record(self._records[started_name])
            raise LifecycleError(f"startup failed at {failed_name}: {exc}") from exc
        return self.snapshot()

    def _stop_record(self, rec: ServiceRecord) -> None:
        if rec.instance is not None:
            try:
                self._call(rec.instance, "stop")
            finally:
                self._call(rec.instance, "shutdown")
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
            services.append({"name": name, "state": rec.state.value,
                             "dependencies": list(rec.spec.dependencies),
                             "critical": rec.spec.critical, "health": rec.health,
                             "error": rec.error})
        critical = [r for r in self._records.values() if r.spec.critical]
        all_critical_running = bool(critical) and all(r.state == ServiceState.RUNNING for r in critical)
        return {"services": services, "total": len(services),
                "running": sum(r.state == ServiceState.RUNNING for r in self._records.values()),
                "system_ready": all_critical_running,
                "lifecycle_order": list(self._order)}
