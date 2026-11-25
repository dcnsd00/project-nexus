import json
from pathlib import Path
import pytest
from mining.solo_profiles import build_solo_pool_profile, build_local_node_profile, SoloProfileError

ROOT=Path(__file__).resolve().parents[1]
POOLS=json.loads((ROOT/'mining'/'pools.json').read_text(encoding='utf-8'))['pools']


def get(pid): return next(p for p in POOLS if p['id']==pid)


def test_publicpool_bitcoin_solo_profile_has_explicit_login_and_no_launch():
    p=build_solo_pool_profile(get('public-pool-btc-solo'),'bc1qexampleaddress','nexus1','x',False)
    assert p['mode']=='SOLO_POOL'
    assert p['host']=='public-pool.io' and p['port']==3333
    assert p['username']=='bc1qexampleaddress.nexus1'
    assert p['mining_started'] is False
    assert 'accepted shares do not equal' in p['share_note'].lower()


def test_ckpool_uses_official_plain_bitcoin_address_username():
    p=build_solo_pool_profile(get('ckpool-btc-solo'),'bc1qexampleaddress','nexus1')
    assert p['host']=='stratum.ckpool.org'
    assert p['username']=='bc1qexampleaddress.nexus1'
    assert p['backup_ports']==[4334]


def test_kryptex_pearl_solo_uses_solo_prefix():
    p=build_solo_pool_profile(get('kryptex-prl-solo-global'),'VTC_OR_PRL_WALLET','worker1')
    assert p['username']=='solo:VTC_OR_PRL_WALLET'


def test_pplns_pool_is_not_silently_promoted_to_solo():
    with pytest.raises(SoloProfileError):
        build_solo_pool_profile(get('veinpool-vtc-eu'),'VTCwallet')


def test_local_regtest_is_loopback_only_and_explicitly_regtest():
    p=build_local_node_profile('LOCAL_REGTEST',network='regtest',payout_script_hex='51')
    assert p['network']=='regtest' and p['mainnet_writes'] is False
    with pytest.raises(SoloProfileError):
        build_local_node_profile('LOCAL_REGTEST',network='main',payout_script_hex='51')
    with pytest.raises(SoloProfileError):
        build_local_node_profile('LOCAL_REGTEST',rpc_url='http://192.168.1.10:18443',network='regtest',payout_script_hex='51')


def test_self_hosted_node_proxy_is_profile_only_not_claimed_running():
    p=build_local_node_profile('LOCAL_NODE_STRATUM_PROXY',network='main',stratum_port=3333)
    assert p['generated_config_only'] is True
    assert p['proxy_started'] is False
    assert p['potential_public_chain_submission'] is True
