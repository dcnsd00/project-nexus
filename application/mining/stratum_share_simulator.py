"""Loopback-only Stratum V1 share submission simulator; never contacts public pools."""
from __future__ import annotations
import hashlib, json, socket, threading

class ShareSimulationError(RuntimeError): pass

def sha256d(data: bytes) -> bytes:
    return hashlib.sha256(hashlib.sha256(data).digest()).digest()

def header_hash_int(header: bytes) -> int:
    if len(header) != 80: raise ShareSimulationError('Header must be 80 bytes')
    return int.from_bytes(sha256d(header)[::-1], 'big')

def find_share(prefix: bytes, target: int, limit: int = 100000):
    if len(prefix) != 76: raise ShareSimulationError('Header prefix must be 76 bytes')
    for nonce in range(limit):
        header = prefix + nonce.to_bytes(4, 'little')
        digest = sha256d(header)
        value = int.from_bytes(digest[::-1], 'big')
        if value <= target: return nonce, digest.hex(), value
    raise ShareSimulationError('No share found within nonce limit')

class MockPool:
    def __init__(self, *, reject=False, stale=False):
        self.reject, self.stale, self.seen = reject, stale, set()
    def validate(self, worker, job_id, nonce, value, target):
        if self.stale: return {'accepted':False,'code':'STALE_JOB'}
        key=(worker,job_id,nonce)
        if key in self.seen: return {'accepted':False,'code':'DUPLICATE_SHARE'}
        self.seen.add(key)
        if self.reject: return {'accepted':False,'code':'POOL_REJECT'}
        if value > target: return {'accepted':False,'code':'LOW_DIFFICULTY'}
        return {'accepted':True,'code':'ACCEPTED'}

def run_local_submit_scenario(*, reject=False, stale=False, duplicate=False):
    target=(1 << 256)-1  # deliberately trivial mock share target; not a block target
    pool=MockPool(reject=reject, stale=stale)
    prefix=bytes.fromhex('20000000'+'00'*32+'11'*32+'65a1b2c3'+'207fffff')
    nonce,digest,value=find_share(prefix,target,limit=10)
    job_id='nexus-sim-job-01'; worker='nexus.sim'
    listener=socket.socket(); listener.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
    listener.bind(('127.0.0.1',0)); listener.listen(1); listener.settimeout(4)
    port=listener.getsockname()[1]; server_result={}
    def serve():
        try:
            conn,_=listener.accept()
            with conn:
                f=conn.makefile('rwb')
                for expected in ('mining.subscribe','mining.authorize'):
                    msg=json.loads(f.readline())
                    if msg.get('method') != expected: raise ShareSimulationError('Unexpected handshake method')
                    result=[[], 'abcd', 4] if expected.endswith('subscribe') else True
                    f.write((json.dumps({'id':msg['id'],'result':result,'error':None})+'\n').encode()); f.flush()
                f.write((json.dumps({'id':None,'method':'mining.set_difficulty','params':[1.0]})+'\n').encode())
                f.write((json.dumps({'id':None,'method':'mining.notify','params':[job_id,'00'*32,'01000000','ffffffff',[],'20000000','207fffff','65a1b2c3',True]})+'\n').encode()); f.flush()
                sub=json.loads(f.readline())
                if sub.get('method')!='mining.submit' or len(sub.get('params',[]))!=5: raise ShareSimulationError('Invalid mining.submit')
                w,jid,ex2,ntime,nonce_hex=sub['params']; n=int(nonce_hex,16)
                # The mock pool recomputes the header hash independently; it does not trust client data.
                server_value=header_hash_int(prefix+n.to_bytes(4,'little'))
                verdict=pool.validate(w,jid,n,server_value,target)
                f.write((json.dumps({'id':sub['id'],'result':verdict['accepted'],'error':None if verdict['accepted'] else [23,verdict['code'],'mock rejection']})+'\n').encode()); f.flush()
                server_result['verdict']=verdict
                if duplicate: server_result['duplicate_verdict']=pool.validate(w,jid,n,server_value,target)
        except Exception as e: server_result['error']=str(e)
        finally: listener.close()
    th=threading.Thread(target=serve,daemon=True); th.start()
    sock=socket.create_connection(('127.0.0.1',port),timeout=3); sock.settimeout(3); f=sock.makefile('rwb')
    try:
        for mid,method,params in ((1,'mining.subscribe',['NEXUS-sim',None]),(2,'mining.authorize',[worker,'x'])):
            f.write((json.dumps({'id':mid,'method':method,'params':params})+'\n').encode()); f.flush()
        responses={}
        while len(responses)<2:
            m=json.loads(f.readline())
            if m.get('id') in (1,2): responses[m['id']]=m
        if responses[1].get('error') or responses[2].get('result') is not True: raise ShareSimulationError('Handshake failed')
        notifications=[]
        while len(notifications)<2:
            m=json.loads(f.readline())
            if m.get('method') in ('mining.set_difficulty','mining.notify'): notifications.append(m)
        submit={'id':3,'method':'mining.submit','params':[worker,job_id,'00000000','65a1b2c3',f'{nonce:08x}']}
        f.write((json.dumps(submit)+'\n').encode()); f.flush(); ack=json.loads(f.readline())
        th.join(3)
        return {'ok':bool(ack.get('result')),'handshake':'PASS','job_received':'PASS','submit_sent':'PASS',
                'nonce':nonce,'hash':digest,'hash_meets_mock_target':value<=target,'pool_response':ack,
                'pool_verdict':server_result.get('verdict'),'duplicate_verdict':server_result.get('duplicate_verdict'),
                'server_error':server_result.get('error'),'scenario':{'reject':reject,'stale':stale,'duplicate':duplicate},
                'scope':'Loopback mock only; no public pool, real miner, GPU or wallet.'}
    finally: sock.close()
