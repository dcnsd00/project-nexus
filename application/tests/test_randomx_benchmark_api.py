from contextlib import asynccontextmanager

from fastapi.testclient import TestClient
import pytest
import nexus_master as nm


@pytest.fixture(scope="module")
def client():
    # The route tests do not require NEXUS runtime services or mining workers.
    original_lifespan = nm.app.router.lifespan_context

    @asynccontextmanager
    async def route_test_lifespan(_app):
        yield

    nm.app.router.lifespan_context = route_test_lifespan
    try:
        with TestClient(nm.app) as test_client:
            yield test_client
    finally:
        nm.app.router.lifespan_context = original_lifespan


def test_randomx_twenty_block_api_forwards_bounded_benchmark(monkeypatch, client):
    seen = {}

    def fake_runner(threads, hashes_per_block, timeout_seconds=300):
        seen.update(threads=threads, hashes_per_block=hashes_per_block,
                    timeout_seconds=timeout_seconds)
        return {"state": "completed", "algorithm": "RandomX",
                "block_count": 20, "hashrate_hs": 1234.5,
                "pool_connected": False}

    monkeypatch.setattr(nm, "run_randomx_synthetic_blocks_benchmark", fake_runner)
    response = client.post("/api/mining/randomx/20block-benchmark",
                           json={"threads": 4, "hashes_per_block": 1500})
    assert response.status_code == 200
    assert response.json()["hashrate_hs"] == 1234.5
    assert seen["threads"] == 4
    assert seen["hashes_per_block"] == 1500


def test_randomx_twenty_block_api_rejects_invalid_hash_count(client):
    response = client.post("/api/mining/randomx/20block-benchmark",
                           json={"threads": 4, "hashes_per_block": 10})
    assert response.status_code == 400
