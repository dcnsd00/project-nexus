from __future__ import annotations
"""
NEXUS wallet format recovery primitives.
Only decrypts a local file/key supplied by the wallet owner with a password they provide.
No password brute force, network lookup, address targeting or transaction broadcast.
"""
import hashlib, hmac, json, unicodedata, base64, binascii
from typing import Iterable, Optional
from pathlib import Path
from urllib.parse import quote, urlparse
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from nexus_wallet_benchmark import (
    SECP256K1_N, keccak256, evm_address, base58check_decode,
    base58check, hash160, compressed_pubkey, private_to_public
)
from cryptography.hazmat.primitives import serialization

class WalletFormatError(ValueError): pass
class WalletPasswordError(ValueError): pass
class WalletIntegrityError(ValueError): pass
class RecoveryAuthorizationError(PermissionError): pass

def _require_owner(owner_authorized: bool):
    if owner_authorized is not True:
        raise RecoveryAuthorizationError("Explicit owner/authorized recovery confirmation is required")

def _hex(s, name, exact_len=None):
    if not isinstance(s, str):
        raise WalletFormatError(f"{name} must be hex text")
    try:
        b=bytes.fromhex(s)
    except ValueError:
        raise WalletFormatError(f"{name} is not valid hex")
    if exact_len is not None and len(b)!=exact_len:
        raise WalletFormatError(f"{name} must be {exact_len} bytes")
    return b

def detect_wallet_format(value):
    """Best-effort local format detection; never reads a blockchain address to find credentials."""
    if isinstance(value, str):
        if value.startswith("6P") and len(value)==58:
            return {"format":"BIP38_NON_EC_OR_EC","decryption":"passphrase_required","scope":"local encrypted private-key string"}
        if value.lower().startswith("0x") and len(value)==66:
            return {"format":"EVM_PRIVATE_KEY_HEX","decryption":"not_encrypted","scope":"sensitive raw key; do not upload"}
        return {"format":"UNKNOWN_TEXT","decryption":"unsupported"}
    if isinstance(value, dict):
        crypto=value.get("crypto")
        if crypto is None: crypto=value.get("Crypto")
        if value.get("version")==3 and isinstance(crypto,dict):
            return {"format":"WEB3_SECRET_STORAGE_V3","decryption":"password_required","scope":"Ethereum-compatible JSON keystore"}
        if value.get("version")==1 and value.get("kdf")=="scrypt-n32768-r8-p1":
            return {"format":"NEXUS_AESGCM_V1","decryption":"password_required","scope":"NEXUS local keystore"}
        nested=value.get("keystore")
        if isinstance(nested,dict) and nested.get("v")==1 and nested.get("kdf")=="scrypt-n32768-r8-p1":
            return {"format":"NEXUS_AESGCM_V1","decryption":"password_required","scope":"NEXUS encrypted recovery export"}
        if "wallet_type" in value or "keystore" in value and "seed_version" in value:
            return {"format":"ELECTRUM_WALLET","decryption":"use_official_electrum","scope":"native encrypted wallet file"}
        return {"format":"UNKNOWN_JSON","decryption":"unsupported"}
    if isinstance(value, list) and len(value) in (64,):
        if all(isinstance(x,int) and 0<=x<=255 for x in value):
            return {"format":"SOLANA_KEYPAIR_JSON","decryption":"not_encrypted_by_default","scope":"64-byte keypair file"}
    return {"format":"UNKNOWN","decryption":"unsupported"}

def decrypt_web3_v3(keystore: dict, password: str, owner_authorized: bool=False) -> dict:
    """
    Decrypt Ethereum Web3 Secret Storage v3 JSON (scrypt or PBKDF2 + AES-128-CTR).
    Returns metadata and key bytes in memory; callers must never log or expose key bytes.
    """
    _require_owner(owner_authorized)
    if not isinstance(keystore,dict) or keystore.get("version")!=3:
        raise WalletFormatError("Not a Web3 Secret Storage v3 keystore")
    c=keystore.get("crypto") or keystore.get("Crypto")
    if not isinstance(c,dict): raise WalletFormatError("Missing crypto object")
    if c.get("cipher")!="aes-128-ctr": raise WalletFormatError("Unsupported cipher; AES-128-CTR required")
    cp=c.get("cipherparams") or {}
    iv=_hex(cp.get("iv"),"cipher IV",16)
    ct=_hex(c.get("ciphertext"),"ciphertext")
    if not ct or len(ct)>4096: raise WalletFormatError("Ciphertext size out of range")
    mac=_hex(c.get("mac"),"MAC",32)
    kdf=str(c.get("kdf","")).lower()
    kp=c.get("kdfparams") or {}
    try: dklen=int(kp.get("dklen"))
    except Exception: raise WalletFormatError("Invalid KDF output length")
    if not 32 <= dklen <= 64: raise WalletFormatError("KDF dklen must be 32..64")
    salt=_hex(kp.get("salt"),"KDF salt")
    if not 16 <= len(salt) <= 64: raise WalletFormatError("KDF salt length out of bounds")
    pwd=password.encode("utf-8")
    if not pwd or len(pwd)>1024: raise WalletPasswordError("Password missing or too long")
    try:
        if kdf=="scrypt":
            n,r,p=int(kp["n"]),int(kp["r"]),int(kp["p"])
            if n < 2**10 or n > 2**18 or n & (n-1) or not 1<=r<=16 or not 1<=p<=4:
                raise WalletFormatError("Scrypt parameters outside NEXUS safety limits (10<=log2(N)<=18, r<=16, p<=4)")
            derived=hashlib.scrypt(pwd,salt=salt,n=n,r=r,p=p,dklen=dklen,maxmem=512*1024*1024)
        elif kdf=="pbkdf2":
            c_iter=int(kp["c"])
            prf=kp.get("prf","")
            if prf!="hmac-sha256" or not 1<=c_iter<=10_000_000:
                raise WalletFormatError("Unsupported PBKDF2 PRF or iteration count")
            derived=hashlib.pbkdf2_hmac("sha256",pwd,salt,c_iter,dklen)
        else:
            raise WalletFormatError("Unsupported Web3 KDF")
    except (KeyError,TypeError,ValueError) as e:
        if isinstance(e,WalletFormatError): raise
        raise WalletFormatError("Malformed KDF parameters") from e
    expected=keccak256(derived[16:32]+ct)
    if not hmac.compare_digest(expected,mac):
        raise WalletPasswordError("Password incorrect or keystore integrity check failed")
    decryptor=Cipher(algorithms.AES(derived[:16]),modes.CTR(iv)).decryptor()
    secret=decryptor.update(ct)+decryptor.finalize()
    if len(secret)!=32:
        raise WalletIntegrityError("Decrypted EVM key must be exactly 32 bytes")
    scalar=int.from_bytes(secret,"big")
    if not 1<=scalar<SECP256K1_N: raise WalletIntegrityError("Decrypted key outside secp256k1 range")
    address=evm_address(scalar)
    expected_addr=keystore.get("address")
    if expected_addr:
        expected_addr=str(expected_addr)
        if not expected_addr.startswith("0x"): expected_addr="0x"+expected_addr
        if address.lower()!=expected_addr.lower():
            raise WalletIntegrityError("Decrypted key does not match keystore address field")
    return {"format":"WEB3_SECRET_STORAGE_V3","decrypted":True,"address":address,
            "private_key":secret,"kdf":kdf,"cipher":"aes-128-ctr","integrity_verified":True}

def _p2pkh_address(secret: bytes, compressed: bool) -> str:
    scalar=int.from_bytes(secret,"big")
    pub=private_to_public(scalar)
    if compressed:
        pub_bytes=pub.public_bytes(serialization.Encoding.X962,serialization.PublicFormat.CompressedPoint)
    else:
        pub_bytes=pub.public_bytes(serialization.Encoding.X962,serialization.PublicFormat.UncompressedPoint)
    return base58check(b"\x00"+hash160(pub_bytes))

def decrypt_bip38_non_ec(encrypted: str, passphrase: str, owner_authorized: bool=False) -> dict:
    """Decrypt BIP38 0x0142 non-EC-multiplied key using owner-provided passphrase."""
    _require_owner(owner_authorized)
    try: payload=base58check_decode(encrypted)
    except Exception as e: raise WalletFormatError("Invalid BIP38 Base58Check string") from e
    if len(payload)!=39 or payload[:2]!=b"\x01\x42":
        raise WalletFormatError("Only BIP38 non-EC-multiplied 0x0142 keys are supported")
    flag=payload[2]
    if flag not in (0xC0,0xE0): raise WalletFormatError("Unsupported or reserved BIP38 flag")
    compressed=(flag==0xE0)
    address_hash=payload[3:7]
    if len(passphrase.encode("utf-8"))>256: raise WalletPasswordError("Passphrase too long")
    norm=unicodedata.normalize("NFC",passphrase).encode("utf-8")
    derived=hashlib.scrypt(norm,salt=address_hash,n=16384,r=8,p=8,dklen=64,maxmem=128*1024*1024)
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    dec=Cipher(algorithms.AES(derived[32:64]),modes.ECB()).decryptor()
    first=dec.update(payload[7:23]); second=dec.update(payload[23:39]); dec.finalize()
    secret=bytes(a^b for a,b in zip(first+second,derived[:32]))
    scalar=int.from_bytes(secret,"big")
    if not 1<=scalar<SECP256K1_N: raise WalletIntegrityError("BIP38 decrypted key outside secp256k1 range")
    address=_p2pkh_address(secret,compressed)
    actual=hashlib.sha256(hashlib.sha256(address.encode("ascii")).digest()).digest()[:4]
    if not hmac.compare_digest(actual,address_hash):
        raise WalletPasswordError("BIP38 passphrase incorrect or address checksum mismatch")
    wif_payload=b"\x80"+secret+(b"\x01" if compressed else b"")
    wif=base58check(wif_payload)
    return {"format":"BIP38_NON_EC","decrypted":True,"address":address,
            "compressed":compressed,"wif":wif,"private_key":secret,
            "address_hash_verified":True}

def bip39_validate(phrase: str, wordlist: Iterable[str]) -> dict:
    words=unicodedata.normalize("NFKD",phrase).strip().split()
    wl=list(wordlist)
    if len(wl)!=2048 or len(set(wl))!=2048:
        raise WalletFormatError("BIP39 wordlist must contain 2048 unique words")
    if len(words) not in (12,15,18,21,24):
        return {"valid":False,"reason":"word_count"}
    index={w:i for i,w in enumerate(wl)}
    try: values=[index[w] for w in words]
    except KeyError as e: return {"valid":False,"reason":"unknown_word","unknown":str(e.args[0])}
    total_bits=len(values)*11
    bits="".join(f"{v:011b}" for v in values)
    ent_len=total_bits*32//33
    cs_len=total_bits-ent_len
    entropy=int(bits[:ent_len],2).to_bytes(ent_len//8,"big")
    checksum=bits[ent_len:]
    expected=bin(int.from_bytes(hashlib.sha256(entropy).digest(),"big"))[2:].zfill(256)[:cs_len]
    return {"valid":hmac.compare_digest(checksum,expected),"reason":"ok" if checksum==expected else "checksum",
            "word_count":len(words),"entropy_bits":ent_len}

def bip39_find_one_missing_word(partial_phrase: str, wordlist: Iterable[str],
                                owner_authorized: bool=False, max_candidates: int=2048) -> list[str]:
    """Recover one missing BIP39 word from an owner-provided backup; checksum-filter only."""
    _require_owner(owner_authorized)
    words=unicodedata.normalize("NFKD",partial_phrase).strip().split()
    if words.count("?")!=1: raise WalletFormatError("Exactly one '?' missing-word marker is required")
    if len(words) not in (12,15,18,21,24): raise WalletFormatError("Unsupported mnemonic word count")
    wl=list(wordlist)
    if len(wl)!=2048 or len(set(wl))!=2048: raise WalletFormatError("BIP39 wordlist must contain 2048 unique words")
    if not 1<=max_candidates<=2048: raise WalletFormatError("max_candidates must be 1..2048")
    pos=words.index("?"); found=[]
    for candidate in wl[:max_candidates]:
        trial=words.copy(); trial[pos]=candidate
        result=bip39_validate(" ".join(trial),wl)
        if result["valid"]: found.append(" ".join(trial))
    return found

def verify_bip39_passphrase(phrase: str, passphrase: str, wordlist: Iterable[str],
                            owner_authorized: bool=False) -> bytes:
    _require_owner(owner_authorized)
    valid=bip39_validate(phrase,wordlist)
    if not valid["valid"]: raise WalletIntegrityError("Mnemonic is not a valid BIP39 phrase")
    # BIP39 passphrase does not have a validity checksum: every passphrase derives a valid, different seed.
    from nexus_wallet_benchmark import bip39_seed
    return bip39_seed(phrase,passphrase)

def detect_keyfile(path):
    """Conservative filename hint only; a filename never proves a wallet format."""
    item = Path(path)
    name = item.name.lower()
    suffix = item.suffix.lower()
    if name == "wallet.dat":
        return {"format": "BITCOIN_CORE_WALLET_CANDIDATE", "method": "filename hint only; verify by loading in local Bitcoin Core"}
    if suffix == ".dat":
        return {"format": "UNKNOWN_FILE", "method": "generic .dat file; format not confirmed"}
    if suffix == ".keys":
        return {"format": "MONERO_KEYS_CANDIDATE", "method": "filename extension only; verify with official Monero wallet software"}
    if "electrum" in str(item).lower() or suffix == ".wallet":
        return {"format": "ELECTRUM_WALLET_CANDIDATE", "method": "filename/path hint only; verify with Electrum"}
    if suffix == ".json" or name == "keystore":
        return {"format": "JSON_KEYSTORE_CANDIDATE", "method": "inspect JSON structure locally"}
    return {"format": "UNKNOWN_FILE", "method": "format not confirmed; no password guessing"}


def load_bip39_wordlist(language: str="english") -> list[str]:
    """Load an official wordlist from the Trezor python-mnemonic distribution."""
    try:
        from mnemonic import Mnemonic
    except ImportError as e:
        raise WalletFormatError("Install the 'mnemonic' package to load official BIP39 wordlists") from e
    try:
        instance=Mnemonic(language)
        words=list(instance.wordlist)
    except Exception as e:
        raise WalletFormatError(f"Unsupported BIP39 language: {language}") from e
    if len(words)!=2048 or len(set(words))!=2048:
        raise WalletIntegrityError("Installed BIP39 wordlist failed integrity checks")
    return words

def validate_solana_keypair(secret_array: list[int]) -> dict:
    """Validate a standard Solana 64-byte JSON keypair; this format is not password-encrypted."""
    if not isinstance(secret_array,list) or len(secret_array)!=64:
        raise WalletFormatError("Solana keypair JSON must be an array of 64 bytes")
    if any(not isinstance(x,int) or isinstance(x,bool) or not 0<=x<=255 for x in secret_array):
        raise WalletFormatError("Solana keypair contains invalid byte values")
    raw=bytes(secret_array)
    try:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
        from cryptography.hazmat.primitives import serialization
        pub=Ed25519PrivateKey.from_private_bytes(raw[:32]).public_key().public_bytes(
            serialization.Encoding.Raw,serialization.PublicFormat.Raw)
    except Exception as e:
        raise WalletIntegrityError("Invalid Solana Ed25519 secret seed") from e
    if not hmac.compare_digest(pub,raw[32:]):
        raise WalletIntegrityError("Solana keypair public half does not match its private seed")
    # Base58 encode the public key using the wallet benchmark primitive.
    from nexus_wallet_benchmark import base58_encode
    return {"format":"SOLANA_KEYPAIR_JSON","valid":True,"address":base58_encode(pub),
            "encrypted":False,"private_key_returned":False}

def bitcoin_core_check_wallet_passphrase(
    rpc_url: str, username: str, rpc_password: str, wallet_name: str,
    wallet_passphrase: str, owner_authorized: bool=False, timeout: float=5.0
) -> dict:
    """
    Verify an owner-supplied Bitcoin Core wallet passphrase through a loopback-only RPC.
    Unlock interval is one second and walletlock is called immediately after verification.
    No address scan, transaction signing or broadcast is performed.
    """
    _require_owner(owner_authorized)
    parsed=urlparse(rpc_url)
    if parsed.scheme!="http" or parsed.hostname not in ("127.0.0.1","localhost","::1"):
        raise WalletFormatError("Bitcoin Core RPC must use local HTTP on loopback only")
    if not (1<=parsed.port<=65535): raise WalletFormatError("Invalid Bitcoin Core RPC port")
    if not wallet_name or "/" in wallet_name or ".." in wallet_name:
        raise WalletFormatError("Invalid local wallet name")
    if not wallet_passphrase: raise WalletPasswordError("Wallet passphrase required")
    endpoint=rpc_url.rstrip("/")+"/wallet/"+quote(wallet_name,safe="")
    import base64
    auth=base64.b64encode(f"{username}:{rpc_password}".encode()).decode()
    def call(method,params):
        body=json.dumps({"jsonrpc":"1.0","id":"nexus-recovery","method":method,"params":params}).encode()
        req=Request(endpoint,data=body,headers={"Authorization":"Basic "+auth,"Content-Type":"application/json"})
        try:
            with urlopen(req,timeout=timeout) as response:
                payload=json.loads(response.read(1_000_000))
        except (URLError,HTTPError,TimeoutError) as e:
            raise WalletFormatError("Cannot reach the local Bitcoin Core RPC") from e
        if payload.get("error"):
            raise WalletPasswordError(str(payload["error"].get("message","RPC error")))
        return payload.get("result")
    call("walletpassphrase",[wallet_passphrase,1])
    try:
        call("walletlock",[])
    except Exception as exc:
        raise WalletFormatError("Password verified, but Bitcoin Core could not relock the wallet; run walletlock manually") from exc
    return {"format":"BITCOIN_CORE_WALLET_DAT","password_verified":True,
            "wallet_name":wallet_name,"currently_unlocked":False,
            "wallet_relocked_after_check":True,"unlock_interval_seconds":1,
            "transaction_broadcast":False}


def bitcoin_core_inspect_wallet(
    rpc_url: str, username: str, rpc_password: str, wallet_name: str,
    owner_authorized: bool=False, timeout: float=5.0, max_transactions: int=10000,
    now_ts: Optional[float]=None,
) -> dict:
    """Read-only inspection of an explicitly loaded owner-authorized Bitcoin Core wallet.

    Returns balances, public addresses, transaction metadata and inactivity age.
    It never reads private keys, unlocks the wallet, signs, prepares or broadcasts a tx.
    RPC is restricted to loopback to avoid sending credentials to a remote host.
    """
    _require_owner(owner_authorized)
    parsed=urlparse(rpc_url)
    if parsed.scheme!="http" or parsed.hostname not in ("127.0.0.1","localhost","::1"):
        raise WalletFormatError("Bitcoin Core RPC must use local HTTP on loopback only")
    if not parsed.port or not (1<=parsed.port<=65535):
        raise WalletFormatError("Invalid Bitcoin Core RPC port")
    if not wallet_name or len(wallet_name)>128 or "/" in wallet_name or ".." in wallet_name:
        raise WalletFormatError("Invalid local wallet name")
    if not 1<=max_transactions<=10000:
        raise WalletFormatError("max_transactions must be 1..10000")

    import time as _time
    import base64 as _base64
    from decimal import Decimal, InvalidOperation
    endpoint=rpc_url.rstrip("/")+"/wallet/"+quote(wallet_name,safe="")
    auth=_base64.b64encode(f"{username}:{rpc_password}".encode()).decode()

    def call(method,params=None,optional=False):
        body=json.dumps({"jsonrpc":"1.0","id":"nexus-readonly-inspect",
                         "method":method,"params":params or []}).encode()
        req=Request(endpoint,data=body,headers={
            "Authorization":"Basic "+auth,"Content-Type":"application/json"})
        try:
            with urlopen(req,timeout=timeout) as response:
                payload=json.loads(response.read(2_000_000))
        except (URLError,HTTPError,TimeoutError, OSError, json.JSONDecodeError) as exc:
            if optional:
                return None
            raise WalletFormatError("Cannot reach the local Bitcoin Core wallet RPC") from exc
        error=payload.get("error")
        if error:
            if optional:
                return None
            message=str(error.get("message","RPC error")) if isinstance(error,dict) else "RPC error"
            raise WalletFormatError(f"Bitcoin Core {method} failed: {message[:160]}")
        return payload.get("result")

    info=call("getwalletinfo")
    balances=call("getbalances",optional=True)
    legacy_balance=call("getbalance",["*",0,True],optional=True) if balances is None else None
    groupings=call("listaddressgroupings",optional=True) or []

    transactions=[]
    truncated=False
    page_size=1000
    offset=0
    while len(transactions)<max_transactions:
        requested=min(page_size,max_transactions-len(transactions))
        batch=call("listtransactions",["*",requested,offset,True])
        if not isinstance(batch,list):
            raise WalletFormatError("Bitcoin Core returned an invalid transaction history")
        transactions.extend(x for x in batch if isinstance(x,dict))
        offset += len(batch)
        if len(batch)<requested:
            break
    if len(transactions)>=max_transactions:
        truncated=True

    def money(value):
        try:
            return format(Decimal(str(value)),"f")
        except (InvalidOperation, ValueError, TypeError):
            return None

    now=float(now_ts if now_ts is not None else _time.time())
    dated=[]
    for tx in transactions:
        stamp=tx.get("time",tx.get("timereceived"))
        try:
            stamp=int(stamp)
            if stamp>0:
                dated.append((stamp,tx))
        except (TypeError,ValueError):
            continue
    latest=max(dated,key=lambda item:item[0]) if dated else None
    if latest:
        inactivity_seconds=max(0.0,now-latest[0])
        inactivity_days=int(inactivity_seconds//86400)
        inactivity_years=inactivity_seconds/(365.2425*86400)
        if inactivity_years>=10:
            activity="INACTIVE_10_PLUS_YEARS"
        elif inactivity_years>=8:
            activity="INACTIVE_8_TO_10_YEARS"
        else:
            activity="ACTIVE_WITHIN_8_YEARS"
        last_ts=latest[0]
    else:
        inactivity_days=None; inactivity_years=None; activity="NO_TRANSACTION_HISTORY"; last_ts=None

    addresses=[]
    for group in groupings if isinstance(groupings,list) else []:
        if not isinstance(group,list):
            continue
        for item in group:
            if isinstance(item,list) and item and isinstance(item[0],str):
                addresses.append({"address":item[0],"balance_btc":money(item[1]) if len(item)>1 else None,
                                  "label":item[2] if len(item)>2 and isinstance(item[2],str) else None})
                if len(addresses)>=500:
                    break
        if len(addresses)>=500:
            break

    tx_summary=[]
    for stamp,tx in sorted(dated,key=lambda item:item[0],reverse=True)[:50]:
        tx_summary.append({
            "txid":tx.get("txid"), "time":stamp,
            "category":tx.get("category"), "amount_btc":money(tx.get("amount")),
            "confirmations":tx.get("confirmations"), "address":tx.get("address")
        })

    if isinstance(balances,dict):
        mine=balances.get("mine",{}) if isinstance(balances.get("mine",{}),dict) else {}
        balance_data={key:money(mine.get(key)) for key in ("trusted","untrusted_pending","immature")}
    else:
        balance_data={"trusted":money(legacy_balance),"untrusted_pending":None,"immature":None}

    return {
        "format":"BITCOIN_CORE_WALLET_DAT", "inspection":"READ_ONLY",
        "wallet_name":info.get("walletname",wallet_name),
        "wallet_version":info.get("walletversion"),
        "descriptors":info.get("descriptors"),
        "private_keys_enabled":info.get("private_keys_enabled"),
        "tx_count_reported":info.get("txcount",len(transactions)),
        "transactions_retrieved":len(transactions), "history_truncated":truncated,
        "balances_btc":balance_data,
        "address_count_returned":len(addresses), "addresses":addresses,
        "last_transaction_at":last_ts,
        "inactive_days":inactivity_days, "inactive_years":round(inactivity_years,3) if inactivity_years is not None else None,
        "activity_classification":activity,
        "recent_transactions":tx_summary,
        "history_completeness_note":"History reflects only the currently loaded Bitcoin Core wallet. An old backup may require a rescan/reindex before absence of transactions can be treated as conclusive.",
        "activity_is_wallet_history_only":True,
        "rescan_required_to_confirm_no_history":True,
        "file_age_is_not_chain_inactivity":True,
        "private_keys_returned":False, "private_keys_read":False, "wallet_unlocked":False,
        "transaction_prepared":False, "transaction_signed":False, "transaction_broadcast":False
    }

WALLET_COMPATIBILITY = {
 "NEXUS_LOCAL_AESGCM_V1":"direct decrypt tested",
 "ETHEREUM_WEB3_SECRET_STORAGE_V3":"direct decrypt for scrypt/PBKDF2 + AES-128-CTR; tested",
 "BITCOIN_BIP38_0142":"direct decrypt for non-EC-multiplied keys; tested",
 "BIP39_MNEMONIC":"checksum/seed derivation; official wordlist loaded via python-mnemonic; single missing word checksum filter",
 "BITCOIN_CORE_WALLET_DAT":"local Bitcoin Core RPC passphrase verification; local daemon required",
 "ELECTRUM_WALLET":"use official Electrum GUI/CLI; native ECIES/AES encryption not decoded by NEXUS yet",
 "METAMASK_BROWSER_VAULT":"use MetaMask-supported local vault recovery process; raw browser vault versions not decoded by NEXUS",
 "MONERO_WALLET_FILE":"use official Monero CLI/GUI; mnemonic/keys restoration supported by vendor tools, not raw file decryption by NEXUS",
 "SOLANA_KEYPAIR_JSON":"validate standard 64-byte Ed25519 keypair; generally not password encrypted",
 "BIP38_0143_EC_MULTIPLY":"not yet implemented",
 "EIP2335_BLS_KEYSTORE":"not yet implemented"
}


def bip39_recover_one_missing_by_address(
    partial_phrase: str, wordlist: Iterable[str], expected_address: str,
    format_name: str, passphrase: str="", address_index: int=0,
    owner_authorized: bool=False
) -> list[dict]:
    """
    Recover one missing mnemonic word by BIP39 checksum + matching an owner-provided
    known address under one explicitly selected derivation format/path.
    This does not search password dictionaries or scan arbitrary addresses.
    """
    _require_owner(owner_authorized)
    from nexus_wallet_benchmark import (
        bip39_seed, derive_path, make_path, bitcoin_address, evm_address, FORMATS
    )
    if format_name not in FORMATS:
        raise WalletFormatError("Unsupported derivation format")
    if not isinstance(expected_address,str) or not expected_address:
        raise WalletFormatError("Expected public address is required")
    words=unicodedata.normalize("NFKD",partial_phrase).strip().split()
    if words.count("?")!=1: raise WalletFormatError("Exactly one missing-word marker '?' is required")
    if len(words) not in (12,15,18,21,24): raise WalletFormatError("Invalid mnemonic word count")
    wl=list(wordlist)
    if len(wl)!=2048 or len(set(wl))!=2048: raise WalletFormatError("BIP39 wordlist must contain 2048 unique words")
    if not 0<=address_index<=1_000_000: raise WalletFormatError("Address index out of bounds")
    path=make_path(format_name,address_index)
    pos=words.index("?")
    matches=[]
    for candidate in wl:
        trial=words.copy(); trial[pos]=candidate
        phrase=" ".join(trial)
        if not bip39_validate(phrase,wl)["valid"]: continue
        seed=bip39_seed(phrase,passphrase)
        key=derive_path(seed,path)
        if format_name=="EVM_ETHEREUM":
            address=evm_address(key)
        else:
            address=bitcoin_address(format_name,key)
        equal=(address.lower()==expected_address.lower())
        if equal:
            matches.append({"recovered_word":candidate,"mnemonic":phrase,
                            "address":address,"format":format_name,"path":path})
    return matches
