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
