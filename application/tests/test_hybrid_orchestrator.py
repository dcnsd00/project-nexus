import pytest
from mining.hybrid_orchestrator import build_hybrid_plan


def test_hybrid_plan_separates_cpu_randomx_and_gpu_pearlpow_without_claiming_execution():
    pools = [
        {"id":"cpu", "coin":"XMR", "algorithm":"RandomX", "name":"CPU pool", "miner":"XMRig / SRBMiner-MULTI"},
        {"id":"gpu", "coin":"BTC", "algorithm":"PearlPow", "name":"GPU pool", "miner":"Compatible miner"},
    ]
    inventory = {"miners":[
        {"id":"xmrig", "name":"XMRig", "available":True, "path":"/miners/xmrig"},
        {"id":"srbminer", "name":"SRBMiner", "available":True, "path":"/miners/srbminer"},
    ]}
    def compatible(pool, miner, device):
        return {"compatible": (miner == "xmrig" if device == "CPU" else miner == "srbminer"), "reasons": []}
    plan = build_hybrid_plan(pools=pools, inventory=inventory, cpu_pool_id="cpu", gpu_pool_id="gpu",
                             compatibility=compatible, hardware={"gpu":{"available":True}})
    assert plan["engines"]["cpu"]["algorithm"] == "RandomX"
    assert plan["engines"]["gpu"]["algorithm"] == "PearlPow"
    assert plan["engines"]["cpu"]["selected"]["miner_id"] == "xmrig"
    assert plan["engines"]["gpu"]["selected"]["miner_id"] == "srbminer"
    assert plan["ready_for_supervisor"] is True
    assert plan["simultaneous_execution_enabled"] is False
    assert plan["execution"] == "plan_only"


def test_hybrid_plan_rejects_wrong_cpu_algorithm():
    with pytest.raises(ValueError, match="RandomX"):
        build_hybrid_plan(pools=[{"id":"cpu","algorithm":"SHA-256d"},{"id":"gpu","algorithm":"PearlPow"}],
                          inventory={"miners":[]}, cpu_pool_id="cpu", gpu_pool_id="gpu",
                          compatibility=lambda *_: {"compatible":False})


def test_hybrid_plan_blocks_when_gpu_backend_not_available():
    pools=[{"id":"cpu","algorithm":"RandomX"},{"id":"gpu","algorithm":"PearlPow"}]
    plan=build_hybrid_plan(pools=pools, inventory={"miners":[]}, cpu_pool_id="cpu", gpu_pool_id="gpu",
                           compatibility=lambda *_: {"compatible":False,"reasons":["not installed"]})
    assert plan["ready_for_supervisor"] is False
    assert plan["engines"]["gpu"]["status"] == "no_compatible_backend"


def test_hybrid_plan_api_returns_explicit_plan_only_status():
    from fastapi.testclient import TestClient
    from nexus_master import app
    with TestClient(app) as client:
        response = client.post('/api/mining/hybrid/plan', json={
            'cpu_pool_id': 'unmineable-randomx-xmr',
            'gpu_pool_id': 'kryptex-prl-global',
        })
    assert response.status_code == 200
    data = response.json()
    assert data['execution'] == 'plan_only'
    assert data['simultaneous_execution_enabled'] is False
    assert set(data['engines']) == {'cpu', 'gpu'}
