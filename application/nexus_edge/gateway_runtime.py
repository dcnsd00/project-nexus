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

    def enabled(self) -> bool:
        return self._env.get("NEXUS_EDGE_GATEWAY_ENABLED", "false").strip().lower() == "true"

    def start(self, host_app: Any) -> None:
        if not self.enabled():
            return
        if self._mounted_app is not None:
            return
        token = self._env.get("NEXUS_EDGE_PROVISIONING_TOKEN")
        if not token or len(token) < 32:
            raise RuntimeError("NEXUS_EDGE_PROVISIONING_TOKEN is missing or too short")
        if self._manager_factory is not None:
            manager = self._manager_factory()
        else:
            from .gateway import create_edge_manager_from_env
            manager = create_edge_manager_from_env(dict(self._env))
        if self._app_factory is None:
            from .gateway import create_edge_app
            app_factory = create_edge_app
        else:
            app_factory = self._app_factory
        gateway_app = app_factory(manager=manager, provisioning_token=token,
                                  env=dict(self._env))
        host_app.mount(self._mount_path, gateway_app, name="nexus-edge-gateway")
        self._host_app = host_app
        self._mounted_app = gateway_app
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
