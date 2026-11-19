import os
from pathlib import Path
from fastapi.testclient import TestClient

os.environ.setdefault('NEXUS_DB', '/tmp/nexus_096_solo_test.db')
import nexus_master

client = TestClient(nexus_master.app)


def test_solo_readiness_lists_only_catalog_solo_pools():
    data = client.get('/api/mining/solo-readiness').json()
    assert data['solo_pool_available'] is True
    assert data['local_node_solo']['ready'] is False
    assert data['local_node_solo']['daemon_detected'] is False
    assert all('SOLO' in str(p['mode']).upper() for p in data['eligible_pools'])


def test_solo_config_rejects_pool_without_solo_mode():
    response = client.post('/api/mining/config', json={
        'pool_id': '2miners-rvn-eu', 'wallet': 'R' + 'a' * 30,
        'mining_mode': 'SOLO_POOL', 'miner_id': None, 'device': 'GPU'
    })
    assert response.status_code == 400
    assert 'SOLO' in response.json()['detail']


def test_solo_config_accepts_catalog_solo_pool_without_starting_process():
    response = client.post('/api/mining/config', json={
        'pool_id': '2miners-rvn-solo-eu', 'wallet': 'R' + 'a' * 30,
        'worker': 'nexus-test', 'mining_mode': 'SOLO_POOL', 'device': 'GPU'
    })
    assert response.status_code == 200
    data = response.json()
    assert data['pool_mode'] == 'SOLO'
    assert data['execution'] == 'not_started'
    assert data['mining_mode'] == 'SOLO_POOL'


def test_version_is_0104():
    assert client.get('/api/nexus/master').json()['version'] == '0.10.26'
