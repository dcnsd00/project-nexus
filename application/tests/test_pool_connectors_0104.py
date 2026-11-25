import json
from modules import pool_connectors as pc


def test_unmineable_signature_is_deterministic_and_hmac_sha256():
    sig=pc.unmineable_signature('GET','/v1/assets/BTC/stats','', '1760000000000', b'', 'secret')
    assert len(sig)==64
    assert sig==pc.unmineable_signature('GET','/v1/assets/BTC/stats','', '1760000000000', b'', 'secret')
    assert sig!=pc.unmineable_signature('GET','/v1/assets/BTC/stats','', '1760000000001', b'', 'secret')


def test_kryptex_account_connector_only_uses_get_and_returns_source(monkeypatch):
    calls=[]
    def fake(url,headers=None,timeout=8):
        calls.append(url)
        return {'url':url,'balance':'0.01'}
    monkeypatch.setattr(pc,'_safe_get_json',fake)
    r=pc.kryptex_account_stats('BTC','bc1qwallet')
    assert r['read_only'] is True and r['status']=='live_api_response'
    assert len(calls)==4
    assert all('/api/v1/miner/' in x or '/api/v3/miner/' in x for x in calls)


def test_braiins_connector_filters_other_users_workers(monkeypatch):
    def fake(url,headers=None,timeout=8):
        if '/profile/' in url: return {'username':'myacct','btc':{'current_balance':'0.001','today_reward':'0.0001'}}
        return {'btc':{'workers':{'myacct.rig1':{'hash_rate_5m':10},'other.rig2':{'hash_rate_5m':999}}}}
    monkeypatch.setattr(pc,'_safe_get_json',fake)
    r=pc.braiins_account_stats('myacct','token-that-is-long-enough')
    assert r['read_only'] is True
    assert set(r['data']['workers'])=={'myacct.rig1'}
    assert r['data']['profile']['btc']['current_balance']=='0.001'


def test_connector_catalog_marks_f2pool_pending_not_fake_live():
    c={x['provider']:x for x in pc.connector_catalog()}
    assert c['Kryptex Pool']['available'] is True
    assert c['Braiins Pool']['available'] is True
    assert c['F2Pool']['available'] is False


def test_rewards_check_redacts_provider_exception_details(monkeypatch):
    from fastapi.testclient import TestClient
    import nexus_master

    sensitive = "API_SECRET=private-token /private/provider/path"
    def fail_provider(wallet, api_key):
        raise RuntimeError(sensitive)

    monkeypatch.setattr(nexus_master, "braiins_account_stats", fail_provider)
    with TestClient(nexus_master.app) as client:
        response = client.post("/api/mining/rewards-check", json={
            "provider": "Braiins",
            "wallet": "nexus-test-user",
            "api_key": "test-read-only-token",
        })
    assert response.status_code == 502
    assert sensitive not in response.text
    assert response.json()["detail"] == "Braiins API unavailable: Braiins metadata unavailable"
