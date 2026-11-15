import os
from fastapi.testclient import TestClient

os.environ.setdefault('NEXUS_WALLET_DB', '/tmp/nexus-1023-api/wallet.db')
os.environ.setdefault('NEXUS_DB', '/tmp/nexus-1023-api/core.db')
from nexus_master import app, hybrid_supervisor


def test_mode_api_selects_exclusive_mode_and_reports_status():
    with TestClient(app) as client:
        hybrid_supervisor.stop_mode()
        a = client.post('/api/mining/mode/standard/start')
        assert a.status_code == 200
        status = client.get('/api/mining/hybrid/status').json()
        assert status['mode'] == 'standard'
        b = client.post('/api/mining/mode/development/start')
        assert b.status_code == 409
        assert client.post('/api/mining/mode/standard/stop').status_code == 200


def test_api_does_not_execute_binary_outside_miner_inventory():
    with TestClient(app) as client:
        hybrid_supervisor.stop_mode()
        client.post('/api/mining/mode/standard/start')
        response = client.post('/api/mining/hybrid/engine/cpu/start', json={
            'binary_path': '/tmp/untrusted-executable', 'args': [], 'miner_id': 'unknown', 'pool_id': 'unmineable-randomx-xmr', 'algorithm': 'RandomX'
        })
        assert response.status_code == 409
        client.post('/api/mining/mode/standard/stop')


def test_optimizer_api_is_recommendation_only():
    with TestClient(app) as client:
        response = client.post('/api/mining/hybrid/optimize/plan', json={'baseline': {}, 'candidates': []})
        assert response.status_code == 200
        assert response.json()['automatic_application'] is False
        assert response.json()['execution'] == 'recommendation_only'


def test_development_api_uses_local_regtest_executor_only():
    with TestClient(app) as client:
        hybrid_supervisor.stop_mode()
        assert client.post('/api/mining/mode/development/start').status_code == 200
        response = client.post('/api/mining/hybrid/engine/cpu/start', json={
            'network': 'regtest', 'algorithm': 'sha256d', 'attempts': 1000
        })
        assert response.status_code == 200
        assert response.json()['started'] is True
        gpu = client.post('/api/mining/hybrid/engine/gpu/start', json={
            'network': 'regtest', 'algorithm': 'sha256d'
        })
        assert gpu.status_code == 409
        invalid = client.post('/api/mining/hybrid/start', json={
            'mode': 'development', 'cpu': {'network': 'mainnet', 'algorithm': 'sha256d'}
        })
        assert invalid.status_code == 400
        client.post('/api/mining/mode/development/stop')


def test_api_maps_invalid_requests_to_client_errors_not_server_errors():
    with TestClient(app) as client:
        assert client.post('/api/mining/mode/unknown/stop').status_code == 400
        assert client.post('/api/mining/hybrid/engine/cpu/start', json={}).status_code in (409, 422)
        assert client.post('/api/mining/hybrid/optimize/plan', json={'baseline': 'bad'}).status_code == 422


def test_randomx_benchmark_api_is_offline_and_reports_missing_backend_truthfully():
    with TestClient(app) as client:
        response = client.post('/api/mining/randomx/benchmark', json={'threads': [1], 'dataset': '1M'})
        assert response.status_code == 200
        data = response.json()
        assert data['algorithm'] == 'RandomX'
        assert data['automatic_application'] is False
        assert data['pool_shares_required_for_production_decision'] is True
        assert data['results'][0]['pool_connected'] is False
        assert data['results'][0]['state'] in ('backend_unavailable', 'completed')


def test_randomx_benchmark_api_rejects_unbounded_thread_sweeps():
    with TestClient(app) as client:
        response = client.post('/api/mining/randomx/benchmark', json={'threads': list(range(1, 10))})
        assert response.status_code == 400
