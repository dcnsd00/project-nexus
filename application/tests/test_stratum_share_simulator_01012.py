from mining.stratum_share_simulator import run_local_submit_scenario

def test_share_accepted():
    r=run_local_submit_scenario()
    assert r['ok'] is True
    assert r['pool_verdict']['code']=='ACCEPTED'
    assert r['handshake']==r['job_received']==r['submit_sent']=='PASS'

def test_pool_rejection():
    r=run_local_submit_scenario(reject=True)
    assert r['ok'] is False
    assert r['pool_verdict']['code']=='POOL_REJECT'

def test_stale_job_rejection():
    r=run_local_submit_scenario(stale=True)
    assert r['ok'] is False
    assert r['pool_verdict']['code']=='STALE_JOB'

def test_duplicate_share_rejection():
    r=run_local_submit_scenario(duplicate=True)
    assert r['ok'] is True
    assert r['duplicate_verdict']['code']=='DUPLICATE_SHARE'
