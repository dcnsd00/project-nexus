"""Opt-in lifecycle integration for the HTTPS NEXUS EDGE gateway.

The gateway is mounted inside NEXUS MASTER only when explicitly enabled.
Secrets and durable storage are validated at startup; failures are reported
by type only and never expose credential material.
"""
from __future__ import annotations

import os
from typing import Any, Callable


class EdgeGatewayRuntime:
    def __init__(
        self,
        *,
        env: dict[str, str] | None = None,
        manager_factory: Callable[[], Any] | None = None,
        app_factory: Callable[..., Any] | None = None,
        mount_path: str = "/edge",
    ) -> None:
        self._env = os.environ if env is None else env
        self._manager_factory = manager_factory
        self._app_factory = app_factory
        self._mount_path = mount_path.rstrip("/") or "/edge"
        self._mounted_app: Any = None
        self._host_app: Any = None
        self._error: str | None = None
        self._owned_manager: Any = None

    def enabled(self) -> bool:
        return self._env.get("NEXUS_EDGE_GATEWAY_ENABLED", "false").strip().lower() == "true"

    def start(self, host_app: Any, manager: Any | None = None) -> None:
        if not self.enabled():
            return
        if self._mounted_app is not None:
            return
        token = self._env.get("NEXUS_EDGE_PROVISIONING_TOKEN")
        if not token or len(token) < 32:
            raise RuntimeError("NEXUS_EDGE_PROVISIONING_TOKEN is missing or too short")
        edge_manager = manager
        created_here = edge_manager is None
        try:
            if edge_manager is None:
                if self._manager_factory is not None:
                    edge_manager = self._manager_factory()
                else:
                    from .gateway import create_edge_manager_from_env
                    edge_manager = create_edge_manager_from_env(dict(self._env))
            snapshot = edge_manager.snapshot()
        except Exception:
            lock = getattr(edge_manager, "_runtime_lock", None)
            if lock is not None:
                lock.release()
            raise
        if snapshot.get("mode") != "sqlite_persistent":
            runtime_lock = getattr(edge_manager, "_runtime_lock", None)
            if runtime_lock is not None:
                runtime_lock.release()
            raise RuntimeError(
                "online EDGE gateway requires the shared sqlite_persistent manager; "
                "configure NEXUS_EDGE_STORAGE_KEY"
            )
        if self._app_factory is None:
            from .gateway import create_edge_app
            app_factory = create_edge_app
        else:
            app_factory = self._app_factory
        try:
            gateway_app = app_factory(manager=edge_manager, provisioning_token=token,
                                      env=dict(self._env))
            host_app.mount(self._mount_path, gateway_app, name="nexus-edge-gateway")
        except Exception:
            lock = getattr(edge_manager, "_runtime_lock", None)
            if lock is not None:
                lock.release()
            raise
        self._host_app = host_app
        self._mounted_app = gateway_app
        self._owned_manager = edge_manager if created_here else None
        self._error = None

    def stop(self, host_app: Any | None = None) -> None:
        target = host_app or self._host_app
        if target is not None and self._mounted_app is not None:
            target.router.routes[:] = [
                route for route in target.router.routes
                if not (getattr(route, "name", None) == "nexus-edge-gateway"
                        and getattr(route, "path", None) == self._mount_path)
            ]
        self._mounted_app = None
        self._host_app = None
        if self._owned_manager is not None:
            lock = getattr(self._owned_manager, "_runtime_lock", None)
            if lock is not None:
                lock.release()
            self._owned_manager = None

    def set_start_error(self, error_type: str) -> None:
        self._error = str(error_type)

    def status(self) -> dict[str, Any]:
        active = self._mounted_app is not None
        return {
            "gateway": "active" if active else (
                "enabled_start_failed" if self._error else (
                    "enabled_not_started" if self.enabled() else "disabled_by_default"
                )
            ),
            "enabled": self.enabled(),
            "mounted_at": self._mount_path if active else None,
            "operator_auth_required": True,
            "durable_storage_required": True,
            "tls_terminator_required": True,
            "last_error_type": self._error,
            "wallet_access_enabled": False,
            "miner_autostart_enabled": False,
            "arbitrary_command_execution_enabled": False,
            "public_chain_writes_enabled": False,
        }
