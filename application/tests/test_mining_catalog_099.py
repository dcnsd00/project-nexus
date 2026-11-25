import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def test_bitcoin_and_nerdminer_pool_entries_exist():
    pools=json.loads((ROOT/'mining'/'pools.json').read_text())['pools']
    ids={p['id'] for p in pools}
    assert {'public-pool-btc-solo','public-pool-btc-pplns','nerdminer-public-pool-lowdiff','kryptex-btc-eu','unmineable-sha256-btc'} <= ids


def test_nerdminer_endpoint_is_external_low_difficulty_solo():
    pools=json.loads((ROOT/'mining'/'pools.json').read_text())['pools']
    p=next(x for x in pools if x['id']=='nerdminer-public-pool-lowdiff')
    assert (p['host'],p['port'],p['coin'],p['algorithm'],p['mode']) == ('web.public-pool.io',21496,'BTC','SHA-256d','SOLO')
    assert 'ESP32' in p['device_class']
    from mining.controller import MINERS
    assert MINERS['nerdminer']['external_device'] is True and MINERS['nerdminer']['device']==['ESP32']


def test_randomx_is_cpu_only_in_srbminer_and_xmrig():
    from mining.controller import MINERS
    assert 'RandomX' in MINERS['xmrig']['algorithms'] and MINERS['xmrig']['device']==['CPU']
    assert 'RandomX' in MINERS['srbminer']['algorithms']
    assert 'CPU' in MINERS['srbminer']['device']


def test_bitcoin_sha256d_not_advertised_as_srbminer_gpu_algorithm():
    from mining.controller import MINERS
    assert 'SHA-256d' not in MINERS['srbminer']['algorithms']


def test_unmineable_payout_coin_distinguished_from_mined_asset():
    pools=json.loads((ROOT/'mining'/'pools.json').read_text())['pools']
    p=next(x for x in pools if x['id']=='unmineable-randomx-btc')
    assert p['coin']=='BTC' and p['payout_asset']=='BTC' and p['mined_asset']=='XMR'


def test_nerdminer_config_endpoint_returns_external_device_settings():
    from fastapi.testclient import TestClient
    from nexus_master import app
    with TestClient(app) as client:
        response=client.post('/api/mining/config',json={
            'pool_id':'public-pool-btc-solo','wallet':'bc1qexamplewalletaddressnotreal0000000000000000000000000000000000',
            'worker':'nm-test','password':'x','mining_mode':'SOLO_POOL','miner_id':'nerdminer','device':'ESP32'
        })
    assert response.status_code==200
    data=response.json()
    assert data['execution']=='not_started'
    assert data['external_device_config']['stratum_host']=='public-pool.io'
    assert data['external_device_config']['stratum_port']==3333
    assert data['external_device_config']['solo'] is True


def test_randomx_gpu_compatibility_is_rejected():
    from fastapi.testclient import TestClient
    from nexus_master import app
    with TestClient(app) as client:
        response=client.post('/api/mining/compatibility',json={'pool_id':'unmineable-randomx-xmr','miner_id':'srbminer','device':'GPU'})
    assert response.status_code==200
    assert response.json()['compatible'] is False
    assert any('RandomX' in reason for reason in response.json()['reasons'])
