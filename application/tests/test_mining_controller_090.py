from fastapi.testclient import TestClient
import pytest
from nexus_master import app


def test_miner_inventory_and_status_routes():
    with TestClient(app) as c:
        inv=c.get('/api/mining/miners')
        assert inv.status_code==200
        ids={x['id'] for x in inv.json()['miners']}
        assert {'xmrig','srbminer','lolminer','gminer','rigel','teamredminer'} <= ids
        st=c.get('/api/mining/status')
        assert st.status_code==200 and 'metrics' in st.json()
        dg=c.get('/api/mining/diagnostics')
        assert dg.status_code==200 and 'errors' in dg.json()


def test_start_rejects_unknown_or_uninstalled_miner():
    with TestClient(app) as c:
        r=c.post('/api/mining/start',json={'miner_id':'unknown','pool_id':'2miners-rvn-eu','wallet':'wallet123','worker':'test','device':'GPU'})
        assert r.status_code==400
        assert 'lansare' in r.json()['detail'].lower() or 'miner' in r.json()['detail'].lower()


def test_start_validates_pool_and_wallet_before_process():
    with TestClient(app) as c:
        r=c.post('/api/mining/start',json={'miner_id':'srbminer','pool_id':'custom','wallet':'wallet123','worker':'test','device':'GPU'})
        assert r.status_code==400
        assert 'host/port' in r.json()['detail'].lower()


def test_stop_is_idempotent():
    with TestClient(app) as c:
        r=c.post('/api/mining/stop')
        assert r.status_code==200
        assert r.json()['status']=='stopped'


def test_supervised_start_stop_with_fake_miner(monkeypatch):
    from mining import controller as mc
    class FakeProc:
        def __init__(self,*args,**kwargs):
            self.args=args[0]; self.kwargs=kwargs; self.returncode=None; self.pid=45678
        def poll(self): return self.returncode
        def terminate(self): self.returncode=0
        def wait(self,timeout=None): return self.returncode
        def kill(self): self.returncode=-9
    monkeypatch.setattr(mc,'_resolve_binary',lambda mid, explicit_path=None:'C:/fake/SRBMiner-MULTI.exe')
    monkeypatch.setattr(mc.subprocess,'Popen',FakeProc)
    monkeypatch.setattr(mc,'_metrics',lambda:{'api_connected':False,'hashrate_hs':None,'hashrate_display':None,'accepted_shares':None,'rejected_shares':None,'gpu':{},'system':{},'raw_api':None})
    started=mc.start({'miner_id':'srbminer','pool_id':'2miners-rvn-eu','wallet':'RWalletExample123','worker':'testRig','algorithm':'KawPoW','device':'GPU','use_ssl':False,'custom_host':None,'custom_port':None,'binary_path':None})
    assert started['pid']==45678 and started['status']=='running'
    assert 'rvn.2miners.com' in ' '.join(mc._proc.args)
    stopped=mc.stop()
    assert stopped['status']=='stopped'


def test_error_diagnostics_classify_common_mining_failures():
    from mining import controller as mc
    assert mc._diagnose('connection timed out')['code']=='POOL_CONNECTION'
    assert mc._diagnose('unsupported algorithm')['code']=='ALGORITHM_UNSUPPORTED'
    assert mc._diagnose('CUDA driver error')['code']=='GPU_DRIVER'
    assert mc._diagnose('out of memory allocating DAG')['code']=='GPU_MEMORY'


def test_trex_launch_uses_official_style_args_and_local_api(monkeypatch):
    from mining import controller as mc
    class FakeProc:
        def __init__(self,*args,**kwargs): self.args=args[0]; self.returncode=None; self.pid=45679
        def poll(self): return self.returncode
        def terminate(self): self.returncode=0
        def wait(self,timeout=None): return self.returncode
        def kill(self): self.returncode=-9
    monkeypatch.setattr(mc,'_resolve_binary',lambda mid, explicit_path=None:'C:/fake/t-rex.exe')
    monkeypatch.setattr(mc.subprocess,'Popen',FakeProc)
    monkeypatch.setattr(mc,'_metrics',lambda:{'api_connected':False,'hashrate_hs':None,'hashrate_display':None,'accepted_shares':None,'rejected_shares':None,'gpu':{},'system':{},'raw_api':None})
    started=mc.start({'miner_id':'trex','pool_id':'woolypooly-rvn','wallet':'RWalletExample123','worker':'testRig','algorithm':'KawPoW','device':'GPU','use_ssl':False,'custom_host':None,'custom_port':None,'binary_path':None})
    args=' '.join(mc._proc.args)
    assert started['status']=='running' and '-a kawpow' in args and '--api-bind-http 127.0.0.1:4067' in args
    assert mc.stop()['status']=='stopped'

def test_strict_miner_pool_compatibility_and_xmrig_cpu_only(monkeypatch):
    from nexus_master import _compatibility
    from mining import controller as mc
    monkeypatch.setattr(mc,'_resolve_binary',lambda mid, explicit_path=None:f'C:/fake/{mid}.exe')
    monkeypatch.setattr('nexus_master._nvidia',lambda:{'available':True,'gpus':[{'name':'NVIDIA test','memory_mib':'8192'}]})
    pool=next(p for p in mc._pool_catalog() if p['id']=='2miners-rvn-eu')
    assert _compatibility(pool,'xmrig','GPU')['compatible'] is False
    assert any('KawPoW' in x for x in _compatibility(pool,'xmrig','GPU')['reasons'])
    assert _compatibility(pool,'srbminer','GPU')['compatible'] is True


def test_start_rejects_manual_algorithm_override(monkeypatch):
    from mining import controller as mc
    monkeypatch.setattr(mc,'_resolve_binary',lambda mid, explicit_path=None:'C:/fake/SRBMiner-MULTI.exe')
    with pytest.raises(ValueError,match='Algoritm incompatibil'):
        mc.start({'miner_id':'srbminer','pool_id':'2miners-rvn-eu','wallet':'RWalletExample123','worker':'testRig','algorithm':'RandomX','device':'GPU','use_ssl':False})


def test_compatibility_blocks_kawpow_when_vram_below_dag(monkeypatch):
    from nexus_master import _compatibility
    from mining import controller as mc
    monkeypatch.setattr(mc,'_resolve_binary',lambda mid, explicit_path=None:'C:/fake/SRBMiner-MULTI.exe')
    monkeypatch.setattr('nexus_master._nvidia',lambda:{'available':True,'gpus':[{'name':'NVIDIA 4GB','memory_mib':'4096'}]})
    pool=next(p for p in mc._pool_catalog() if p['id']=='2miners-rvn-eu')
    d=_compatibility(pool,'srbminer','GPU')
    assert d['compatible'] is False
    assert any('VRAM insuficient' in x for x in d['reasons'])


def test_redact_command_args_hides_split_and_inline_secrets():
    from mining import controller as mc
    command = [
        "miner.exe", "--user", "wallet.worker", "--pass", "POOL_SECRET_SENTINEL",
        "--password=INLINE_SECRET_SENTINEL", "-p", "SHORT_SECRET_SENTINEL",
        "--api-access-token", "TOKEN_SECRET_SENTINEL",
    ]
    rendered = " ".join(mc._redact_command_args(command))
    for secret in (
        "POOL_SECRET_SENTINEL", "INLINE_SECRET_SENTINEL",
        "SHORT_SECRET_SENTINEL", "TOKEN_SECRET_SENTINEL",
    ):
        assert secret not in rendered
    assert rendered.count("[REDACTED]") == 4


def test_controller_launch_log_redacts_pool_password(monkeypatch, tmp_path):
    from mining import controller as mc

    class FakeProc:
        def __init__(self, *args, **kwargs):
            self.args = args[0]
            self.returncode = None
            self.pid = 48761
        def poll(self): return self.returncode
        def terminate(self): self.returncode = 0
        def wait(self, timeout=None): return self.returncode
        def kill(self): self.returncode = -9

    monkeypatch.setattr(mc, "LOG", tmp_path / "miner.log")
    monkeypatch.setattr(mc, "_resolve_binary", lambda mid, explicit_path=None: "C:/fake/SRBMiner-MULTI.exe")
    monkeypatch.setattr(mc.subprocess, "Popen", FakeProc)
    monkeypatch.setattr(mc, "_metrics", lambda: {
        "api_connected": False, "hashrate_hs": None, "hashrate_display": None,
        "accepted_shares": None, "rejected_shares": None, "gpu": {}, "system": {},
        "raw_api": None,
    })
    secret = "POOL_SECRET_SENTINEL"
    started = mc.start({
        "miner_id": "srbminer", "pool_id": "2miners-rvn-eu",
        "wallet": "RWalletExample123", "worker": "testRig",
        "algorithm": "KawPoW", "device": "GPU", "use_ssl": False,
        "password": secret,
    })
    assert started["pid"] == 48761
    log = mc.LOG.read_text(encoding="utf-8")
    assert secret not in log
    assert "[REDACTED]" in log
    mc.stop()


def test_xmrig_config_is_private_temporary_and_deleted_on_stop(monkeypatch, tmp_path):
    import os
    from mining import controller as mc

    class FakeProc:
        def __init__(self, *args, **kwargs):
            self.args = args[0]
            self.returncode = None
            self.pid = 48762
        def poll(self): return self.returncode
        def terminate(self): self.returncode = 0
        def wait(self, timeout=None): return self.returncode
        def kill(self): self.returncode = -9

    monkeypatch.setattr(mc, "tempfile.tempdir", str(tmp_path))
    monkeypatch.setattr(mc, "LOG", tmp_path / "miner.log")
    monkeypatch.setattr(mc, "_resolve_binary", lambda mid, explicit_path=None: "C:/fake/xmrig.exe")
    monkeypatch.setattr(mc.subprocess, "Popen", FakeProc)
    monkeypatch.setattr(mc, "_metrics", lambda: {
        "api_connected": False, "hashrate_hs": None, "hashrate_display": None,
        "accepted_shares": None, "rejected_shares": None, "gpu": {}, "system": {},
        "raw_api": None,
    })
    secret = "XMRIG_SECRET_SENTINEL"
    started = mc.start({
        "miner_id": "xmrig", "pool_id": "unmineable-randomx-xmr",
        "wallet": "XMRWalletExample123", "worker": "testRig",
        "algorithm": "RandomX", "device": "CPU", "use_ssl": False,
        "password": secret,
    })
    config_path = mc._runtime_config_path
    assert config_path is not None and config_path.exists()
    assert config_path.name.startswith("nexus-xmrig-")
    assert config_path != mc.RUNTIME / "xmrig.runtime.json"
    config = __import__("json").loads(config_path.read_text(encoding="utf-8"))
    assert config["pools"][0]["pass"] == secret
    assert secret not in mc.LOG.read_text(encoding="utf-8")
    if os.name != "nt":
        assert config_path.stat().st_mode & 0o777 == 0o600
    assert started["status"] in {"starting", "running"}
    mc.stop()
    assert not config_path.exists()
    assert mc._runtime_config_path is None
