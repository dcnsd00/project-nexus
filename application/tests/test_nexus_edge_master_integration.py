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
