import json
from pathlib import Path
from fastapi.testclient import TestClient
import nexus_master

client=TestClient(nexus_master.app)
ROOT=Path(__file__).resolve().parents[1]

def test_major_coin_catalog_contains_pow_and_non_pow_classification():
    d=client.get('/api/mining/coins').json()
    c={x['symbol']:x for x in d['coins']}
    for sym in ('BTC','BCH','LTC','DOGE','XMR','RVN','ETC','KAS','VTC','ZEC','DASH','ALPH','NEXA','ETHW','KDA','SC','ALEO','PRL'):
        assert sym in c
    assert c['BTC']['pow_mineable'] is True and 'ASIC' in c['BTC']['device_classes']
    assert c['XMR']['algorithm']=='RandomX' and c['XMR']['device_classes']==['CPU']
    assert c['ETH']['pow_mineable'] is False
    assert c['SOL']['pow_mineable'] is False

def test_major_pool_catalog_structural_audit_is_clean():
    d=client.get('/api/mining/catalog-audit').json()
    assert d['pool_count'] >= 69
    assert d['duplicate_ids']==[]
    assert d['missing_required_fields']==[]
    assert d['solo_missing_worker_format']==[]
    assert d['live_reachability_checked'] is False

def test_all_documented_solo_profiles_generate_without_starting_mining():
    profiles=client.get('/api/mining/solo-profiles').json()['solo_pools']
    assert len(profiles) >= 7
    for p in profiles:
        identity='acct' if p['id']=='viabtc-btc-global' else ('PRL'+'a'*32 if p['coin']=='PRL' else ('R'+'a'*33 if p['coin']=='RVN' else ('bc1q'+'a'*30)))
        response=client.post('/api/mining/solo/config',json={
            'mode':'SOLO_POOL','pool_id':p['id'],'wallet':identity,'worker':'nexus-test'
        })
        assert response.status_code==200, (p['id'],response.text)
        result=response.json()
        assert result['mode']=='SOLO_POOL'
        assert result['mining_started'] is False
        assert result['host']==p['host'] and result['port']==p['port']
        assert result['username']

def test_catalog_pool_ignores_stale_custom_endpoint_values():
    r=client.post('/api/mining/config',json={
        'pool_id':'f2pool-btc-eu','wallet':'myaccount','worker':'rig1','miner_id':'asic',
        'device':'ASIC','custom_host':'attacker.invalid','custom_port':1,'custom_algorithm':'wrong'
    })
    assert r.status_code==200
    d=r.json()
    assert d['host']=='btc-euro.f2pool.com' and d['port']==1314
    assert d['wallet_worker']=='myaccount.rig1'
    assert d['algorithm']=='SHA-256d'

def test_solo_rejects_standard_pplns_pool_and_accepts_dedicated_2miners_rvn():
    bad=client.post('/api/mining/solo/config',json={'mode':'SOLO_POOL','pool_id':'2miners-rvn-eu','wallet':'R'+'a'*33})
    assert bad.status_code==400
    good=client.post('/api/mining/solo/config',json={'mode':'SOLO_POOL','pool_id':'2miners-rvn-solo-eu','wallet':'R'+'a'*33})
    assert good.status_code==200
    assert good.json()['host']=='solo-rvn.2miners.com' and good.json()['port']==7070

def test_local_regtest_rejects_non_loopback_rpc_and_mainnet_mode():
    bad=client.post('/api/mining/solo/config',json={'mode':'LOCAL_REGTEST','rpc_url':'http://192.168.1.10:18443','payout_script_hex':'51'})
    assert bad.status_code==400
    bad2=client.post('/api/mining/solo/config',json={'mode':'LOCAL_REGTEST','network':'main','payout_script_hex':'51'})
    assert bad2.status_code==400
    good=client.post('/api/mining/solo/config',json={'mode':'LOCAL_REGTEST','network':'regtest','payout_script_hex':'51'})
    assert good.status_code==200 and good.json()['mainnet_writes'] is False

def test_self_hosted_node_profile_warns_about_mainnet_submission_and_is_config_only():
    r=client.post('/api/mining/solo/config',json={
        'mode':'LOCAL_NODE_STRATUM_PROXY','network':'main','rpc_url':'http://127.0.0.1:8332','stratum_port':3333
    })
    assert r.status_code==200
    d=r.json()
    assert d['generated_config_only'] is True
    assert d['proxy_started'] is False
    assert d['potential_public_chain_submission'] is True

def test_solo_profiles_expose_full_operator_settings_not_just_host_and_port():
    r=client.post('/api/mining/solo/config',json={
        'mode':'SOLO_POOL','pool_id':'public-pool-btc-solo','wallet':'bc1q'+'b'*30,'worker':'esp32-1'
    })
    assert r.status_code==200
    d=r.json()
    for key in ('primary_endpoint','tls_available','worker_format','auth_type','identity_label',
                'backup_ports','share_difficulty_default','fee_note','payout_rule','device_class','source'):
        assert key in d
    assert d['primary_endpoint']['host']=='public-pool.io'
    assert d['primary_endpoint']['port']==3333
    assert d['tls_available'] is True


def test_viabtc_solo_requires_account_mode_toggle_note():
    r=client.post('/api/mining/solo/config',json={
        'mode':'SOLO_POOL','pool_id':'viabtc-btc-global','wallet':'myaccount','worker':'rig1'
    })
    assert r.status_code==200
    d=r.json()
    assert d['solo_requires_account_mode'] is True
    assert 'dashboard' in d['activation_note']
    assert d['username']=='myaccount.rig1'

def test_viabtc_major_coin_endpoint_matrix_uses_correct_main_and_tls_ports():
    data=client.get('/api/mining/pools').json()['pools']
    rows={p['id']:p for p in data}
    assert rows['viabtc-btc-global']['ssl_host']=='btc-ssl.viabtc.io'
    assert rows['viabtc-btc-global']['ssl_port']==551
    assert rows['viabtc-kas-global']['port']==315
    assert rows['viabtc-kas-global']['backup_ports']==[3015]
    assert rows['viabtc-kas-global']['ssl_host']=='kas-ssl.powhashing.com'
    assert rows['viabtc-kas-global']['ssl_port']==3015
    assert rows['viabtc-bch-global']['port']==3333 and rows['viabtc-bch-global']['ssl_port']==551
    assert rows['viabtc-ltc-global']['port']==3333 and rows['viabtc-ltc-global']['ssl_port']==551
    assert rows['viabtc-zec-global']['port']==3002 and rows['viabtc-zec-global']['ssl_port']==3002
    assert rows['viabtc-dash-global']['port']==3004 and rows['viabtc-dash-global']['backup_ports']==[304]

def test_f2pool_pearl_pool_is_catalogued_with_operator_source():
    data=client.get('/api/mining/pools').json()['pools']
    p=next(x for x in data if x['id']=='f2pool-prl-global')
    assert p['host']=='pearl.f2pool.com' and p['port']==5500
    assert p['algorithm']=='PearlHash' and p['auth_type']=='account_worker'
    assert p['source'].startswith('https://f2pool.zendesk.com/')


def test_luxor_and_poolin_bitcoin_profiles_have_documented_login_and_failover():
    data=client.get('/api/mining/pools').json()['pools']
    rows={p['id']:p for p in data}
    luxor=rows['luxor-btc-global']
    assert luxor['host']=='btc.global.luxor.tech' and luxor['port']==700
    assert luxor['worker_format']=='ACCOUNT.worker' and luxor['auth_type']=='account_worker'
    assert luxor['device_class']==['ASIC']
    poolin=rows['poolin-btc-global']
    assert poolin['host']=='btc.ss.poolin.me' and poolin['port']==443
    assert poolin['backup_ports']==[1883,700]
    assert poolin['ssl_port'] is None  # port 443 alone is not proof of TLS
    assert poolin['worker_format']=='ACCOUNT.worker'


def test_f2pool_primary_and_etc_tls_hosts_match_current_operator_docs():
    data=client.get('/api/mining/pools').json()['pools']
    rows={p['id']:p for p in data}
    btc=rows['f2pool-btc-global']
    assert btc['port']==1314 and btc['backup_ports']==[25,3333]
    assert btc['ssl_host']=='btcssl.f2pool.com' and btc['ssl_port']==1300
    etc=rows['f2pool-etc-global']
    assert etc['ssl_host']=='etcssl.f2pool.com' and etc['ssl_port']==8180
