"""Stratum V1 connection diagnostics and Bitcoin job/header reconstruction.
The live CPU scanner/submission lifecycle is implemented in stratum_miner.py.
"""
from __future__ import annotations
import json, socket, ssl, time, re, hashlib
from typing import Any

_HEX = re.compile(r'^(?:[0-9a-fA-F]{2})*$')
_HOST = re.compile(r'^[A-Za-z0-9.-]{1,253}$')

class StratumSessionError(RuntimeError):
    pass

def _send(sock, obj):
    sock.sendall((json.dumps(obj, separators=(',', ':'))+'\n').encode())

def _recv_lines(sock, deadline):
    buf=b''
    while time.monotonic() < deadline:
        try: chunk=sock.recv(8192)
        except socket.timeout: continue
        if not chunk: return
        buf += chunk
        if len(buf)>1_048_576: raise StratumSessionError('Mesaj Stratum depășește 1 MiB.')
        while b'\n' in buf:
            line,buf=buf.split(b'\n',1)
            if not line.strip(): continue
            try: msg=json.loads(line.decode('utf-8'))
            except (UnicodeDecodeError,json.JSONDecodeError): continue
            if isinstance(msg,dict): yield msg

def parse_notify(params: Any) -> dict:
    if not isinstance(params,list) or len(params)<9:
        raise StratumSessionError('mining.notify are mai puțin de 9 parametri.')
    job_id, prev_hash, coinb1, coinb2, branches, version, nbits, ntime, clean = params[:9]
    for name,value in [('prev_hash',prev_hash),('coinb1',coinb1),('coinb2',coinb2),('version',version),('nbits',nbits),('ntime',ntime)]:
        if not isinstance(value,str) or not _HEX.fullmatch(value): raise StratumSessionError(f'Câmp hex invalid: {name}.')
    if len(prev_hash)!=64 or len(version)!=8 or len(nbits)!=8 or len(ntime)!=8:
        raise StratumSessionError('Lungime invalidă pentru prev_hash/version/nbits/ntime.')
    if not isinstance(branches,list) or len(branches)>64 or any(not isinstance(x,str) or len(x)!=64 or not _HEX.fullmatch(x) for x in branches):
        raise StratumSessionError('Lista Merkle branches este invalidă.')
    if not isinstance(clean,bool): raise StratumSessionError('clean_jobs trebuie să fie boolean.')
    return {'job_id':str(job_id),'prev_hash':prev_hash,'coinb1_bytes':len(coinb1)//2,'coinb2_bytes':len(coinb2)//2,
            'merkle_branch_count':len(branches),'version':version,'nbits':nbits,'ntime':ntime,'clean_jobs':clean}

def build_coinbase_hash(coinb1: str, extranonce1: str, extranonce2: str, coinb2: str) -> bytes:
    parts=[coinb1,extranonce1,extranonce2,coinb2]
    if any(not isinstance(x,str) or not _HEX.fullmatch(x) for x in parts): raise ValueError('Coinbase/extranonce hex invalid.')
    raw=b''.join(bytes.fromhex(x) for x in parts)
    return hashlib.sha256(hashlib.sha256(raw).digest()).digest()

def build_merkle_root(coinbase_hash: bytes, branches: list[str]) -> bytes:
    if len(coinbase_hash)!=32: raise ValueError('Coinbase hash trebuie să aibă 32 bytes.')
    root=coinbase_hash
    for branch in branches:
        if not isinstance(branch,str) or len(branch)!=64 or not _HEX.fullmatch(branch): raise ValueError('Merkle branch invalid.')
        root=hashlib.sha256(hashlib.sha256(root+bytes.fromhex(branch)).digest()).digest()
    return root

def build_header(version: str, prev_hash: str, merkle_root: bytes, ntime: str, nbits: str, nonce: int) -> bytes:
    if not 0<=nonce<=0xffffffff: raise ValueError('Nonce în afara intervalului uint32.')
    fields=[version,prev_hash,ntime,nbits]
    if any(not _HEX.fullmatch(x) for x in fields): raise ValueError('Header field hex invalid.')
    # Stratum encodes version/ntime/nbits as displayed uint32 hex; serialize LE.
    # prev_hash and computed Merkle root are already in their serialized byte order.
    return bytes.fromhex(version)[::-1]+bytes.fromhex(prev_hash)+merkle_root+bytes.fromhex(ntime)[::-1]+bytes.fromhex(nbits)[::-1]+nonce.to_bytes(4,'little')

def probe_job(host: str, port: int, username: str, password: str='x', use_tls: bool=False, timeout: float=8.0) -> dict:
    if not isinstance(host,str) or not _HOST.fullmatch(host) or '..' in host: raise ValueError('Host Stratum invalid.')
    if isinstance(port,bool) or not isinstance(port,int) or not 1<=port<=65535: raise ValueError('Port Stratum invalid.')
    if not isinstance(username,str) or not 3<=len(username)<=256 or any(c.isspace() for c in username): raise ValueError('Username invalid.')
    timeout=max(2.0,min(float(timeout),15.0)); start=time.perf_counter(); deadline=time.monotonic()+timeout
    ctx=ssl.create_default_context() if use_tls else None
    sock=socket.create_connection((host,port),timeout=min(timeout,5))
    sock.settimeout(.4)
    conn=ctx.wrap_socket(sock,server_hostname=host) if ctx else sock
    pending={1:None,2:None}; subscribed=False; authorized=False; difficulty=None; job=None; extranonce1=None; extranonce2_size=None
    try:
        _send(conn,{'id':1,'method':'mining.subscribe','params':['NEXUS/0.10.10',None]})
        # authorize immediately; notifications and responses can interleave.
        _send(conn,{'id':2,'method':'mining.authorize','params':[username,password]})
        for msg in _recv_lines(conn,deadline):
            mid=msg.get('id')
            if mid in pending:
                pending[mid]=msg
                if mid==1 and not msg.get('error') and isinstance(msg.get('result'),list):
                    result=msg['result']; subscribed=True
                    if len(result)>1: extranonce1=result[1]
                    if len(result)>2: extranonce2_size=result[2]
                if mid==2: authorized=msg.get('result') is True and not msg.get('error')
            method=msg.get('method'); params=msg.get('params')
            if method=='mining.set_difficulty' and isinstance(params,list) and params:
                try: difficulty=float(params[0])
                except (ValueError,TypeError): pass
            elif method=='mining.notify':
                job=parse_notify(params)
            elif method=='mining.set_extranonce' and isinstance(params,list) and len(params)>=2:
                extranonce1,extranonce2_size=params[0],params[1]
            if subscribed and authorized and job:
                break
        if not subscribed or not authorized:
            return {'ok':False,'stage':'subscribe_or_authorize','subscribed':subscribed,'authorized':authorized,
                    'error':'Pool did not complete subscribe and authorize before timeout/job.','job_received':bool(job)}
        if not job: return {'ok':False,'stage':'wait_job','subscribed':True,'authorized':True,'job_received':False,
                           'difficulty':difficulty,'error':'Handshake valid, dar pool-ul nu a trimis mining.notify în intervalul de test.'}
        return {'ok':True,'stage':'job_received','subscribed':True,'authorized':True,'job_received':True,
                'job':job,'difficulty':difficulty,'extranonce1':extranonce1,'extranonce2_size':extranonce2_size,
                'latency_ms':round((time.perf_counter()-start)*1000,2),
                'scope':'TCP/TLS + subscribe + authorize + mining.notify parse; no nonce scan and no share submitted.'}
    finally: conn.close()


def assemble_bitcoin_header(job_params: Any, extranonce1: str, extranonce2: str) -> bytes:
    """Build an 80-byte Bitcoin header from a complete Stratum mining.notify payload."""
    parse_notify(job_params)
    _, prev_hash, coinb1, coinb2, branches, version, nbits, ntime, _ = job_params[:9]
    coinbase_hash = build_coinbase_hash(coinb1, extranonce1, extranonce2, coinb2)
    merkle_root = build_merkle_root(coinbase_hash, branches)
    header = build_header(version, prev_hash, merkle_root, ntime, nbits, 0)
    if len(header) != 80:
        raise StratumSessionError("Header reconstruit nu are 80 bytes.")
    return header
