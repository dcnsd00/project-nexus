from fastapi.testclient import TestClient
from nexus_master import app

def test_dashboard_route():
    with TestClient(app) as c:
        r=c.get('/api/nexus/dashboard')
        assert r.status_code == 200 and 'NEXUS Control Center' in r.text

def test_pool_catalog_and_config():
    with TestClient(app) as c:
        p=c.get('/api/mining/pools')
        assert p.status_code == 200
        assert len(p.json()['pools']) >= 10
        cfg=c.post('/api/mining/config',json={'pool_id':'2miners-rvn-eu','wallet':'RTestWalletAddress123','worker':'test rig'})
        assert cfg.status_code == 200
        assert cfg.json()['url']=='stratum+tcp://rvn.2miners.com:6060'
        assert cfg.json()['execution']=='not_started'

def test_pool_custom_requires_host():
    with TestClient(app) as c:
        r=c.post('/api/mining/config',json={'pool_id':'custom','wallet':'wallet123'})
        assert r.status_code == 400

def test_crypto_catalog_cache(monkeypatch, tmp_path):
    import modules.coin_catalog as cc
    monkeypatch.setattr(cc,'CACHE',tmp_path/'coins.json')
    class FakeResponse:
        status=200
        def __enter__(self): return self
        def __exit__(self,*args): pass
        def read(self): return b'[{"id":"btc-bitcoin","name":"Bitcoin","symbol":"BTC","rank":1,"type":"coin","is_active":true}]'
    monkeypatch.setattr(cc.urllib.request,'urlopen',lambda *a,**k:FakeResponse())
    data=cc.get_coins(force=True)
    assert data['coins'][0]['symbol']=='BTC' and not data['cached']
    assert cc.get_coins()['cached']

def test_coin_catalog_serves_stale_cache_when_upstream_is_unavailable(monkeypatch, tmp_path):
    import json, urllib.error
    import modules.coin_catalog as cc
    monkeypatch.setattr(cc, 'CACHE', tmp_path / 'coins.json')
    cc.CACHE.write_text(json.dumps({
        'schema_version': 2, 'source': 'CoinPaprika API', 'fetched_at': 1,
        'coins': [{'id': 'btc-bitcoin', 'name': 'Bitcoin', 'symbol': 'BTC', 'rank': 1,
                  'type': 'coin', 'is_active': True, 'is_new': False}]
    }), encoding='utf-8')
    def offline(*args, **kwargs):
        raise urllib.error.URLError('offline test')
    monkeypatch.setattr(cc.urllib.request, 'urlopen', offline)
    data = cc.get_coins(force=True)
    assert data['cached'] is True and data['stale'] is True and data['fallback'] is True
    assert data['coins'][0]['symbol'] == 'BTC'
    assert 'offline test' in data['upstream_error']


def test_coin_catalog_uses_bundled_mining_catalog_without_cache(monkeypatch, tmp_path):
    import urllib.error
    import modules.coin_catalog as cc
    monkeypatch.setattr(cc, 'CACHE', tmp_path / 'missing.json')
    def offline(*args, **kwargs):
        raise urllib.error.URLError('no internet')
    monkeypatch.setattr(cc.urllib.request, 'urlopen', offline)
    data = cc.get_coins(force=True)
    assert data['fallback'] is True and data['stale'] is True
    assert data['source'] == 'NEXUS bundled mining catalogue'
    assert any(x['symbol'] == 'BTC' for x in data['coins'])
    assert all(x['catalog_source'] == 'NEXUS bundled mining catalogue' for x in data['coins'])


def test_coin_catalog_does_not_overwrite_valid_cache_on_failed_refresh(monkeypatch, tmp_path):
    import json, urllib.error
    import modules.coin_catalog as cc
    monkeypatch.setattr(cc, 'CACHE', tmp_path / 'coins.json')
    original = {'schema_version': 2, 'source': 'CoinPaprika API', 'fetched_at': 2,
                'coins': [{'id': 'eth-ethereum', 'name': 'Ethereum', 'symbol': 'ETH', 'rank': 2,
                          'type': 'coin', 'is_active': True, 'is_new': False}]}
    cc.CACHE.write_text(json.dumps(original), encoding='utf-8')
    before = cc.CACHE.read_bytes()
    monkeypatch.setattr(cc.urllib.request, 'urlopen', lambda *a, **k: (_ for _ in ()).throw(urllib.error.URLError('offline')))
    data = cc.get_coins(force=True)
    assert data['coins'][0]['symbol'] == 'ETH'
    assert cc.CACHE.read_bytes() == before

def test_coin_catalog_api_returns_explicit_fallback_when_offline(monkeypatch, tmp_path):
    import urllib.error
    import modules.coin_catalog as cc
    from fastapi.testclient import TestClient
    import nexus_master
    monkeypatch.setattr(cc, 'CACHE', tmp_path / 'no-cache.json')
    monkeypatch.setattr(cc.urllib.request, 'urlopen', lambda *a, **k: (_ for _ in ()).throw(urllib.error.URLError('offline api test')))
    with TestClient(nexus_master.app) as client:
        response = client.get('/api/coins/catalog?refresh=true&limit=10')
    assert response.status_code == 200
    body = response.json()
    assert body['fallback'] is True and body['stale'] is True
    assert body['source'] == 'NEXUS bundled mining catalogue'
    assert body['total_returned'] > 0


def test_native_engine_status_api_is_read_only():
    from fastapi.testclient import TestClient
    import nexus_master
    with TestClient(nexus_master.app) as client:
        response = client.get('/api/mining/native-engine')
    assert response.status_code == 200
    body = response.json()
    assert 'available' in body and 'variants' in body
