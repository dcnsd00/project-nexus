"""Secure transport adapters and network-path capability model for NEXUS EDGE.

LAN, WAN and mobile data are IP paths and use the same TLS-protected protocols.
LoRaWAN is bridged through a LoRaWAN Network Server/webhook; it is not treated
as a transparent IP socket.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Callable


class NetworkPath(str, Enum):
    LAN = "lan"
    WAN = "wan"
    MOBILE_DATA = "mobile_data"
    LORAWAN = "lorawan"
    IOT = "iot"


class TransportKind(str, Enum):
    HTTPS = "https"
    MQTTS = "mqtts"
    LORAWAN_WEBHOOK = "lorawan_webhook"
    IOT_WEBHOOK = "iot_webhook"


PATH_TRANSPORTS: dict[NetworkPath, tuple[TransportKind, ...]] = {
    NetworkPath.LAN: (TransportKind.HTTPS, TransportKind.MQTTS),
    NetworkPath.WAN: (TransportKind.HTTPS, TransportKind.MQTTS),
    NetworkPath.MOBILE_DATA: (TransportKind.HTTPS, TransportKind.MQTTS),
    NetworkPath.LORAWAN: (TransportKind.LORAWAN_WEBHOOK,),
    NetworkPath.IOT: (TransportKind.HTTPS, TransportKind.MQTTS, TransportKind.IOT_WEBHOOK),
}


def transport_matrix() -> dict[str, list[str]]:
    """Return the documented transport options without claiming live connectivity."""
    return {path.value: [kind.value for kind in kinds]
            for path, kinds in PATH_TRANSPORTS.items()}


@dataclass(frozen=True)
class MQTTConfig:
    host: str
    client_id: str
    port: int = 8883
    username: str | None = None
    password: str | None = None
    ca_certs: str | None = None
    client_cert: str | None = None
    client_key: str | None = None
    topic_prefix: str = "nexus/v1"
    keepalive_s: int = 45
    max_message_bytes: int = 65_536

    def validate(self) -> None:
        if not self.host.strip() or not re.fullmatch(r"[A-Za-z0-9._:-]{1,128}", self.client_id):
            raise ValueError("MQTT host and safe client_id are required")
        if not 1 <= self.port <= 65535 or not 10 <= self.keepalive_s <= 600:
            raise ValueError("invalid MQTT port or keepalive")
        if (self.client_cert is None) != (self.client_key is None):
            raise ValueError("MQTT client certificate and key must be supplied together")
        if self.max_message_bytes < 128 or self.max_message_bytes > 1_048_576:
            raise ValueError("invalid MQTT message size limit")
        if not re.fullmatch(r"[A-Za-z0-9/_-]{1,96}", self.topic_prefix):
            raise ValueError("invalid MQTT topic prefix")


class MQTTBridge:
    """Opt-in MQTTS client; payload authorization remains the EDGE manager's job."""

    def __init__(self, config: MQTTConfig, on_message: Callable[[str, dict[str, Any]], None],
                 *, client_factory: Callable[..., Any] | None = None) -> None:
        config.validate()
        self.config = config
        self.on_message = on_message
        self._client_factory = client_factory
        self._client: Any = None
        self.started = False
        self.connected = False
        self.rejected_messages = 0
        self.last_message_error_type: str | None = None

    def _factory(self) -> Callable[..., Any]:
        if self._client_factory is not None:
            return self._client_factory
        try:
            import paho.mqtt.client as mqtt
        except ImportError as exc:
            raise RuntimeError("install optional dependency paho-mqtt>=2,<3 to enable MQTTS") from exc
        return lambda **kwargs: mqtt.Client(
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2, **kwargs
        )

    def start(self) -> None:
        if self.started:
            return
        client = self._factory()(client_id=self.config.client_id)
        try:
            if self.config.username is not None:
                client.username_pw_set(self.config.username, self.config.password)
            client.tls_set(
                ca_certs=self.config.ca_certs,
                certfile=self.config.client_cert,
                keyfile=self.config.client_key,
            )
            client.tls_insecure_set(False)
            client.on_message = self._handle_message
            client.on_connect = self._on_connect
            client.on_disconnect = self._on_disconnect
            result = client.connect(
                self.config.host, self.config.port, self.config.keepalive_s
            )
            if result not in (None, 0):
                raise RuntimeError("MQTT client rejected the connection request")
            self._client = client
            client.loop_start()
            self.started = True
        except Exception:
            self.connected = False
            self.started = False
            self._client = None
            for method in ("disconnect", "loop_stop"):
                try:
                    getattr(client, method)()
                except Exception:
                    pass
            raise

    def _on_connect(
        self, client: Any, userdata: Any, flags: Any,
        reason_code: Any, properties: Any = None,
    ) -> None:
        try:
            accepted = int(reason_code) == 0
        except (TypeError, ValueError):
            accepted = str(reason_code).strip().lower() in {"0", "success"}
        self.connected = accepted
        if not accepted:
            self.last_message_error_type = "BrokerConnectionRejected"
            return
        result = client.subscribe(
            f"{self.config.topic_prefix}/nodes/+/up", qos=1
        )
        result_code = result[0] if isinstance(result, tuple) else result
        if result_code not in (None, 0):
            self.connected = False
            self.last_message_error_type = "SubscriptionRejected"

    def _on_disconnect(self, client: Any, userdata: Any, *args: Any) -> None:
        self.connected = False

    def _handle_message(self, client: Any, userdata: Any, message: Any) -> None:
        try:
            raw = bytes(message.payload)
            if len(raw) > self.config.max_message_bytes:
                raise ValueError("message exceeds configured size limit")
            body = json.loads(raw.decode("utf-8"))
            if not isinstance(body, dict):
                raise ValueError("MQTT message must contain a JSON object")
            self.on_message(str(message.topic), body)
        except Exception as exc:
            # Never let malformed or unauthenticated broker messages terminate
            # the Paho network-loop callback. Record type only, not payload.
            self.rejected_messages += 1
            self.last_message_error_type = type(exc).__name__

    def publish_downlink(self, node_id: str, payload: dict[str, Any]) -> None:
        if not self.started or self._client is None:
            raise RuntimeError("MQTTS bridge is not started")
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]{2,63}", node_id):
            raise ValueError("invalid node_id")
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"),
                             ensure_ascii=False, allow_nan=False).encode("utf-8")
        if len(encoded) > self.config.max_message_bytes:
            raise ValueError("MQTT payload exceeds configured limit")
        result = self._client.publish(
            f"{self.config.topic_prefix}/nodes/{node_id}/down", encoded, qos=1, retain=False
        )
        if getattr(result, "rc", 0) != 0:
            raise RuntimeError("MQTT broker rejected downlink publish")

    def stop(self) -> None:
        if self._client is not None:
            self._client.disconnect()
            self._client.loop_stop()
        self._client = None
        self.started = False
        self.connected = False


def mqtt_config_from_env(env: dict[str, str] | None = None) -> MQTTConfig:
    """Read optional MQTT settings; no network activity occurs in this function."""
    import os
    source = os.environ if env is None else env
    host = source.get("NEXUS_EDGE_MQTT_HOST", "")
    if not host:
        raise RuntimeError("NEXUS_EDGE_MQTT_HOST is not configured")
    return MQTTConfig(
        host=host,
        client_id=source.get("NEXUS_EDGE_MQTT_CLIENT_ID", "nexus-edge-gateway"),
        port=int(source.get("NEXUS_EDGE_MQTT_PORT", "8883")),
        username=source.get("NEXUS_EDGE_MQTT_USERNAME"),
        password=source.get("NEXUS_EDGE_MQTT_PASSWORD"),
        ca_certs=source.get("NEXUS_EDGE_MQTT_CA"),
        client_cert=source.get("NEXUS_EDGE_MQTT_CERT"),
        client_key=source.get("NEXUS_EDGE_MQTT_KEY"),
        topic_prefix=source.get("NEXUS_EDGE_MQTT_TOPIC_PREFIX", "nexus/v1"),
    )

def authenticate_mqtt_uplink(manager: Any, topic: str, body: dict[str, Any], *,
                             topic_prefix: str = "nexus/v1") -> dict[str, Any]:
    """Validate a configured MQTTS topic/envelope and consume its node sequence exactly once."""
    if not isinstance(topic_prefix, str) or not re.fullmatch(r"[A-Za-z0-9/_-]{1,96}", topic_prefix):
        raise ValueError("invalid NEXUS MQTT topic prefix")
    pattern = re.escape(topic_prefix) + r"/nodes/([A-Za-z0-9][A-Za-z0-9._:-]{2,63})/up"
    match = re.fullmatch(pattern, topic)
    if not match:
        raise ValueError("unexpected NEXUS MQTT uplink topic")
    required = {"timestamp", "sequence", "payload", "signature"}
    if set(body) != required or not isinstance(body["payload"], dict):
        raise ValueError("invalid MQTT uplink envelope")
    node_id = match.group(1)
    manager.authenticate_request(
        node_id, "mqtt.uplink", body["timestamp"], body["sequence"],
        body["payload"], body["signature"],
    )
    return {"accepted": True, "node_id": node_id, "transport": "mqtts",
            "payload": body["payload"]}
