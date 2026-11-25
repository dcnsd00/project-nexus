from contextlib import asynccontextmanager

from fastapi.testclient import TestClient
import pytest
import nexus_master


@pytest.fixture(scope="module")
def client():
    # This probe route test does not need the full runtime service graph.
    original_lifespan = nexus_master.app.router.lifespan_context

    @asynccontextmanager
    async def route_test_lifespan(_app):
        yield

    nexus_master.app.router.lifespan_context = route_test_lifespan
    try:
        with TestClient(nexus_master.app) as test_client:
            yield test_client
    finally:
        nexus_master.app.router.lifespan_context = original_lifespan


def test_stratum_probe_uses_operator_tls_hostname(monkeypatch, client):
    seen = {}

    def fake(host, port, username, password, use_tls, timeout):
        seen.update(host=host, port=port, username=username, tls=use_tls)
        return {"ok": False, "stage": "mock", "no_work_requested": True}

    monkeypatch.setattr(nexus_master, "probe_stratum", fake)
    response = client.post("/api/mining/stratum-probe", json={
        "pool_id": "2miners-rvn-solo-eu", "wallet": "R" + "a" * 33,
        "worker": "rig1", "use_tls": True
    })
    assert response.status_code == 200
    assert seen["host"] == "solo-rvn.2miners.com"
    assert seen["port"] == 17070
    assert seen["tls"] is True
    assert seen["username"].endswith(".rig1")
