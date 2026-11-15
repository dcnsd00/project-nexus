import json
from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]


def test_coin_and_pool_catalogs_have_unique_ids_and_required_fields():
    coins = json.loads((ROOT / 'mining' / 'coins.json').read_text(encoding='utf-8'))['coins']
    pools = json.loads((ROOT / 'mining' / 'pools.json').read_text(encoding='utf-8'))['pools']
    assert len({c['symbol'] for c in coins}) == len(coins)
    assert len({p['id'] for p in pools}) == len(pools)
    for p in pools:
        if p.get('id') != 'custom':
            assert p.get('host')
            assert isinstance(p.get('port'), int) and 1 <= p['port'] <= 65535


def test_main_pow_assets_and_cosmos_pos_registry_are_separate():
    from fastapi.testclient import TestClient
    from nexus_master import app
    with TestClient(app) as c:
        pow_assets = c.get('/api/mining/coins')
        staking = c.get('/api/staking/assets')
    assert pow_assets.status_code == 200
    assert staking.status_code == 200
    coins = {x['symbol']: x for x in pow_assets.json()['coins']}
    assert coins['BTC']['algorithm'] == 'SHA-256d'
    assert coins['ETC']['algorithm'] == 'Etchash'
    assert coins['XMR']['algorithm'] == 'RandomX'
    assert coins['PRL']['algorithm'] in ('PearlHash', 'PearlPow')
    assert coins['ATOM']['pow_mineable'] is False
    pos = {x['symbol']: x for x in staking.json()['assets']}
    assert pos['ATOM']['consensus'] == 'Proof-of-Stake'
    assert pos['OSMO']['consensus'] == 'Proof-of-Stake'


def test_unmineable_atom_is_payout_asset_not_mined_asset_and_is_paused():
    pools = json.loads((ROOT / 'mining' / 'pools.json').read_text(encoding='utf-8'))['pools']
    atom_routes = [p for p in pools if p.get('payout_asset') == 'ATOM']
    assert len(atom_routes) == 2
    assert {(p['mined_asset'], p['algorithm']) for p in atom_routes} == {
        ('PRL', 'PearlPow'), ('XEL', 'XelisHash')
    }
    assert all(p['payout_status'] == 'paused' and p['selectable'] is False for p in atom_routes)


def test_atom_paused_route_cannot_generate_or_start_config():
    with TestClient(__import__('nexus_master').app) as c:
        r = c.post('/api/mining/config', json={
            'pool_id': 'unmineable-pearlpow-atom',
            'wallet': 'cosmos1examplewalletaddressnotreal',
            'worker': 'nexus-test',
            'miner_id': 'bzminer',
            'device': 'GPU',
        })
    assert r.status_code == 409
    assert 'suspendat' in r.json()['detail'].lower()


def test_catalog_only_coin_is_listed_but_not_startable():
    with TestClient(__import__('nexus_master').app) as c:
        r = c.post('/api/mining/config', json={
            'pool_id': 'unmineable-xelishash-atom',
            'wallet': 'cosmos1examplewalletaddressnotreal',
            'worker': 'nexus-test',
            'miner_id': 'bzminer',
            'device': 'GPU',
        })
    assert r.status_code == 409


def test_unmineable_public_catalog_metadata_is_read_only_and_shape_tolerant(monkeypatch):
    from modules import unmineable_catalog
    sample = {'coins': [{'symbol': 'ATOM', 'name': 'Cosmos', 'enabled': False},
                        {'symbol': 'BTC', 'name': 'Bitcoin', 'enabled': True}]}
    monkeypatch.setattr(unmineable_catalog, '_request_json', lambda path, timeout: sample)
    data = unmineable_catalog.public_asset_catalog(timeout=3)
    assert data['provider'] == 'unMineable'
    assert data['read_only'] is True and data['auth_required'] is False
    assert data['count'] == 2
    assert {x['symbol'] for x in data['assets']} == {'ATOM', 'BTC'}


def test_unmineable_public_api_route_has_no_credentials_required(monkeypatch):
    from modules import unmineable_catalog
    monkeypatch.setattr(unmineable_catalog, 'public_asset_catalog', lambda timeout=8.0: {
        'provider': 'unMineable', 'status': 'live_public_metadata', 'read_only': True,
        'auth_required': False, 'count': 1, 'assets': [{'symbol': 'BTC'}]
    })
    with TestClient(__import__('nexus_master').app) as c:
        r = c.get('/api/mining/unmineable/assets?refresh=true')
    assert r.status_code == 200
    assert r.json()['assets'][0]['symbol'] == 'BTC'
    assert r.json()['auth_required'] is False


def test_bzminer_is_an_official_release_installer_but_not_auto_executed():
    from mining import installer
    row = next(x for x in installer.list_sources() if x['id'] == 'bzminer')
    assert row['automatic_download'] is True
    assert row['official_url'] == 'https://github.com/bzminer/bzminer/releases'
    assert row['installed'] is False or isinstance(row['managed_path'], str)


def test_bzminer_upstream_windows_asset_selector_is_exact(monkeypatch):
    from mining import installer
    payload = {
        'tag_name': 'v100.52', 'html_url': 'https://github.com/bzminer/bzminer/releases/tag/v100.52',
        'assets': [
            {'name': 'bzminer_v100.52_windows.zip', 'browser_download_url': 'https://github.com/bzminer/bzminer/releases/download/v100.52/bzminer_v100.52_windows.zip', 'size': 100, 'digest': 'sha256:' + 'a' * 64},
            {'name': 'bzminer_v100.52_linux.tar.gz', 'browser_download_url': 'https://example.invalid/linux.tar.gz', 'size': 100},
        ]
    }
    monkeypatch.setattr(installer, '_request', lambda url: json.dumps(payload).encode())
    release = installer.latest_release('bzminer')
    assert release['version'] == 'v100.52'
    assert release['asset_name'] == 'bzminer_v100.52_windows.zip'
    assert release['source_repo'] == 'bzminer/bzminer'


def test_bzminer_profile_is_limited_to_gpu_algorithms_with_known_mapping():
    from mining.controller import MINERS
    bz = MINERS['bzminer']
    assert bz['launch'] is True
    assert bz['device'] == ['GPU']
    assert {'PearlHash', 'PearlPow', 'KawPoW', 'Etchash'} <= set(bz['algorithms'])
    assert 'RandomX' not in bz['algorithms']


def test_version_endpoint_is_updated_to_0108():
    with TestClient(__import__('nexus_master').app) as c:
        r = c.get('/api/nexus/master')
    assert r.status_code == 200
    assert r.json()['version'] == '0.10.25'
