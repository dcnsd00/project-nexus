from fastapi.testclient import TestClient

import nexus_master


def test_master_injects_one_lifecycle_owned_manager_into_both_network_adapters(monkeypatch, tmp_path):
    from modules import data_paths

    monkeypatch.setattr(data_paths, "DATA_DIR", tmp_path / "nexus-data")
    monkeypatch.delenv("NEXUS_EDGE_DATABASE", raising=False)
    monkeypatch.delenv("NEXUS_EDGE_STORAGE_KEY", raising=False)
    monkeypatch.delenv("NEXUS_DEPLOYMENT_MODE", raising=False)
    monkeypatch.delenv("NEXUS_SERVER_COUNT", raising=False)
    monkeypatch.delenv("NEXUS_STATE_BACKEND", raising=False)
    observed = {}

    monkeypatch.setattr(nexus_master._edge_transport, "enabled", lambda: True)
    monkeypatch.setattr(nexus_master._edge_gateway_runtime, "enabled", lambda: True)

    def start_mqtt(manager=None):
        observed["mqtt"] = manager

    def start_https(host_app, manager=None):
        observed["https"] = manager

    monkeypatch.setattr(nexus_master._edge_transport, "start", start_mqtt)
    monkeypatch.setattr(nexus_master._edge_gateway_runtime, "start", start_https)

    with TestClient(nexus_master.app) as client:
        runtime = nexus_master.app.state.nexus_runtime
        expected = runtime.get_service_instance("edge_manager").service.manager
        assert observed["mqtt"] is expected
        assert observed["https"] is expected
        assert observed["mqtt"] is observed["https"]
        topology = client.get("/api/edge/topology").json()
        assert topology["mode"] == "single"
        assert topology["configuration_validated"] is True
        assert topology["operational_failover_verified"] is False
        assert client.get("/api/edge/nodes").json()["state"] == "available"
        assert client.get("/api/edge/tasks").json()["tasks"] == []
        expected.telemetry = lambda limit=100: [{
            "event_id": 1, "node_id": "edge-c5-001", "sequence": 1,
            "transport": "https", "payload": {"sensitive": "not-in-master-status"},
        }]
        telemetry_status = client.get("/api/edge/telemetry").json()
        assert telemetry_status["events"][0]["event_id"] == 1
        assert "payload" not in telemetry_status["events"][0]


def test_master_rejects_active_active_topology_with_local_sqlite(monkeypatch, tmp_path):
    from pytest import raises
    from modules import data_paths

    monkeypatch.setattr(data_paths, "DATA_DIR", tmp_path / "nexus-data")
    monkeypatch.setenv("NEXUS_DEPLOYMENT_MODE", "active_active")
    monkeypatch.setenv("NEXUS_SERVER_COUNT", "2")
    monkeypatch.setenv("NEXUS_STATE_BACKEND", "sqlite")
    monkeypatch.setenv("NEXUS_SHARED_STATE", "false")
    monkeypatch.setenv("NEXUS_DISTRIBUTED_TASK_CLAIMS", "false")

    with raises(ValueError, match="active-active requires a shared transactional database"):
        with TestClient(nexus_master.app):
            pass

def test_master_still_stops_core_services_when_optional_edge_shutdown_fails(monkeypatch, tmp_path):
    from modules import data_paths

    monkeypatch.setattr(data_paths, "DATA_DIR", tmp_path / "nexus-data")
    monkeypatch.delenv("NEXUS_EDGE_DATABASE", raising=False)
    monkeypatch.delenv("NEXUS_EDGE_STORAGE_KEY", raising=False)

    def fail_gateway_stop(*args, **kwargs):
        raise OSError("gateway shutdown failure")

    def fail_mqtt_stop(*args, **kwargs):
        raise OSError("MQTT shutdown failure")

    monkeypatch.setattr(nexus_master._edge_gateway_runtime, "stop", fail_gateway_stop)
    monkeypatch.setattr(nexus_master._edge_transport, "stop", fail_mqtt_stop)

    with TestClient(nexus_master.app):
        runtime = nexus_master.app.state.nexus_runtime
        assert runtime.snapshot()["running"] > 0

    assert runtime.snapshot()["running"] == 0
    assert nexus_master.app.state.nexus_runtime is None

def test_master_end_to_end_shared_manager_https_and_mqtts_telemetry(monkeypatch, tmp_path):
    import base64
    import time
    from cryptography.fernet import Fernet
    from modules import data_paths
    from nexus_edge.gateway_runtime import EdgeGatewayRuntime
    from nexus_edge.manager import sign_message
    from nexus_edge.runtime import EdgeTransportRuntime

    database = tmp_path / "edge.sqlite3"
    token = "operator-token-" + "x" * 40
    monkeypatch.setattr(data_paths, "DATA_DIR", tmp_path / "nexus-data")
    monkeypatch.setenv("NEXUS_EDGE_DATABASE", str(database))
    monkeypatch.setenv("NEXUS_EDGE_STORAGE_KEY", Fernet.generate_key().decode("ascii"))
    monkeypatch.setenv("NEXUS_EDGE_PROVISIONING_TOKEN", token)
    monkeypatch.setenv("NEXUS_EDGE_GATEWAY_ENABLED", "true")
    monkeypatch.setenv("NEXUS_EDGE_MQTT_ENABLED", "true")
    monkeypatch.setenv("NEXUS_EDGE_MQTT_HOST", "broker.example")
    monkeypatch.setenv("NEXUS_EDGE_MQTT_USERNAME", "nexus")
    monkeypatch.setenv("NEXUS_EDGE_MQTT_PASSWORD", "test-password")
    monkeypatch.delenv("NEXUS_DEPLOYMENT_MODE", raising=False)
    monkeypatch.delenv("NEXUS_SERVER_COUNT", raising=False)
    monkeypatch.delenv("NEXUS_STATE_BACKEND", raising=False)

    class FakeBridge:
        def __init__(self, config, on_message):
            self.config = config
            self.callback = on_message
            self.started = False
            self.connected = False

        def start(self):
            self.started = True
            self.connected = True

        def stop(self):
            self.started = False
            self.connected = False

        def status(self):
            return {"started": self.started, "connected": self.connected}

    gateway_runtime = EdgeGatewayRuntime()
    transport_runtime = EdgeTransportRuntime(
        bridge_factory=lambda config, on_message: FakeBridge(config, on_message)
    )
    monkeypatch.setattr(nexus_master, "_edge_gateway_runtime", gateway_runtime)
    monkeypatch.setattr(nexus_master, "_edge_transport", transport_runtime)

    with TestClient(nexus_master.app) as client:
        runtime = nexus_master.app.state.nexus_runtime
        manager = runtime.get_service_instance("edge_manager").service.manager
        assert gateway_runtime._mounted_app.state.edge_manager is manager
        assert transport_runtime._manager is manager
        assert transport_runtime.status()["mqtts"] == "active"

        provisioned = client.post(
            "/edge/v1/edge/nodes/provision",
            headers={"Authorization": "Bearer " + token},
            json={"node_id": "esp32-shared-001", "capabilities": ["telemetry"]},
        )
        assert provisioned.status_code == 200
        secret = base64.urlsafe_b64decode(
            provisioned.json()["node_secret_b64url"]
        )
        assert provisioned.json()["minimum_next_sequence"] == 1

        node_id = "esp32-shared-001"
        mqtt_payload = {"temperature_c": 20.5, "source": "mqtt"}
        mqtt_timestamp = int(time.time())
        mqtt_message = {
            "kind": "node_request",
            "action": "mqtt.uplink",
            "node_id": node_id,
            "timestamp": mqtt_timestamp,
            "sequence": 1,
            "payload": mqtt_payload,
        }
        mqtt_body = {
            "timestamp": mqtt_timestamp,
            "sequence": 1,
            "payload": mqtt_payload,
            "signature": sign_message(secret, mqtt_message),
        }
        transport_runtime._bridge.callback(
            f"nexus/v1/nodes/{node_id}/up", mqtt_body
        )

        https_payload = {"temperature_c": 21.0, "source": "https"}
        https_timestamp = int(time.time())
        https_message = {
            "kind": "node_request",
            "action": "https.uplink",
            "node_id": node_id,
            "timestamp": https_timestamp,
            "sequence": 2,
            "payload": https_payload,
        }
        https_response = client.post(
            f"/edge/v1/edge/nodes/{node_id}/uplink/https",
            json={
                "timestamp": https_timestamp,
                "sequence": 2,
                "payload": https_payload,
                "signature": sign_message(secret, https_message),
            },
        )
        assert https_response.status_code == 200

        history = manager.telemetry(limit=10)
        assert [event["transport"] for event in history] == ["https", "mqtts"]
        assert [event["sequence"] for event in history] == [2, 1]
        assert client.get("/api/edge/telemetry").json()["events"][0].get("payload") is None

