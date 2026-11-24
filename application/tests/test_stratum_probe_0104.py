import json, socket, threading
from mining.stratum_probe import probe_stratum


def fake_stratum(auth_ok=True):
    server=socket.socket(); server.bind(('127.0.0.1',0)); server.listen(1)
    port=server.getsockname()[1]
    def run():
        try:
            c,_=server.accept()
            with c:
                f=c.makefile('rwb')
                req1=json.loads(f.readline())
                assert req1['method']=='mining.subscribe'
                f.write((json.dumps({'id':1,'result':[[], 'extranonce', 4], 'error':None})+'\n').encode()); f.flush()
                req2=json.loads(f.readline())
                assert req2['method']=='mining.authorize'
                f.write((json.dumps({'id':2,'result':auth_ok,'error':None if auth_ok else [20,'unauthorized',None]})+'\n').encode()); f.flush()
        finally:
            server.close()
    th=threading.Thread(target=run,daemon=True); th.start()
    return port,th


def test_stratum_probe_subscribe_and_authorize_no_work():
    port,th=fake_stratum(True)
    r=probe_stratum('127.0.0.1',port,'wallet.worker','x',False,3)
    th.join(1)
    assert not th.is_alive()
    assert r['ok'] is True and r['subscribed'] is True and r['authorized'] is True
    assert r['no_work_requested'] is True


def test_stratum_probe_reports_auth_rejected():
    port,th=fake_stratum(False)
    r=probe_stratum('127.0.0.1',port,'wallet.worker','x',False,3)
    th.join(1)
    assert not th.is_alive()
    assert r['ok'] is False and r['stage']=='authorize_rejected'


def test_stratum_probe_rejects_invalid_endpoint_inputs():
    import pytest
    with pytest.raises(ValueError): probe_stratum('bad host',3333,'wallet.worker')
    with pytest.raises(ValueError): probe_stratum('localhost',70000,'wallet.worker')
