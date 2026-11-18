from cryptography.fernet import Fernet
import time

from nexus_edge.manager import EdgeManager, sign_message
from nexus_edge.replay_guard import SQLiteReplayGuard
from nexus_edge.runtime import EdgeTransportRuntime
from nexus_edge.sqlite_store import SQLiteEdgeStore
from nexus_edge.transports import MQTTConfig


class _Bridge:
    def __init__(self, config, callback):
        self.callback = callback
        self.started = False
        self.stops = 0

    def start(self):
        self.started = True

    def stop(self):
        self.started = False
        self.stops += 1


def test_edge_runtime_is_disabled_without_explicit_opt_in():
    calls = []
    runtime = EdgeTransportRuntime(
        env={},
        manager_factory=lambda: calls.append("manager"),
        bridge_factory=_Bridge,
    )
    runtime.start()
    assert calls == []
    assert runtime.status()["mqtts"] == "disabled_by_default"


def test_edge_runtime_reuses_shared_durable_manager_and_authenticates_uplinks(
    monkeypatch, tmp_path
):
    env = {
        "NEXUS_EDGE_MQTT_ENABLED": "true",
        "NEXUS_EDGE_MQTT_HOST": "broker.example",
        "NEXUS_EDGE_MQTT_CLIENT_ID": "nexus-runtime-test",
    }
    database = tmp_path / "edge.sqlite3"
    manager = EdgeManager(
        store=SQLiteEdgeStore(database, encryption_key=Fernet.generate_key()),
        replay_guard=SQLiteReplayGuard(database),
    )
    node_id = "esp32-node-11"
    secret = b"nexus-edge-mqtt-runtime-test-secret"
    manager.register_node(node_id, ["telemetry"], secret)

    monkeypatch.setattr(
        "nexus_edge.transports.mqtt_config_from_env",
        lambda values: MQTTConfig(
            host="broker.example", client_id="nexus-runtime-test"
        ),
    )
    created = []
    runtime = EdgeTransportRuntime(
        env=env,
        manager_factory=lambda: (_ for _ in ()).throw(
            AssertionError("must reuse the LifecycleManager-owned instance")
        ),
        bridge_factory=lambda config, callback: (
            created.append(_Bridge(config, callback)) or created[-1]
        ),
    )

    runtime.start(manager)
    assert len(created) == 1 and created[0].started
    assert runtime._manager is manager

    timestamp = int(time.time())
    payload = {"temperature_c": 21.5}
    signed = {
        "kind": "node_request",
        "action": "mqtt.uplink",
        "node_id": node_id,
        "timestamp": timestamp,
        "sequence": 1,
        "payload": payload,
    }
    body = {
        "timestamp": timestamp,
        "sequence": 1,
        "payload": payload,
        "signature": sign_message(secret, signed),
    }
    created[0].callback(f"nexus/v1/nodes/{node_id}/up", body)

    assert runtime.status()["connected"] is True
    assert runtime.status()["accepted_uplinks_buffered"] == 1
    runtime.stop()
    assert created[0].started is False and created[0].stops == 1


def test_edge_runtime_rejects_ephemeral_manager():
    runtime = EdgeTransportRuntime(
        env={
            "NEXUS_EDGE_MQTT_ENABLED": "true",
            "NEXUS_EDGE_MQTT_HOST": "broker.example",
        },
        bridge_factory=_Bridge,
    )
    try:
        runtime.start(EdgeManager())
    except RuntimeError as exc:
        assert "sqlite_persistent" in str(exc)
    else:
        raise AssertionError("MQTTS must reject in-memory EDGE state")
