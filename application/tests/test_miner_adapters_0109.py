import pytest
from mining import controller as mc

class FakeProc:
    def __init__(self, args, **kwargs):
        self.args=args; self.kwargs=kwargs; self.pid=98765; self.returncode=None
    def poll(self): return self.returncode
    def terminate(self): self.returncode=0
    def wait(self, timeout=None): return self.returncode
    def kill(self): self.returncode=-9

@pytest.mark.parametrize('mid,exe,algo,expected', [
    ('lolminer','lolMiner.exe','KawPoW','--algo KAWPOW'),
    ('gminer','miner.exe','KawPoW','--algo kawpow'),
    ('rigel','rigel.exe','KawPoW','--algorithm kawpow'),
    ('teamredminer','teamredminer.exe','KawPoW','-a kawpow'),
])
def test_new_miner_adapters_build_commands_without_launching_real_binaries(monkeypatch, tmp_path, mid, exe, algo, expected):
    pool={'id':'custom','name':'Test Pool','coin':'RVN','algorithm':algo,'miner':mid,
          'host':'pool.example.test','port':3333,'selectable':True,'payout_status':'active'}
    monkeypatch.setattr(mc,'_pool_catalog',lambda:[pool])
    monkeypatch.setattr(mc,'_resolve_binary',lambda miner_id, explicit_path=None:f'C:/fake/{exe}')
    monkeypatch.setattr(mc.subprocess,'Popen',FakeProc)
    monkeypatch.setattr(mc,'_metrics',lambda:{'api_connected':False,'hashrate_hs':None,'hashrate_display':None,
       'accepted_shares':None,'rejected_shares':None,'gpu':{},'system':{},'raw_api':None})
    monkeypatch.setattr(mc,'LOG',tmp_path/'miner.log')
    result=mc.start({'miner_id':mid,'pool_id':'custom','custom_host':'pool.example.test','custom_port':3333,
       'wallet':'wallet_example_123','worker':'nexus_test','algorithm':algo,'device':'GPU','use_ssl':False})
    assert result['status']=='running'
    assert expected in ' '.join(mc._proc.args)
    assert 'pool.example.test' in ' '.join(mc._proc.args)
    mc.stop()


def test_teamredminer_refuses_cpu(monkeypatch):
    pool={'id':'custom','name':'Test Pool','coin':'RVN','algorithm':'KawPoW','miner':'teamredminer',
          'host':'pool.example.test','port':3333,'selectable':True,'payout_status':'active'}
    monkeypatch.setattr(mc,'_pool_catalog',lambda:[pool])
    with pytest.raises(ValueError,match='nu suportă dispozitivul'):
        mc.start({'miner_id':'teamredminer','pool_id':'custom','custom_host':'pool.example.test',
                  'custom_port':3333,'wallet':'wallet_example_123','worker':'nexus_test',
                  'algorithm':'KawPoW','device':'CPU','use_ssl':False})
