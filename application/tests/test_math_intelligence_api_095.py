from fastapi.testclient import TestClient
from nexus_master import app

def test_math_catalog_is_local_and_has_required_engines():
    with TestClient(app) as c:
        r=c.get('/api/math-intelligence/catalog')
        assert r.status_code==200
        d=r.json()
        assert d['private_local'] is True
        ids={x['id'] for x in d['shortcuts']}
        assert {'sha512_exact','modular_solver','candidate_triage'} <= ids

def test_hash_benchmark_api_sha512():
    with TestClient(app) as c:
        r=c.post('/api/math-intelligence/hash-benchmark',json={'algorithms':['sha512'],'payload_bytes':64,'iterations':10})
        assert r.status_code==200
        assert r.json()['results'][0]['algorithm']=='sha512'

def test_modular_solver_api():
    with TestClient(app) as c:
        r=c.post('/api/math-intelligence/modular-solve',json={'a':14,'b':30,'modulus':100})
        assert r.status_code==200 and r.json()['verification'] is True

def test_triage_api_does_not_auto_apply():
    with TestClient(app) as c:
        r=c.post('/api/math-intelligence/triage',json={'baseline_hashrate':100,'candidate_hashrate':110,'duration_seconds':240,'accepted_shares':10,'rejected_shares':0,'exact_equivalence_verified':True,'independent_runs':3})
        assert r.status_code==200
        assert r.json()['auto_apply'] is False
