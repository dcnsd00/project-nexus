from fastapi.testclient import TestClient
import nexus_master

client=TestClient(nexus_master.app)

def test_stratum_probe_uses_operator_tls_hostname(monkeypatch):
    seen={}
    def fake(host,port,username,password,use_tls,timeout):
        seen.update(host=host,port=port,username=username,tls=use_tls)
        return {'ok':False,'stage':'mock','no_work_requested':True}
    monkeypatch.setattr(nexus_master,'probe_stratum',fake)
    r=client.post('/api/mining/stratum-probe',json={
        'pool_id':'2miners-rvn-solo-eu','wallet':'R'+'a'*33,'worker':'rig1','use_tls':True
    })
    assert r.status_code==200
    assert seen['host']=='solo-rvn.2miners.com'
    assert seen['port']==17070
    assert seen['tls'] is True
    assert seen['username'].endswith('.rig1')
