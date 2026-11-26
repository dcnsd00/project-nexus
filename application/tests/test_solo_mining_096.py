import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi.testclient import TestClient
import pytest

os.environ.setdefault('NEXUS_DB', '/tmp/nexus_096_solo_test.db')
import nexus_master


@pytest.fixture(scope="module")
def client():
    # Readiness/configuration routes are tested without starting mining or
    # the full service graph; TestClient still owns and closes its portal.
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


def test_solo_readiness_lists_only_catalog_solo_pools(client):
    data = client.get('/api/mining/solo-readiness').json()
    assert data['solo_pool_available'] is True
    assert data['local_node_solo']['ready'] is False
    assert data['local_node_solo']['daemon_detected'] is False
    assert all('SOLO' in str(p['mode']).upper() for p in data['eligible_pools'])


def test_solo_config_rejects_pool_without_solo_mode(client):
    response = client.post('/api/mining/config', json={
        'pool_id': '2miners-rvn-eu', 'wallet': 'R' + 'a' * 30,
        'mining_mode': 'SOLO_POOL', 'miner_id': None, 'device': 'GPU'
    })
    assert response.status_code == 400
    assert 'SOLO' in response.json()['detail']


def test_solo_config_accepts_catalog_solo_pool_without_starting_process(client):
    response = client.post('/api/mining/config', json={
        'pool_id': '2miners-rvn-solo-eu', 'wallet': 'R' + 'a' * 30,
        'worker': 'nexus-test', 'mining_mode': 'SOLO_POOL', 'device': 'GPU'
    })
    assert response.status_code == 200
    data = response.json()
    assert data['pool_mode'] == 'SOLO'
    assert data['execution'] == 'not_started'
    assert data['mining_mode'] == 'SOLO_POOL'


def test_version_is_0104(client):
    assert client.get('/api/nexus/master').json()['version'] == '0.10.27'
