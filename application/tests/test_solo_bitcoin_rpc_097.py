import pytest
from mining.solo_bitcoin_rpc import BitcoinRPC, SoloRPCError, benchmark_sha256d, mine_regtest_block, _compact_target

class MockRPC:
    def __init__(self, chain='regtest', bits='207fffff', txs=None, submit=None):
        self.chain=chain; self.bits=bits; self.txs=txs or []; self.submitted=None; self.submit=submit
    def call(self, method, params=None):
        if method=='getblockchaininfo': return {'chain':self.chain}
        if method=='getblocktemplate': return {'height':101,'coinbasevalue':5000000000,'transactions':self.txs,'version':4,'previousblockhash':'00'*32,'curtime':1700000000,'bits':self.bits}
        if method=='submitblock': self.submitted=params[0]; return self.submit
        raise AssertionError(method)

def test_sha256d_benchmark_runs_and_reports_scope():
    r=benchmark_sha256d(1000)
    assert r['iterations']==1000 and r['hashrate_hs']>0 and len(r['last_digest'])==64
    assert 'not GPU' in r['scope']

def test_regtest_miner_finds_and_submits_block():
    rpc=MockRPC()
    r=mine_regtest_block(rpc,'51',10000)
    assert r['block_found'] is True and r['submitted'] is True
    assert r['network']=='regtest' and rpc.submitted and len(rpc.submitted)>160

def test_miner_refuses_mainnet_and_nonempty_mempool():
    with pytest.raises(SoloRPCError,match='regtest'):
        mine_regtest_block(MockRPC(chain='main'), '51', 10)
    with pytest.raises(SoloRPCError,match='mempool gol'):
        mine_regtest_block(MockRPC(txs=[{'data':'00'}]), '51', 10)

def test_rpc_requires_loopback_and_auth():
    with pytest.raises(SoloRPCError,match='loopback'):
        BitcoinRPC('http://192.0.2.1:8332','u','p')
    with pytest.raises(SoloRPCError,match='cookie'):
        BitcoinRPC()

def test_compact_target_regtest_is_high():
    assert _compact_target('207fffff') > 2**254
