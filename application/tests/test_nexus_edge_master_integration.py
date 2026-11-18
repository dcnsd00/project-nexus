from fastapi.testclient import TestClient

import nexus_master


def test_master_injects_one_lifecycle_owned_manager_into_both_network_adapters(monkeypatch, tmp_path):
    from modules import data_paths

    monkeypatch.setattr(data_paths, "DATA_DIR", tmp_path / "nexus-data")
    monkeypatch.delenv("NEXUS_EDGE_DATABASE", raising=False)
    monkeypatch.delenv("NEXUS_EDGE_STORAGE_KEY", raising=False)
    observed = {}

    monkeypatch.setattr(nexus_master._edge_transport, "enabled", lambda: True)
    monkeypatch.setattr(nexus_master._edge_gateway_runtime, "enabled", lambda: True)

    def start_mqtt(manager=None):
        observed["mqtt"] = manager

    def start_https(host_app, manager=None):
        observed["https"] = manager

    monkeypatch.setattr(nexus_master._edge_transport, "start", start_mqtt)
    monkeypatch.setattr(nexus_master._edge_gateway_runtime, "start", start_https)

    with TestClient(nexus_master.app):
        runtime = nexus_master.app.state.nexus_runtime
        expected = runtime.get_service_instance("edge_manager").service.manager
        assert observed["mqtt"] is expected
        assert observed["https"] is expected
        assert observed["mqtt"] is observed["https"]
