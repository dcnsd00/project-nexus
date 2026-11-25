"""Bitcoin SHA-256d proof-of-work primitives for assembled Stratum jobs.

Scans caller-supplied nonce ranges only. Does not open sockets, submit shares,
or start miners. Network submission requires a separately authorized client.
"""
from __future__ import annotations
from dataclasses import dataclass
from modules.sha2_research_bridge import ExactBitcoinMidstate

class BitcoinPowError(ValueError): pass

def compact_target(nbits: str) -> int:
    if not isinstance(nbits, str) or len(nbits) != 8: raise BitcoinPowError("nbits trebuie să conțină 8 caractere hex.")
    try: compact=int(nbits,16)
    except ValueError as exc: raise BitcoinPowError("nbits invalid.") from exc
    exponent=compact >> 24; mantissa=compact & 0x007fffff
    if compact & 0x00800000 or mantissa == 0 or not 3 <= exponent <= 32: raise BitcoinPowError("Compact target invalid.")
    target=mantissa << (8*(exponent-3))
    if target <= 0 or target >= 1 << 256: raise BitcoinPowError("Target în afara uint256.")
    return target

def difficulty_target(difficulty: float) -> int:
    if isinstance(difficulty,bool) or not isinstance(difficulty,(int,float)) or difficulty <= 0: raise BitcoinPowError("Dificultatea Stratum trebuie să fie pozitivă.")
    return min((1 << 256)-1,max(1,int((0xffff * (1 << 208)) / float(difficulty))))

@dataclass(frozen=True)
class NonceResult:
    nonce: int; hash_internal_hex: str; hash_display_hex: str; hash_value: int
    meets_share_target: bool; meets_block_target: bool

def scan_nonce_range(header_template: bytes, start_nonce: int, count: int, share_target: int, block_target: int | None=None) -> dict:
    if not isinstance(header_template,bytes) or len(header_template)!=80: raise BitcoinPowError("Header-ul trebuie să aibă exact 80 bytes.")
    if isinstance(start_nonce,bool) or not isinstance(start_nonce,int) or not 0<=start_nonce<=0xffffffff: raise BitcoinPowError("start_nonce invalid.")
    if isinstance(count,bool) or not isinstance(count,int) or not 1<=count<=1_000_000: raise BitcoinPowError("count trebuie să fie între 1 și 1.000.000.")
    if isinstance(share_target,bool) or not isinstance(share_target,int) or not 0<share_target<1<<256: raise BitcoinPowError("share_target invalid.")
    if block_target is not None and (isinstance(block_target,bool) or not isinstance(block_target,int) or not 0<block_target<1<<256): raise BitcoinPowError("block_target invalid.")
    if block_target is not None and block_target>share_target: raise BitcoinPowError("block_target trebuie să fie mai dificil sau egal cu share_target (block_target <= share_target).")
    engine=ExactBitcoinMidstate(header_template); checked=0; best=None; first_share=None
    for nonce in range(start_nonce,min(0x100000000,start_nonce+count)):
        digest=engine.hash_nonce(nonce); value=int.from_bytes(digest[::-1],"big"); checked+=1
        meets_share=value<=share_target; meets_block=bool(block_target is not None and value<=block_target)
        if best is None or value<best.hash_value: best=NonceResult(nonce,digest.hex(),digest[::-1].hex(),value,meets_share,meets_block)
        if meets_block:
            return {"status":"share_candidate","checked":checked,"nonce":nonce,"hash_internal_hex":digest.hex(),"hash_display_hex":digest[::-1].hex(),"hash_value_hex":f"{value:064x}","meets_share_target":True,"meets_block_target":True,"engine":"exact_sha256d_midstate","reference_guard":"each nonce compared with hashlib"}
        if meets_share and first_share is None:
            first_share=(nonce,digest,value)
            if block_target is None:
                return {"status":"share_candidate","checked":checked,"nonce":nonce,"hash_internal_hex":digest.hex(),"hash_display_hex":digest[::-1].hex(),"hash_value_hex":f"{value:064x}","meets_share_target":True,"meets_block_target":False,"engine":"exact_sha256d_midstate","reference_guard":"each nonce compared with hashlib"}
    if first_share is not None:
        nonce,digest,value=first_share
        return {"status":"share_candidate","checked":checked,"nonce":nonce,"hash_internal_hex":digest.hex(),"hash_display_hex":digest[::-1].hex(),"hash_value_hex":f"{value:064x}","meets_share_target":True,"meets_block_target":False,"engine":"exact_sha256d_midstate","reference_guard":"each nonce compared with hashlib"}
    return {"status":"range_exhausted","checked":checked,"best_nonce":best.nonce if best else None,"best_hash_display_hex":best.hash_display_hex if best else None,"best_hash_value_hex":f"{best.hash_value:064x}" if best else None,"meets_share_target":False,"meets_block_target":False,"engine":"exact_sha256d_midstate","reference_guard":"each nonce compared with hashlib"}
