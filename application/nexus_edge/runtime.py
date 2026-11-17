"""Opt-in EDGE transport lifecycle for the NEXUS MASTER process.

MQTTS is never started unless NEXUS_EDGE_MQTT_ENABLED=true. Uplinks are
HMAC/replay validated and retained only in a bounded in-memory diagnostics queue.
"""
from __future__ import annotations

import os
from collections import deque
from threading import RLock
from typing import Any, Callable


class EdgeTransportRuntime:
    def __init__(self, *, env: dict[str, str] | None = None,
                 manager_factory: Callable[[], Any] | None = None,
                 bridge_factory: Callable[..., Any] | None = None) -> None:
        self._env = os.environ if env is None else env
        self._manager_factory = manager_factory
        self._bridge_factory = bridge_factory
        self._lock = RLock()
        self._manager: Any = None
        self._bridge: Any = None
        self._error: str | None = None
        self._received: deque[dict[str, Any]] = deque(maxlen=1000)

    def enabled(self) -> bool:
        return self._env.get("NEXUS_EDGE_MQTT_ENABLED", "false").strip().lower() == "true"

    def start(self) -> None:
        if not self.enabled():
            return
        with self._lock:
            if self._bridge is not None:
                return
            if self._manager_factory is None:
                from .gateway import create_edge_manager_from_env
                manager_factory = create_edge_manager_from_env
            else:
                manager_factory = self._manager_factory
            if self._bridge_factory is None:
                from .transports import MQTTBridge, mqtt_config_from_env
                bridge_factory = MQTTBridge
                config = mqtt_config_from_env(dict(self._env))
            else:
                bridge_factory = self._bridge_factory
                from .transports import mqtt_config_from_env
                config = mqtt_config_from_env(dict(self._env))
            from .transports import authenticate_mqtt_uplink
            manager = manager_factory()

            def on_message(topic: str, body: dict[str, Any]) -> None:
                accepted = authenticate_mqtt_uplink(manager, topic, body)
                with self._lock:
                    self._received.append(accepted)

            bridge = bridge_factory(config, on_message)
            bridge.start()
            self._manager = manager
            self._bridge = bridge
            self._error = None

    def stop(self) -> None:
        with self._lock:
            bridge, self._bridge = self._bridge, None
            self._manager = None
        if bridge is not None:
            bridge.stop()

    def set_start_error(self, error_type: str) -> None:
        with self._lock:
            self._error = error_type

    def status(self) -> dict[str, Any]:
        with self._lock:
            active = self._bridge is not None and bool(getattr(self._bridge, "started", False))
            return {
                "mqtts": "active" if active else ("enabled_start_failed" if self._error else ("enabled_not_started" if self.enabled() else "disabled_by_default")),
                "enabled": self.enabled(),
                "connected": active,
                "accepted_uplinks_buffered": len(self._received),
                "last_error_type": self._error,
                "wallet_access_enabled": False,
                "miner_autostart_enabled": False,
                "arbitrary_command_execution_enabled": False,
            }
