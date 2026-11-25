"""NEXUS Bitcoin Core RPC solo miner for local regtest/signet nodes.

Safety: loopback RPC only, regtest by default, bounded nonce attempts, empty
mempool templates only. It never accepts private keys; payout script is public.
"""
from __future__ import annotations
import base64, hashlib, json, os, struct, time, urllib.request
from pathlib import Path
from typing import Any

class SoloRPCError(RuntimeError): pass

def sha256d(data: bytes) -> bytes:
    return hashlib.sha256(hashlib.sha256(data).digest()).digest()

def varint(n: int) -> bytes:
    if n < 0xfd: return bytes([n])
    if n <= 0xffff: return b'\xfd' + struct.pack('<H', n)
    if n <= 0xffffffff: return b'\xfe' + struct.pack('<I', n)
    return b'\xff' + struct.pack('<Q', n)

def push_data(b: bytes) -> bytes:
    if len(b) < 76: return bytes([len(b)]) + b
    if len(b) <= 255: return b'\x4c' + bytes([len(b)]) + b
    raise SoloRPCError('Coinbase script prea mare')

def script_num(n: int) -> bytes:
    if n == 0: return b''
    out=bytearray()
    while n:
        out.append(n & 0xff); n >>= 8
    if out[-1] & 0x80: out.append(0)
    return bytes(out)

def coinbase_tx(height: int, value: int, payout_script: bytes, extra_nonce: bytes=b'NEXUS') -> bytes:
    if not payout_script or len(payout_script)>10000: raise SoloRPCError('Payout script invalid')
    height_push=push_data(script_num(height))
    sig=(height_push + push_data(extra_nonce))[:100]
    tx=(struct.pack('<i',2)+varint(1)+b'\x00'*32+struct.pack('<I',0xffffffff)+varint(len(sig))+sig+
        struct.pack('<I',0xffffffff)+varint(1)+struct.pack('<Q',value)+varint(len(payout_script))+payout_script+struct.pack('<I',0))
    return tx

class BitcoinRPC:
    def __init__(self, url='http://127.0.0.1:18443', username=None, password=None, cookie_file=None, timeout=5):
        self.url=url; self.username=username; self.password=password; self.cookie_file=Path(cookie_file).expanduser() if cookie_file else None; self.timeout=timeout
        from urllib.parse import urlparse
        parsed=urlparse(url)
        if parsed.scheme!='http' or parsed.hostname not in ('127.0.0.1','localhost','::1'):
            raise SoloRPCError('RPC permis numai pe loopback HTTP; nu expune credentialele pe rețea.')
        if not self.cookie_file and (not username or not password): raise SoloRPCError('Configurează RPC cookie sau user/parolă.')
    def call(self, method: str, params: list|None=None):
        if self.cookie_file:
            try: auth=self.cookie_file.read_text().strip()
            except OSError as e: raise SoloRPCError(f'RPC cookie indisponibil: {e}')
        else: auth=f'{self.username}:{self.password}'
        token=base64.b64encode(auth.encode()).decode()
        body=json.dumps({'jsonrpc':'1.0','id':'nexus','method':method,'params':params or []}).encode()
        req=urllib.request.Request(self.url,body,{'Authorization':'Basic '+token,'Content-Type':'application/json'})
        try:
            with urllib.request.urlopen(req,timeout=self.timeout) as resp: payload=json.loads(resp.read())
        except Exception as e: raise SoloRPCError(f'RPC {method} failed: {type(e).__name__}: {e}')
        if payload.get('error'): raise SoloRPCError(f'RPC {method}: {payload["error"]}')
        return payload.get('result')

def _compact_target(bits_hex: str) -> int:
    bits=int(bits_hex,16); exponent=bits >> 24; mantissa=bits & 0x007fffff
    return mantissa << (8*(exponent-3)) if exponent>=3 else mantissa >> (8*(3-exponent))

def benchmark_sha256d(iterations: int=200000) -> dict:
    iterations=max(1000,min(int(iterations),2_000_000)); header=bytes(80); start=time.perf_counter(); digest=header
    for i in range(iterations):
        digest=sha256d(header[:76]+struct.pack('<I',i & 0xffffffff))
    elapsed=time.perf_counter()-start
    return {'algorithm':'SHA-256d','iterations':iterations,'elapsed_seconds':round(elapsed,6),'hashrate_hs':round(iterations/elapsed,2),'last_digest':digest[::-1].hex(),'scope':'CPU header-hash microbenchmark; not GPU miner hashrate'}

def mine_regtest_block(rpc: BitcoinRPC, payout_script_hex: str, max_nonce_attempts: int=5_000_000) -> dict:
    max_nonce_attempts=max(1,min(int(max_nonce_attempts),20_000_000))
    try: network=rpc.call('getblockchaininfo')
    except Exception as e: raise SoloRPCError(f'Nu pot verifica rețeaua nodului: {e}')
    chain=network.get('chain')
    if chain!='regtest': raise SoloRPCError(f'Mining RPC activ numai pe regtest. Rețea detectată: {chain!r}')
    try: payout=bytes.fromhex(payout_script_hex)
    except ValueError: raise SoloRPCError('Payout script trebuie să fie hex valid.')
    if not payout: raise SoloRPCError('Payout script gol.')
    tpl=rpc.call('getblocktemplate',[{'rules':['segwit']}])
    txs=tpl.get('transactions') or []
    if txs: raise SoloRPCError('Template conține tranzacții; versiunea curentă acceptă numai mempool gol pentru a garanta construirea corectă a merkle/witness commitment.')
    cb=coinbase_tx(int(tpl['height']),int(tpl['coinbasevalue']),payout)
    merkle=sha256d(cb)
    version=int(tpl['version']); prev=bytes.fromhex(tpl['previousblockhash'])[::-1]
    ntime=int(tpl.get('curtime',int(time.time()))); bits=str(tpl['bits']); target=_compact_target(bits)
    prefix=struct.pack('<I',version)+prev+merkle+struct.pack('<I',ntime)+bytes.fromhex(bits)[::-1]
    start=time.perf_counter(); found=None; tested=0
    for nonce in range(max_nonce_attempts):
        tested+=1; digest=sha256d(prefix+struct.pack('<I',nonce))
        if int.from_bytes(digest,'little') <= target:
            found=nonce; break
    elapsed=time.perf_counter()-start
    result={'network':'regtest','height':int(tpl['height']),'nonce_attempts':tested,'elapsed_seconds':round(elapsed,6),'hashrate_hs':round(tested/elapsed,2) if elapsed else None,'target_bits':bits,'block_found':found is not None}
    if found is None: result['submitted']=False; result['reason']='Nonce budget epuizat; rulează din nou pentru un template nou.'; return result
    block=(prefix+struct.pack('<I',found)+varint(1)+cb).hex()
    submit=rpc.call('submitblock',[block])
    result.update({'nonce':found,'block_hash':sha256d(prefix+struct.pack('<I',found))[::-1].hex(),'submitted':submit is None,'submit_result':submit})
    return result
