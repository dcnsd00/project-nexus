import json
from pathlib import Path
from mining.pool_config import pool_endpoint, pool_username

ROOT = Path(__file__).resolve().parents[1]


def test_curated_catalog_has_unique_complete_entries_and_known_solo_endpoints():
    data=json.loads((ROOT/'mining'/'pools.json').read_text(encoding='utf-8'))
    pools=data['pools']; ids=[p['id'] for p in pools]
    assert len(pools) >= 69
    assert len(ids)==len(set(ids))
    for p in pools:
        assert p.get('source')
        if p['id']!='custom':
            assert p.get('coin') and p.get('algorithm') and p.get('host') and p.get('port')
    solo=[p for p in pools if 'SOLO' in p.get('mode','').upper()]
    expected={'public-pool-btc-solo','nerdminer-public-pool-lowdiff','2miners-rvn-solo-eu',
               'braiins-btc-solo','ckpool-btc-solo','kryptex-prl-solo-global'}
    assert expected <= {p['id'] for p in solo}
    assert all(p.get('worker_format') for p in solo)


def test_tls_endpoint_uses_tls_host_if_operator_publishes_separate_hostname():
    pool={'host':'plain.example','port':1234,'ssl_host':'tls.example','ssl_port':443}
    assert pool_endpoint(pool,False)==('plain.example',1234)
    assert pool_endpoint(pool,True)==('tls.example',443)


def test_operator_specific_login_formats():
    assert pool_username({'worker_format':'ACCOUNT.worker'},'subacct','rig1')=='subacct.rig1'
    assert pool_username({'worker_format':'BTC_ADDRESS'},'bc1address','rig1')=='bc1address'
    assert pool_username({'worker_format':'BTC_ADDRESS[.worker]'},'bc1address','rig1')=='bc1address.rig1'
    assert pool_username({'worker_format':'KRYPTEX_SOLO_PREFIX','solo_username_prefix':'solo:'},'VTCaddress','rig1')=='solo:VTCaddress'
    assert pool_username({'worker_format':'WALLET.worker'},'VTCaddress','rig1')=='VTCaddress.rig1'


def test_coin_catalog_distinguishes_non_pow_and_bitcoin_hardware_class():
    data=json.loads((ROOT/'mining'/'coins.json').read_text(encoding='utf-8'))
    items={x['symbol']:x for x in data['coins']}
    assert items['BTC']['pow_mineable'] is True
    assert 'ASIC' in items['BTC']['device_classes']
    assert items['XMR']['algorithm']=='RandomX' and items['XMR']['device_classes']==['CPU']
    assert items['ETH']['pow_mineable'] is False
    assert items['SOL']['pow_mineable'] is False
    assert {'ETHW','PRL','KDA','SC'} <= set(items)
