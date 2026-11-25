import importlib
from fastapi.testclient import TestClient
import nexus_master
import modules.earnings_intelligence as intel


def client_for(tmp_path, monkeypatch):
    monkeypatch.setattr(intel, "DB_PATH", tmp_path / "intel.db")
    intel.init_db()
    return TestClient(nexus_master.app)


def test_opportunity_device_evaluation_and_shadow_only(tmp_path, monkeypatch):
    c=client_for(tmp_path,monkeypatch)
    op=c.post('/api/intel/opportunities',json={
      'name':'Test PoW','category':'pow','asset':'TST','algorithm':'SHA-256d',
      'device_classes':['ASIC'],'estimated_tokens_day':2,'price_ron':10,'confidence':0.8,
      'daily_fee_ron':1,'transferable':True,'eligibility_verified':True,'payout_verified':True,
      'liquidity_usd':10000,'min_payout':0.1,'payout_days':2,'status':'verified'}).json()['id']
    dev=c.post('/api/intel/devices',json={
      'name':'ASIC test','device_type':'ASIC','watts_load':100,'tariff_ron_kwh':1,
      'capabilities':['SHA-256d']}).json()['id']
    ev=c.get(f'/api/intel/evaluate/{op}/{dev}').json()
    assert ev['decision']=='positive_estimate'
    assert ev['gross_ron_day']==20
    assert ev['energy_ron_day']==2.4
    assert ev['net_ron_day']==16.6
    plan=c.post('/api/intel/scheduler/shadow').json()
    assert plan['mode']=='shadow_only' and plan['live_execution'] is False
    assert plan['plans'][0]['execution']=='not_started'


def test_unknown_economics_never_positive(tmp_path, monkeypatch):
    c=client_for(tmp_path,monkeypatch)
    op=c.post('/api/intel/opportunities',json={'name':'Unknown','category':'depin'}).json()['id']
    dev=c.post('/api/intel/devices',json={'name':'Phone','device_type':'ANDROID'}).json()['id']
    ev=c.get(f'/api/intel/evaluate/{op}/{dev}').json()
    assert ev['decision']=='insufficient_evidence'
    assert 'price_ron' in ev['missing']


def test_rewards_deduplicate_tx_hash_and_payouts(tmp_path, monkeypatch):
    c=client_for(tmp_path,monkeypatch)
    payload={'asset':'BTC','amount':0.0001,'state':'realized','tx_hash':'abc123456789'}
    assert c.post('/api/intel/rewards',json=payload).status_code==200
    assert c.post('/api/intel/rewards',json=payload).status_code==409
    p={'asset':'BTC','amount':0.0001,'tx_hash':'txhash123456789','verification':'explorer_confirmed'}
    assert c.post('/api/intel/payouts',json=p).status_code==200
    assert c.post('/api/intel/payouts',json=p).status_code==409


def test_wallet_watch_is_read_only_and_status(tmp_path, monkeypatch):
    c=client_for(tmp_path,monkeypatch)
    r=c.post('/api/intel/wallet-watch',json={'chain':'Bitcoin','address':'bc1qexampleaddress123456789','label':'watch'}).json()
    assert r['signing'] is False
    status=c.get('/api/intel/status').json()
    assert status['provider_connectors_live']==0
    assert status['private_keys_accepted'] is False


def test_opportunity_values_are_parameterized_and_do_not_change_schema(tmp_path, monkeypatch):
    c = client_for(tmp_path, monkeypatch)
    hostile_text = "x'); DROP TABLE devices;--"
    created = c.post(
        "/api/intel/opportunities",
        json={"name": hostile_text, "category": "pow"},
    )
    assert created.status_code == 200
    rows = c.get("/api/intel/opportunities").json()
    assert any(row["name"] == hostile_text for row in rows)
    assert c.get("/api/intel/devices").status_code == 200
