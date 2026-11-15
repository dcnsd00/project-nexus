"""Integrated low-rate Bitcoin Stratum V1 CPU reference miner for NEXUS.

This is intended for protocol validation and experimentation, not competitive
Bitcoin mining. It uses exact SHA-256d, standard Stratum V1 jobs and submissions.
TLS certificate validation is enabled by default. It never stores private keys.
"""
from __future__ import annotations
import json, socket, ssl, threading, time, hashlib, struct
from collections import deque
from typing import Any

from mining.bitcoin_pow_engine import compact_target, difficulty_target, scan_nonce_range
from mining.native_sha256d import scan_nonce_range_optimized, native_status
from mining.stratum_session import parse_notify, assemble_bitcoin_header, StratumSessionError

class StratumMinerError(RuntimeError):
    pass

class StratumBitcoinWorker:
    def __init__(self, host: str, port: int, username: str, password: str='x',
                 use_tls: bool=False, timeout: float=8.0, scan_chunk: int=50000,
                 prefer_native: bool=False, native_threads: int | None=None, native_variant: int | None=None):
        if not host or len(host)>253 or any(c.isspace() for c in host): raise ValueError('Host Stratum invalid.')
        if isinstance(port,bool) or not isinstance(port,int) or not 1<=port<=65535: raise ValueError('Port Stratum invalid.')
        if not isinstance(username,str) or not 3<=len(username)<=256 or any(c.isspace() for c in username): raise ValueError('Username invalid.')
        if not isinstance(password,str) or len(password)>128: raise ValueError('Parola Stratum invalidă.')
        if not 1<=scan_chunk<=50000: raise ValueError('scan_chunk trebuie să fie 1..50000.')
        self.host,self.port,self.username,self.password=host,port,username,password
        self.use_tls=bool(use_tls); self.timeout=max(2,min(float(timeout),20)); self.scan_chunk=scan_chunk
        self.prefer_native=bool(prefer_native); self.native_threads=native_threads; self.native_variant=native_variant
        self._engine_name='Python exact SHA-256d reference'
        self._stop=threading.Event(); self._thread=None; self._sock=None; self._buf=b''
        self._send_lock=threading.Lock(); self._lock=threading.RLock(); self._next_id=3
        self._pending={}; self._job=None; self._job_seq=0; self._difficulty=None
        self._extranonce1=None; self._extranonce2_size=None; self._extranonce2=0; self._nonce=0
        self._connected=False; self._authorized=False; self._status='created'; self._error=None
        self._started=time.time(); self._hashes=0; self._hash_window=0; self._window_start=time.monotonic()
        self._accepted=0; self._rejected=0; self._submitted=0; self._last_share=None
        self._events=deque(maxlen=100); self._exit_code=None; self.returncode=None; self.pid=None

    def _event(self, text):
        with self._lock: self._events.append({'time':time.strftime('%H:%M:%S'),'message':str(text)})

    def start(self):
        if self._thread and self._thread.is_alive(): raise RuntimeError('Worker deja pornit.')
        self._thread=threading.Thread(target=self._run,name='NEXUS-Stratum-BTC',daemon=True)
        self._thread.start(); return self

    def terminate(self):
        self._stop.set()
        try:
            if self._sock: self._sock.shutdown(socket.SHUT_RDWR)
        except OSError: pass

    def kill(self): self.terminate()

    def wait(self, timeout=None):
        if self._thread: self._thread.join(timeout)
        return self._exit_code

    def poll(self):
        if self._thread is None: return self._exit_code
        if self._thread.is_alive(): return None
        return self._exit_code if self._exit_code is not None else 0

    def _send(self, obj):
        raw=(json.dumps(obj,separators=(',',':'))+'\n').encode()
        with self._send_lock:
            if not self._sock: raise StratumMinerError('Socket închis.')
            self._sock.sendall(raw)

    def _read_messages(self, wait_seconds=0.05):
        if not self._sock: return []
        self._sock.settimeout(max(0.01,wait_seconds))
        try: chunk=self._sock.recv(65536)
        except socket.timeout: return []
        if not chunk: raise StratumMinerError('Pool-ul a închis conexiunea.')
        self._buf+=chunk
        if len(self._buf)>1_048_576: raise StratumMinerError('Buffer Stratum depășește 1 MiB.')
        out=[]
        while b'\n' in self._buf:
            line,self._buf=self._buf.split(b'\n',1)
            if not line.strip(): continue
            try: msg=json.loads(line.decode('utf-8'))
            except (UnicodeDecodeError,json.JSONDecodeError) as exc: raise StratumMinerError(f'Mesaj JSON Stratum invalid: {exc}')
            if isinstance(msg,dict): out.append(msg)
        return out

    def _handle_message(self,msg):
        mid=msg.get('id')
        if mid in self._pending:
            pending=self._pending.pop(mid)
            if pending=='subscribe':
                if msg.get('error') or not isinstance(msg.get('result'),list) or len(msg['result'])<3:
                    raise StratumMinerError(f'Subscribe respins: {msg.get("error")}')
                result=msg['result']; ex1=result[1]; exsize=result[2]
                if not isinstance(ex1,str) or len(ex1)%2 or any(c not in '0123456789abcdefABCDEF' for c in ex1):
                    raise StratumMinerError('extranonce1 invalid din subscribe.')
                if isinstance(exsize,bool) or not isinstance(exsize,int) or not 1<=exsize<=16:
                    raise StratumMinerError('extranonce2_size invalid (1..16 bytes).')
                self._extranonce1=ex1; self._extranonce2_size=exsize
                self._event(f'Subscribe OK; extranonce2={exsize} bytes.')
            elif pending=='authorize':
                if msg.get('error') or msg.get('result') is not True: raise StratumMinerError(f'Authorize respins: {msg.get("error")}')
                self._authorized=True; self._event('Worker autorizat de pool.')
            elif isinstance(pending,dict) and pending.get('type')=='share':
                ok=msg.get('result') is True and not msg.get('error')
                if ok: self._accepted+=1; self._event(f'Share #{pending["seq"]} ACCEPTED de pool.')
                else: self._rejected+=1; self._event(f'Share #{pending["seq"]} REJECTED: {msg.get("error")}')
                self._last_share={'accepted':ok,'response':msg.get('error') or msg.get('result'),'nonce':pending['nonce'],'job_id':pending['job_id']}
            return
        method=msg.get('method'); params=msg.get('params')
        if method=='mining.set_difficulty':
            if not isinstance(params,list) or not params: raise StratumMinerError('set_difficulty fără parametri.')
            value=params[0]
            if isinstance(value,bool) or not isinstance(value,(int,float)) or value<=0: raise StratumMinerError('Dificultate Stratum invalidă.')
            self._difficulty=float(value); self._event(f'Dificultate pool: {self._difficulty:g}.')
        elif method=='mining.notify':
            meta=parse_notify(params)
            with self._lock:
                self._job={'params':params,'meta':meta,'received':time.monotonic(),'difficulty':self._difficulty}
                self._job_seq+=1; self._nonce=0; self._extranonce2=0
            self._event(f'Job nou: {meta["job_id"]}; clean={meta["clean_jobs"]}.')
        elif method=='mining.set_extranonce':
            if not isinstance(params,list) or len(params)<2: raise StratumMinerError('set_extranonce invalid.')
            ex1,size=params[:2]
            if not isinstance(ex1,str) or len(ex1)%2 or any(c not in '0123456789abcdefABCDEF' for c in ex1): raise StratumMinerError('extranonce1 invalid.')
            if isinstance(size,bool) or not isinstance(size,int) or not 1<=size<=16: raise StratumMinerError('extranonce2_size invalid.')
            self._extranonce1=ex1; self._extranonce2_size=size; self._extranonce2=0; self._nonce=0
            self._event('Pool-ul a rotit extranonce.')
        elif method=='client.show_message' and isinstance(params,list) and params:
            self._event('Pool: '+str(params[0])[:300])
        elif method=='client.reconnect':
            raise StratumMinerError('Pool-ul a solicitat reconnect; repornirea automată nu este activată în acest build.')

    def _make_extranonce2(self):
        assert self._extranonce2_size is not None
        if self._extranonce2 >= 1 << (8*self._extranonce2_size):
            raise StratumMinerError('Spațiul extranonce2 epuizat pentru conexiunea curentă.')
        return self._extranonce2.to_bytes(self._extranonce2_size,'big').hex()

    def _submit(self, job, nonce, extranonce2):
        submit_id=self._next_id; self._next_id+=1
        self._submitted+=1
        self._pending[submit_id]={'type':'share','seq':self._submitted,
                                  'nonce':f'{nonce:08x}','job_id':job['meta']['job_id'],'sent':time.monotonic()}
        self._send({'id':submit_id,'method':'mining.submit','params':[self.username,job['meta']['job_id'],extranonce2,job['meta']['ntime'],f'{nonce:08x}']})
        self._event(f'Share candidat trimis: job={job["meta"]["job_id"]}, nonce={nonce:08x}.')

    def _run(self):
        try:
            self._status='connecting'
            raw=socket.create_connection((self.host,self.port),timeout=self.timeout)
            if self.use_tls:
                context=ssl.create_default_context()
                self._sock=context.wrap_socket(raw,server_hostname=self.host)
            else: self._sock=raw
            self._connected=True; self._status='handshake'; self._event(f'Conectat la {self.host}:{self.port}'+(' TLS' if self.use_tls else ' TCP')+'.')
            self._pending[1]='subscribe'; self._pending[2]='authorize'
            self._send({'id':1,'method':'mining.subscribe','params':['NEXUS/0.10.14',None]})
            self._send({'id':2,'method':'mining.authorize','params':[self.username,self.password]})
            while not self._stop.is_set():
                for msg in self._read_messages(0.05): self._handle_message(msg)
                if not self._authorized or not self._job or self._difficulty is None or self._extranonce1 is None: continue
                job=self._job; seq=self._job_seq
                if job.get('difficulty') is None:
                    job['difficulty']=self._difficulty
                ex2=self._make_extranonce2()
                header=assemble_bitcoin_header(job['params'],self._extranonce1,ex2)
                share_target=difficulty_target(job['difficulty'])
                block_target=compact_target(job['meta']['nbits'])
                start=self._nonce
                count=min(self.scan_chunk,0x100000000-start)
                if count<=0:
                    self._extranonce2+=1; self._nonce=0; continue
                if self.prefer_native:
                    scanned=scan_nonce_range_optimized(header,start,count,share_target,block_target,
                                                       threads=self.native_threads,variant=self.native_variant)
                else:
                    scanned=scan_nonce_range(header,start,count,share_target,block_target)
                self._engine_name=str(scanned.get('engine', 'Python exact SHA-256d reference'))
                self._hashes+=int(scanned.get('checked',0)); self._hash_window+=int(scanned.get('checked',0))
                self._nonce=start+int(scanned.get('checked',0))
                if scanned['status']=='share_candidate':
                    if scanned.get('meets_block_target'):
                        self._event('CANDIDAT DE BLOC: hash-ul atinge target-ul de rețea; pool-ul decide validarea și propagarea.')
                    for incoming in self._read_messages(0.001): self._handle_message(incoming)
                    if seq==self._job_seq and not self._stop.is_set(): self._submit(job,scanned['nonce'],ex2)
                    self._nonce=scanned['nonce']+1
                if self._nonce>=0x100000000:
                    self._extranonce2+=1; self._nonce=0
                if time.monotonic()-self._window_start>=1.0:
                    self._window_rate=self._hash_window/(time.monotonic()-self._window_start)
                    self._hash_window=0; self._window_start=time.monotonic()
                # Expire unanswered share requests without counting them accepted/rejected.
                now=time.monotonic()
                for pid,pending in list(self._pending.items()):
                    if isinstance(pending,dict) and pending.get('type')=='share' and now-pending['sent']>20:
                        self._pending.pop(pid,None); self._event('Timeout răspuns mining.submit; share neconfirmat.')
                if seq!=self._job_seq: continue
            self._status='stopped'; self._exit_code=0; self.returncode=0
        except Exception as exc:
            if self._stop.is_set():
                self._status='stopped'; self._exit_code=0; self.returncode=0
            else:
                self._error=f'{type(exc).__name__}: {exc}'; self._status='error'; self._exit_code=1; self.returncode=1; self._event('EROARE: '+self._error)
        finally:
            self._connected=False
            try:
                if self._sock: self._sock.close()
            except OSError: pass
            self._sock=None
            if self._stop.is_set() and self._status!='error': self._status='stopped'; self._exit_code=0; self.returncode=0

    def metrics(self):
        with self._lock:
            elapsed=max(0.001,time.monotonic()-self._started)
            rate=getattr(self,'_window_rate',self._hashes/elapsed)
            return {'api_connected':self._connected,'hashrate_hs':round(rate,2),'hashrate_display':f'{rate:.2f} H/s',
                    'accepted_shares':self._accepted,'rejected_shares':self._rejected,'submitted_shares':self._submitted,
                    'hashes_scanned':self._hashes,'current_difficulty':self._difficulty,'job_id':self._job['meta']['job_id'] if self._job else None,
                    'worker_authorized':self._authorized,'last_share':self._last_share,'gpu':{},'system':{},
                    'engine':self._engine_name,'native_requested':self.prefer_native,
                    'native':native_status() if self.prefer_native else {'available':False,'reason':'native backend disabled'}}

    def status(self):
        return {'status':self._status,'connected':self._connected,'authorized':self._authorized,'error':self._error,
                'metrics':self.metrics(),'events':list(self._events),'uptime_seconds':round(time.time()-self._started,1)}
