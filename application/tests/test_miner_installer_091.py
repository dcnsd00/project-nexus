import io, json, zipfile
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from nexus_master import app
from mining import installer as mi

def test_installer_catalog_route_lists_official_sources():
    with TestClient(app) as c:
        r=c.get('/api/mining/installers')
        assert r.status_code==200
        rows={x['id']:x for x in r.json()['installers']}
        assert {'xmrig','srbminer','trex','lolminer','gminer','rigel','teamredminer','bzminer'} <= set(rows)
        assert rows['teamredminer']['automatic_download'] is False

def test_latest_release_requires_windows_asset(monkeypatch):
    payload={'tag_name':'v1.2','html_url':'https://github.com/xmrig/xmrig/releases/tag/v1.2','assets':[{'name':'xmrig-1.2-windows-x64.zip','browser_download_url':'https://example.invalid/a.zip','size':123,'digest':'sha256:'+'a'*64}]}
    monkeypatch.setattr(mi,'_request',lambda url:json.dumps(payload).encode())
    d=mi.latest_release('xmrig')
    assert d['version']=='v1.2' and d['asset_name'].endswith('.zip')

def test_installer_refuses_zip_path_traversal(tmp_path):
    zpath=tmp_path/'bad.zip'
    with zipfile.ZipFile(zpath,'w') as z: z.writestr('../evil.exe',b'bad')
    with pytest.raises(ValueError,match='cale nesigură'):
        mi._safe_extract_zip(zpath,tmp_path/'out')

def test_installer_extracts_only_expected_windows_package(monkeypatch,tmp_path):
    import hashlib
    buf=io.BytesIO()
    with zipfile.ZipFile(buf,'w') as z: z.writestr('release/xmrig.exe',b'MZ fake executable')
    blob=buf.getvalue(); digest=hashlib.sha256(blob).hexdigest()
    release={'id':'xmrig','name':'XMRig','version':'test-1','release_url':'https://github.com/xmrig/xmrig/releases/tag/test-1',
             'asset_name':'xmrig-windows-x64.zip','download_url':'https://github.com/xmrig/xmrig/releases/download/test/a.zip',
             'size_bytes':len(blob),'upstream_digest':'sha256:'+digest,'automatic_download':True,'source_repo':'xmrig/xmrig'}
    monkeypatch.setattr(mi,'latest_release',lambda mid:release)
    class Resp:
        def __enter__(self): return self
        def __exit__(self,*a): pass
        def read(self,n=-1):
            nonlocal blob
            if not blob:return b''
            if n<0: out=blob; blob=b''; return out
            out=blob[:n]; blob=blob[n:]; return out
    monkeypatch.setattr(mi.urllib.request,'urlopen',lambda *a,**k:Resp())
    monkeypatch.setattr(mi,'INSTALL_ROOT',tmp_path/'miners')
    d=mi.install('xmrig')
    assert d['ok'] and d['integrity']=='sha256_verified_against_upstream'
    assert Path(d['installed_executable']).name=='xmrig.exe'


def test_2miners_pool_account_read_only_mapping(monkeypatch):
    import json
    from nexus_master import app
    class Response:
        def __enter__(self): return self
        def __exit__(self,*a): pass
        def read(self):
            return json.dumps({'currentHashrate':1234,'hashrate':1000,'stats':{'balance':123456789,'immature':0,'paid':200000000,'lastShare':1700000000},'workersOnline':1,'workersTotal':1,'paymentsTotal':2,'24hreward':100000000}).encode()
    monkeypatch.setattr('urllib.request.urlopen',lambda *a,**k:Response())
    with TestClient(app) as c:
        r=c.get('/api/mining/pool-account',params={'pool_id':'2miners-rvn-eu','wallet':'RTestWallet123'})
        assert r.status_code==200
        d=r.json()
        assert d['read_only'] is True
        assert d['balance']['coin']==1.23456789
        assert d['paid']['coin']==2.0


def test_pool_account_rejects_non_2miners_pool():
    with TestClient(app) as c:
        r=c.get('/api/mining/pool-account',params={'pool_id':'woolypooly-rvn','wallet':'RTestWallet123'})
        assert r.status_code==400
