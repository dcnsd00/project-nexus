import hashlib, json, socket, struct, threading, time

from mining.stratum_miner import StratumBitcoinWorker
from mining.stratum_session import assemble_bitcoin_header, build_header
from mining.bitcoin_pow_engine import difficulty_target

JOB=['nexus-job-014','00112233445566778899aabbccddeeff00112233445566778899aabbccddeeff','01000000','ffffffff',['11'*32], '20000000','207fffff','65a1b2c3',True]

def _read_json_line(conn, buf=b''):
    while b'\n' not in buf:
        part=conn.recv(8192)
        if not part: raise RuntimeError('client disconnected')
        buf+=part
    line,rest=buf.split(b'\n',1)
    return json.loads(line.decode()),rest

def _mock_pool(reject=False):
    listener=socket.socket(); listener.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
    listener.bind(('127.0.0.1',0)); listener.listen(1); listener.settimeout(5)
    result={'port':listener.getsockname()[1]}; submitted=threading.Event(); failures=[]
    def run():
        try:
            conn,_=listener.accept(); conn.settimeout(5)
            with conn:
                buf=b''; seen={}
                while len(seen)<2:
                    msg,buf=_read_json_line(conn,buf); seen[msg['method']]=msg
                assert seen['mining.subscribe']['params'][0].startswith('NEXUS/')
                conn.sendall((json.dumps({'id':1,'result':[[], 'a1b2', 4],'error':None})+'\n').encode())
                conn.sendall((json.dumps({'id':2,'result':True,'error':None})+'\n').encode())
                conn.sendall((json.dumps({'id':None,'method':'mining.set_difficulty','params':[1e-20]})+'\n').encode())
                conn.sendall((json.dumps({'id':None,'method':'mining.notify','params':JOB})+'\n').encode())
                while True:
                    msg,buf=_read_json_line(conn,buf)
                    if msg.get('method')!='mining.submit': continue
                    worker,job_id,ex2,ntime,nonce_hex=msg['params']
                    assert worker=='public-address.worker'
                    assert job_id==JOB[0]
                    assert len(ex2)==8 and ntime==JOB[7] and len(nonce_hex)==8
                    # Independent mock-pool reconstruction: deliberately does not call
                    # NEXUS assemble_bitcoin_header(), so byte-order/merkle bugs are observable.
                    coinbase=bytes.fromhex(JOB[2]+'a1b2'+ex2+JOB[3])
                    merkle=hashlib.sha256(hashlib.sha256(coinbase).digest()).digest()
                    for branch in JOB[4]:
                        merkle=hashlib.sha256(hashlib.sha256(merkle+bytes.fromhex(branch)).digest()).digest()
                    header=(bytes.fromhex(JOB[5])[::-1]+bytes.fromhex(JOB[1])+merkle+
                            bytes.fromhex(JOB[7])[::-1]+bytes.fromhex(JOB[6])[::-1]+
                            int(nonce_hex,16).to_bytes(4,'little'))
                    assert len(header)==80
                    digest=hashlib.sha256(hashlib.sha256(header).digest()).digest()
                    hval=int.from_bytes(digest[::-1],'big')
                    assert hval<=difficulty_target(1e-20)
                    submitted.set()
                    ack={'id':msg['id'],'result':False if reject else True,
                         'error':[23,'test reject',None] if reject else None}
                    conn.sendall((json.dumps(ack)+'\n').encode())
                    # Wait for the test to stop the worker; keep the connection alive.
                    while conn.recv(1024): pass
                    break
        except Exception as exc: failures.append(repr(exc))
        finally: listener.close()
    th=threading.Thread(target=run,daemon=True); th.start()
    result['thread']=th; result['submitted']=submitted; result['failures']=failures
    return result

def _run_case(reject=False):
    pool=_mock_pool(reject)
    worker=StratumBitcoinWorker('127.0.0.1',pool['port'],'public-address.worker','x',False,timeout=4,scan_chunk=1).start()
    assert pool['submitted'].wait(5), worker.status()
    deadline=time.time()+3
    expected='rejected_shares' if reject else 'accepted_shares'
    while time.time()<deadline and worker.metrics()[expected]<1: time.sleep(.02)
    metrics=worker.metrics()
    worker.terminate(); worker.wait(3); pool['thread'].join(3)
    assert not pool['failures'], pool['failures']
    assert metrics[expected]>=1, metrics
    return metrics

def test_stratum_header_serializes_integer_fields_little_endian():
    root=bytes.fromhex('3ba3edfd7a7b12b27ac72c3e67768f617fc81bc3888a51323a9fb8aa4b1e5e4a')
    header=build_header('00000001','00'*32,root,'495fab29','1d00ffff',0x7c2bac1d)
    assert header[:4]==bytes.fromhex('01000000')
    assert header[68:72]==bytes.fromhex('29ab5f49')
    assert header[72:76]==bytes.fromhex('ffff001d')
    assert header[76:80]==bytes.fromhex('1dac2b7c')
    assert hashlib.sha256(hashlib.sha256(header).digest()).digest()[::-1].hex().startswith('000000000019d668')

def test_worker_handshake_scan_submit_and_pool_accept():
    m=_run_case(False)
    assert m['accepted_shares']==1 and m['hashes_scanned']>=1

def test_worker_records_pool_rejection():
    m=_run_case(True)
    assert m['rejected_shares']==1 and m['accepted_shares']==0


def test_controller_starts_and_stops_integrated_native_worker(monkeypatch):
    from mining import controller
    pool=_mock_pool(False)
    catalog_pool={'id':'custom','pool':'Local mock','name':'Local Stratum BTC test','coin':'BTC',
                  'algorithm':'SHA-256d','mode':'SOLO','host':'127.0.0.1','port':pool['port'],
                  'miner':'NEXUS internal','worker_format':'WALLET.worker','stratum_protocol':'V1'}
    monkeypatch.setattr(controller,'_pool_catalog',lambda:[catalog_pool])
    req={'miner_id':'nexus-btc-cpu','pool_id':'custom','wallet':'public-address','worker':'worker',
         'password':'x','algorithm':'SHA-256d','device':'CPU','use_ssl':False,
         'custom_host':'127.0.0.1','custom_port':pool['port'],'mining_mode':'SOLO_POOL'}
    started=controller.start(req)
    assert started['miner_id']=='nexus-btc-cpu'
    assert pool['submitted'].wait(5)
    deadline=time.time()+3
    while time.time()<deadline and controller.status()['metrics'].get('accepted_shares',0)<1:
        time.sleep(.02)
    running=controller.status()
    assert running['miner_id']=='nexus-btc-cpu'
    assert running['metrics']['accepted_shares']>=1
    assert running['metrics']['native_requested'] is True
    assert running['metrics']['engine'].startswith(('native_sha256d_variant_', 'exact_sha256d_midstate'))
    stopped=controller.stop()
    assert stopped['status']=='stopped'
    pool['thread'].join(3)
    assert not pool['failures'], pool['failures']

def test_api_compatibility_exposes_internal_worker_for_public_pool_btc():
    import json
    import nexus_master
    pools=json.load(open('mining/pools.json',encoding='utf-8'))['pools']
    pool=next(p for p in pools if p['id']=='public-pool-btc-solo')
    result=nexus_master._compatibility(pool,'nexus-btc-cpu','CPU')
    assert result['compatible'] is True, result
    assert result['algorithm']=='SHA-256d' and result['device']=='CPU'

def test_fastapi_start_status_stop_runs_complete_stratum_pipeline(tmp_path, monkeypatch):
    import json
    from fastapi.testclient import TestClient
    import nexus_master
    from mining import controller

    mock=_mock_pool(False)
    pool={'id':'custom','pool':'Custom mock','name':'BTC mock SOLO','coin':'BTC','algorithm':'SHA-256d',
          'mode':'SOLO','host':'','port':0,'ssl_port':0,'miner':'NEXUS internal',
          'worker_format':'WALLET.worker','stratum_protocol':'V1'}
    (tmp_path/'mining').mkdir()
    (tmp_path/'mining'/'pools.json').write_text(json.dumps({'pools':[pool]}),encoding='utf-8')
    monkeypatch.setattr(nexus_master,'ROOT',tmp_path)
    monkeypatch.setattr(controller,'_pool_catalog',lambda:[pool])
    with TestClient(nexus_master.app) as client:
        response=client.post('/api/mining/start',json={
            'miner_id':'nexus-btc-cpu','pool_id':'custom','wallet':'public-address','worker':'worker',
            'password':'x','algorithm':'SHA-256d','device':'CPU','use_ssl':False,
            'custom_host':'127.0.0.1','custom_port':mock['port'],'mining_mode':'SOLO_POOL'})
        assert response.status_code==200, response.text
        assert response.json()['miner_id']=='nexus-btc-cpu'
        assert mock['submitted'].wait(5)
        deadline=time.time()+3
        state=None
        while time.time()<deadline:
            state=client.get('/api/mining/status').json()
            if state['metrics'].get('accepted_shares',0)>=1: break
            time.sleep(.02)
        assert state and state['metrics']['accepted_shares']>=1, state
        stopped=client.post('/api/mining/stop')
        assert stopped.status_code==200 and stopped.json()['status']=='stopped'
    mock['thread'].join(3)
    assert not mock['failures'], mock['failures']


def test_stratum_prevhash_is_retained_in_wire_serialization_order():
    # CGMiner's reference parser concatenates the Stratum prev_hash field into
    # header data before hex2bin; nonzero bytes catch accidental byte reversal.
    prev='0123456789abcdef'*4
    header=build_header('20000000',prev,bytes(range(32)),'65a1b2c3','207fffff',0x01020304)
    assert header[4:36] == bytes.fromhex(prev)
    assert header[0:4] == bytes.fromhex('00000020')
    assert header[68:72] == bytes.fromhex('c3b2a165')
    assert header[72:76] == bytes.fromhex('ffff7f20')
    assert header[76:80] == bytes.fromhex('04030201')
