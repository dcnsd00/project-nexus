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

    def start(self, manager: Any | None = None) -> None:
        if not self.enabled():
            return
        with self._lock:
            if self._bridge is not None:
                return
            edge_manager = manager
            if edge_manager is None:
                if self._manager_factory is None:
                    from .gateway import create_edge_manager_from_env
                    manager_factory = create_edge_manager_from_env
                else:
                    manager_factory = self._manager_factory
                edge_manager = manager_factory()
            snapshot = edge_manager.snapshot()
            if snapshot.get("mode") != "sqlite_persistent":
                raise RuntimeError(
                    "MQTTS requires the shared sqlite_persistent EDGE manager; "
                    "configure NEXUS_EDGE_STORAGE_KEY"
                )
            if self._bridge_factory is None:
                from .transports import MQTTBridge, mqtt_config_from_env
                bridge_factory = MQTTBridge
                config = mqtt_config_from_env(dict(self._env))
            else:
                bridge_factory = self._bridge_factory
                from .transports import mqtt_config_from_env
                config = mqtt_config_from_env(dict(self._env))
            from .transports import authenticate_mqtt_uplink

            def on_message(topic: str, body: dict[str, Any]) -> None:
                accepted = authenticate_mqtt_uplink(
                    edge_manager, topic, body, topic_prefix=config.topic_prefix
                )
                event = edge_manager.record_telemetry(
                    accepted["node_id"], accepted["payload"], transport="mqtts"
                )
                with self._lock:
                    self._received.append({
                        "accepted": True,
                        "node_id": event["node_id"],
                        "event_id": event["event_id"],
                        "transport": event["transport"],
                        "payload_sha256": event["payload_sha256"],
                    })

            bridge = bridge_factory(config, on_message)
            bridge.start()
            self._manager = edge_manager
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
            bridge = self._bridge
            started = bridge is not None and bool(getattr(bridge, "started", False))
            connected = bridge is not None and bool(
                getattr(bridge, "connected", started)
            )
            return {
                "mqtts": "active" if connected else (
                    "enabled_start_failed" if self._error else (
                        "enabled_connecting_or_disconnected" if started else (
                            "enabled_not_started" if self.enabled() else "disabled_by_default"
                        )
                    )
                ),
                "enabled": self.enabled(),
                "started": started,
                "connected": connected,
                "accepted_uplinks_buffered": len(self._received),
                "rejected_uplinks": int(getattr(bridge, "rejected_messages", 0)),
                "last_message_error_type": getattr(
                    bridge, "last_message_error_type", None
                ),
                "last_error_type": self._error,
                "wallet_access_enabled": False,
                "miner_autostart_enabled": False,
                "arbitrary_command_execution_enabled": False,
            }
