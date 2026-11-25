import hashlib, json, socket, threading
import pytest
from mining.stratum_session import parse_notify, build_coinbase_hash, build_merkle_root, build_header, probe_job, StratumSessionError

JOB=['job-1','00'*32,'01000000','ffffffff',[], '20000000','1d00ffff','65a1b2c3',True]

def test_parse_valid_notify():
    got=parse_notify(JOB)
    assert got['job_id']=='job-1' and got['clean_jobs'] is True and got['merkle_branch_count']==0

def test_parse_rejects_malformed_notify():
    with pytest.raises(StratumSessionError): parse_notify(JOB[:8])
    bad=JOB.copy(); bad[1]='xyz'
    with pytest.raises(StratumSessionError): parse_notify(bad)

def test_coinbase_hash_and_header():
    raw=bytes.fromhex('01020304aabbccdd')
    expected=hashlib.sha256(hashlib.sha256(raw).digest()).digest()
    got=build_coinbase_hash('01020304','aa','bb','ccdd')
    assert got==expected
    root=build_merkle_root(got,[])
    header=build_header('20000000','00'*32,root,'65a1b2c3','1d00ffff',0x12345678)
    assert len(header)==80 and header[-4:]==bytes.fromhex('78563412')

def test_merkle_branch_order():
    a=b'\x11'*32; b='22'*32
    expected=hashlib.sha256(hashlib.sha256(a+bytes.fromhex(b)).digest()).digest()
    assert build_merkle_root(a,[b])==expected

def test_probe_job_local_mock_server():
    server=socket.socket(); server.bind(('127.0.0.1',0)); server.listen(1)
    port=server.getsockname()[1]
    def serve():
        conn,_=server.accept()
        with conn:
            buf=b''; seen=set()
            while len(seen)<2:
                buf+=conn.recv(4096)
                while b'\n' in buf:
                    line,buf=buf.split(b'\n',1)
                    if not line: continue
                    obj=json.loads(line); seen.add(obj['id'])
            msgs=[
              {'id':1,'result':[[['mining.notify','x']],'abcd',4],'error':None},
              {'id':2,'result':True,'error':None},
              {'id':None,'method':'mining.set_difficulty','params':[64]},
              {'id':None,'method':'mining.notify','params':JOB},
            ]
            for m in msgs: conn.sendall((json.dumps(m)+'\n').encode())
    th=threading.Thread(target=serve,daemon=True); th.start()
    result=probe_job('127.0.0.1',port,'wallet.worker',timeout=4)
    server.close(); th.join(1)
    assert result['ok'] and result['job_received'] and result['authorized']
    assert result['difficulty']==64 and result['job']['job_id']=='job-1'
    assert 'no share submitted' in result['scope']


def test_parse_notify_rejects_invalid_job_ids_and_oversized_coinbase():
    bad = JOB.copy()
    bad[0] = ""
    with pytest.raises(StratumSessionError):
        parse_notify(bad)
    bad = JOB.copy()
    bad[2] = "aa" * 100000
    with pytest.raises(StratumSessionError):
        parse_notify(bad)


@pytest.mark.parametrize("value", [0, -1, float("nan"), float("inf"), True, "1"])
def test_stratum_difficulty_rejects_non_positive_or_non_finite_values(value):
    from mining.stratum_session import parse_difficulty
    with pytest.raises(StratumSessionError):
        parse_difficulty([value])


@pytest.mark.parametrize("value", [0.000001, 1, 64, 1e30])
def test_stratum_difficulty_accepts_positive_finite_values(value):
    from mining.stratum_session import parse_difficulty
    assert parse_difficulty([value]) == float(value)


def test_set_extranonce_validates_hex_and_size_boundaries():
    from mining.stratum_session import parse_set_extranonce
    assert parse_set_extranonce(["aabb", 4]) == ("aabb", 4)
    for params in (["xyz", 4], ["aa", -1], ["aa", 33], ["aa", True], ["aa"], ["aa", 1.5]):
        with pytest.raises(StratumSessionError):
            parse_set_extranonce(params)
