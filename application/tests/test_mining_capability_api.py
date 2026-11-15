from fastapi.testclient import TestClient
from nexus_master import app


def test_algorithm_capability_catalog_exposes_common_services():
    with TestClient(app) as client:
        response = client.get("/api/mining/capabilities/algorithms")
    assert response.status_code == 200
    data = response.json()
    assert "math_intelligence" in data["common_nexus_services"]
    assert "crypto_engine" in data["common_nexus_services"]
    assert any(x["algorithm_id"] == "RandomX" for x in data["algorithms"])


def test_pool_coverage_is_explicitly_not_live_validation():
    with TestClient(app) as client:
        response = client.get("/api/mining/capabilities/pool-coverage")
    assert response.status_code == 200
    data = response.json()
    assert data["pool_profile_count"] > 0
    assert data["catalog_is_live_validation"] is False


def test_capability_evaluate_blocks_randomx_gpu_and_unknown_pool():
    with TestClient(app) as client:
        blocked = client.post("/api/mining/capabilities/evaluate", json={
            "algorithm": "RandomX", "device": "GPU", "miner_id": "xmrig"
        })
        missing = client.post("/api/mining/capabilities/evaluate", json={
            "algorithm": "RandomX", "device": "CPU", "miner_id": "xmrig",
            "pool_id": "not-a-real-pool"
        })
    assert blocked.status_code == 200
    assert blocked.json()["compatible"] is False
    assert missing.status_code == 404


def test_backend_catalog_and_discovery_are_read_only():
    with TestClient(app) as client:
        catalog = client.get("/api/mining/backends")
        discovery = client.get("/api/mining/backends/discovery")
    assert catalog.status_code == 200
    assert catalog.json()["execution_enabled"] is False
    assert any(x["backend_id"] == "xmrig" for x in catalog.json()["backends"])
    assert discovery.status_code == 200
    assert discovery.json()["execution_enabled"] is False
    assert all(x["operationally_validated"] is False for x in discovery.json()["backends"])


def test_backend_evaluation_enforces_algorithm_device_pair():
    with TestClient(app) as client:
        allowed = client.post("/api/mining/backends/evaluate", json={
            "backend_id": "xmrig", "algorithm": "RandomX", "device_class": "CPU"
        })
        blocked = client.post("/api/mining/backends/evaluate", json={
            "backend_id": "xmrig", "algorithm": "RandomX", "device_class": "GPU"
        })
    assert allowed.status_code == 200
    assert allowed.json()["compatible"] is True
    assert blocked.status_code == 200
    assert blocked.json()["compatible"] is False
