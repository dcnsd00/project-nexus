from fastapi.testclient import TestClient

from nexus_master import app
from mining.pool_failover_simulator import standard_failover_scenarios


def test_pool_failover_api_lists_offline_scenarios():
    with TestClient(app) as client:
        response = client.get("/api/mining/pool-failover/scenarios")
    assert response.status_code == 200
    data = response.json()
    assert data["scenario_count"] >= 5
    assert data["execution"] == "simulation_only"
    assert data["network_accessed"] is False
    assert data["miner_started"] is False


def test_pool_failover_api_runs_simulation_without_external_actions():
    events = standard_failover_scenarios()["primary_failure_secondary_healthy"]
    with TestClient(app) as client:
        response = client.post("/api/mining/pool-failover/simulate", json={"events": events})
    assert response.status_code == 200
    data = response.json()
    assert data["active_pool"] == "secondary"
    assert data["failovers"] == 1
    assert data["execution"] == "simulation_only"
    assert data["network_accessed"] is False
    assert data["miner_started"] is False
    assert data["share_submitted"] is False


def test_pool_failover_api_rejects_invalid_policy():
    with TestClient(app) as client:
        response = client.post("/api/mining/pool-failover/simulate", json={
            "events": [], "primary": "same", "secondary": "same"
        })
    assert response.status_code == 400
