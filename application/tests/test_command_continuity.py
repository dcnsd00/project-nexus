"""End-to-end command-surface continuity tests for the NEXUS MASTER app."""
from fastapi.testclient import TestClient

from nexus_master import app


READ_ONLY_STATUS_ENDPOINTS = (
    "/api/nexus/master",
    "/api/nexus/readiness",
    "/api/nexus/modules",
    "/api/nexus/module-registry",
    "/api/nexus/module-registry/health",
    "/api/nexus/runtime",
    "/api/nexus/telemetry",
    "/api/mining/hardware",
    "/api/mining/miners",
    "/api/mining/status",
    "/api/mining/processes",
    "/api/mining/diagnostics",
    "/api/mining/pools",
    "/api/mining/capabilities/algorithms",
    "/api/crypto/algorithms",
    "/api/research/sha2/status",
    "/api/research/rcsc/status",
    "/api/math/hybrid/capabilities",
    "/api/edge/transports",
    "/api/edge/gateway",
    "/api/wallet/status",
)


def test_master_command_surface_status_endpoints_are_reachable():
    with TestClient(app) as client:
        for endpoint in READ_ONLY_STATUS_ENDPOINTS:
            response = client.get(endpoint)
            assert response.status_code == 200, (
                endpoint, response.status_code, response.text[:500]
            )


def test_dashboard_is_served_and_uses_live_telemetry_contract():
    with TestClient(app) as client:
        response = client.get("/api/nexus/dashboard")
        assert response.status_code == 200
        assert "resourceChart" in response.text
        assert "pollTelemetry" in response.text
        telemetry = client.get("/api/nexus/telemetry?history=5")
        assert telemetry.status_code == 200
        body = telemetry.json()
        assert body["snapshot"]["cpu"]["utilization_percent"] is not None
        assert body["snapshot"]["memory"]["utilization_percent"] is not None
        assert isinstance(body["history"], list)


def test_mining_start_stop_commands_are_connected_to_supervisor(monkeypatch):
    from mining import controller as mining_controller
    import nexus_master

    class FakeProcess:
        def __init__(self, args, **kwargs):
            self.args = args
            self.kwargs = kwargs
            self.pid = 987654
            self.returncode = None

        def poll(self):
            return self.returncode

        def terminate(self):
            self.returncode = 0

        def wait(self, timeout=None):
            return self.returncode

        def kill(self):
            self.returncode = -9

    monkeypatch.setattr(mining_controller, "_resolve_binary",
                        lambda miner_id, explicit_path=None: "C:/fake/SRBMiner-MULTI.exe")
    monkeypatch.setattr(mining_controller.subprocess, "Popen", FakeProcess)
    monkeypatch.setattr(mining_controller, "_metrics", lambda: {
        "api_connected": False, "hashrate_hs": None, "hashrate_display": None,
        "accepted_shares": None, "rejected_shares": None, "gpu": {},
        "system": {}, "raw_api": None,
    })
    monkeypatch.setattr(nexus_master, "_nvidia", lambda: {
        "available": True, "gpus": [{"name": "test GPU", "memory_mib": "8192"}]
    })

    with TestClient(app) as client:
        client.post("/api/mining/stop")
        started = client.post("/api/mining/start", json={
            "miner_id": "srbminer",
            "pool_id": "2miners-rvn-eu",
            "wallet": "RWalletExample123",
            "worker": "nexus-ci-test",
            "algorithm": "KawPoW",
            "device": "GPU",
        })
        assert started.status_code == 200, started.text
        assert started.json()["status"] == "running"
        assert started.json()["pid"] == 987654
        status = client.get("/api/mining/status")
        assert status.status_code == 200
        stopped = client.post("/api/mining/stop")
        assert stopped.status_code == 200
        assert stopped.json()["status"] == "stopped"


def test_master_starts_and_reports_the_local_runtime_graph():
    with TestClient(app) as client:
        response = client.get("/api/nexus/runtime")
        assert response.status_code == 200
        body = response.json()
        assert body["system_ready"] is True
        assert body["running"] == body["total"]
        services = {row["name"]: row for row in body["services"]}
        assert services["crypto_engine"]["state"] == "running"
        assert services["data_paths"]["state"] == "running"
        assert services["edge_manager"]["state"] == "running"
        assert services["edge_manager"]["health"]["mode"] == "local_control_plane_no_transport"
        registry = client.get("/api/nexus/module-registry").json()
        edge = next(row for row in registry["modules"] if row["id"] == "edge_manager")
        assert edge["runtime_registered"] is True
        assert edge["operational_verified"] is False


def test_unified_operator_snapshot_is_read_only_and_reports_evidence_boundaries():
    with TestClient(app) as client:
        response = client.get("/api/nexus/operator")
        assert response.status_code == 200
        body = response.json()
        assert body["product"] == "NEXUS"
        assert body["safety"]["read_only"] is True
        assert body["safety"]["starts_or_stops_miners"] is False
        assert body["execution_model"]["services_share_master_process"] is True
        assert body["execution_model"]["individual_service_pids"].startswith("not_applicable")
        assert body["evidence_policy"]["missing_values"].startswith("reported_as_unavailable")
        assert body["summary"]["services_total"] >= 1
        assert isinstance(body["services"], list)
