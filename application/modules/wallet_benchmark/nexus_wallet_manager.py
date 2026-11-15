from __future__ import annotations
import base64, hashlib, json, os, secrets, sqlite3, time
from contextlib import contextmanager
from pathlib import Path
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.asymmetric import ec
from nexus_wallet_benchmark import SECP256K1_N, evm_address, validate_address

router = APIRouter(prefix="/api/wallet", tags=["wallet"])
DB = Path(os.getenv("NEXUS_WALLET_DB", "./data/nexus_wallets.db"))
NETWORKS = {"ETHEREUM","BASE","BNB","POLYGON","ARBITRUM"}
@contextmanager
def db():
    DB.parent.mkdir(parents=True, exist_ok=True)
    c=sqlite3.connect(DB, timeout=15); c.row_factory=sqlite3.Row
    try:
        c.execute("PRAGMA journal_mode=DELETE")
        c.execute("""CREATE TABLE IF NOT EXISTS vaults(
          id TEXT PRIMARY KEY,label TEXT NOT NULL,address TEXT NOT NULL,
          keystore TEXT NOT NULL,created REAL NOT NULL)""")
        c.execute("""CREATE TABLE IF NOT EXISTS watch_addresses(
          id TEXT PRIMARY KEY,label TEXT NOT NULL,network TEXT NOT NULL,
          address TEXT NOT NULL,created REAL NOT NULL,
          UNIQUE(network,address))""")
        c.execute("""CREATE TABLE IF NOT EXISTS bitcoin_vaults(
          id TEXT PRIMARY KEY,label TEXT NOT NULL,address TEXT NOT NULL UNIQUE,
          compressed INTEGER NOT NULL,keystore TEXT NOT NULL,created REAL NOT NULL)""")
        c.commit()
        yield c
        c.commit()
    except Exception:
        c.rollback()
        raise
    finally:
        c.close()


def initialize_schema() -> dict:
    """Create/upgrade wallet tables without decrypting or rewriting vault records."""
    with db() as c:
        tables = {r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    return {"status": "ok", "tables": sorted(tables),
            "bitcoin_vault_table_present": "bitcoin_vaults" in tables}


class CreateVault(BaseModel):
    label: str = Field(default="NEXUS EVM Wallet", min_length=1, max_length=64)
    password: str = Field(min_length=12, max_length=256)
class UnlockVault(BaseModel):
    wallet_id: str
    password: str = Field(min_length=12, max_length=256)
class WatchAddress(BaseModel):
    label: str = Field(min_length=1, max_length=64)
    network: str
    address: str

class UnlockBitcoinVault(BaseModel):
    wallet_id: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=12, max_length=256)

def _derive_key(password: str, salt: bytes) -> bytes:
    return hashlib.scrypt(password.encode("utf-8"), salt=salt, n=2**15, r=8, p=1, dklen=32, maxmem=128*1024*1024)

def _encrypt_secret(secret: bytes, password: str) -> str:
    salt=os.urandom(16); nonce=os.urandom(12); key=_derive_key(password,salt)
    cipher=AESGCM(key).encrypt(nonce,secret,b"NEXUS-LOCAL-KEYSTORE-v1")
    return json.dumps({"v":1,"kdf":"scrypt-n32768-r8-p1","salt":base64.b64encode(salt).decode(),
      "nonce":base64.b64encode(nonce).decode(),"ciphertext":base64.b64encode(cipher).decode()})

def _decrypt_secret(blob: str, password: str) -> bytes:
    from nexus_keystore_recovery import decrypt_keystore
    return decrypt_keystore(blob, password)

@router.post("/vault/create")
def create_vault(x: CreateVault):
    # Random EVM key; secret is encrypted before persistence and never returned.
    k = secrets.randbelow(SECP256K1_N-1)+1
    address = evm_address(k)
    secret = k.to_bytes(32,"big")
    blob = _encrypt_secret(secret,x.password)
    wallet_id=secrets.token_hex(8)
    with db() as c:
        c.execute("INSERT INTO vaults VALUES(?,?,?,?,?)",(wallet_id,x.label,address,blob,time.time()))
    return {"wallet_id":wallet_id,"label":x.label,"address":address,
      "networks":sorted(NETWORKS),"keystore_encrypted":True,"private_key_returned":False,
      "warning":"Local EVM keystore only. No seed phrase is generated. Do not use for material funds until independently audited."}

@router.post("/vault/unlock")
def unlock_vault(x: UnlockVault):
    with db() as c: row=c.execute("SELECT * FROM vaults WHERE id=?",(x.wallet_id,)).fetchone()
    if not row: raise HTTPException(404,"Wallet not found")
    try: secret=_decrypt_secret(row["keystore"],x.password)
    except Exception: raise HTTPException(401,"Incorrect password or corrupt keystore")
    if len(secret)!=32: raise HTTPException(500,"Invalid key material")
    key=int.from_bytes(secret,"big")
    if not 1 <= key < SECP256K1_N: raise HTTPException(500,"Invalid secp256k1 key")
    if evm_address(key).lower()!=row["address"].lower(): raise HTTPException(500,"Keystore/address mismatch")
    return {"unlocked":True,"wallet_id":row["id"],"address":row["address"],
      "networks":sorted(NETWORKS),"private_key_returned":False,
      "broadcast_enabled":False,"message":"Local key decryption and address correspondence verified. No transaction was sent."}

@router.get("/vaults")
def list_vaults():
    with db() as c: rows=c.execute("SELECT id,label,address,created FROM vaults ORDER BY created DESC").fetchall()
    return [dict(r) for r in rows]

@router.get("/bitcoin/vaults")
def list_bitcoin_vaults():
    with db() as c:
        rows = c.execute("SELECT id,label,address,compressed,created FROM bitcoin_vaults ORDER BY created DESC").fetchall()
    return [dict(r) for r in rows]

@router.post("/bitcoin/vault/unlock")
def unlock_bitcoin_vault(x: UnlockBitcoinVault):
    with db() as c:
        row = c.execute("SELECT * FROM bitcoin_vaults WHERE id=?", (x.wallet_id,)).fetchone()
    if not row:
        raise HTTPException(404, "Bitcoin vault not found")
    secret = None
    try:
        secret = bytearray(_decrypt_secret(row["keystore"], x.password))
        if len(secret) != 32:
            raise ValueError("Invalid private key length")
        scalar = int.from_bytes(secret, "big")
        if not 1 <= scalar < SECP256K1_N:
            raise ValueError("Invalid secp256k1 scalar")
        from nexus_wallet_formats import _p2pkh_address
        address = _p2pkh_address(bytes(secret), bool(row["compressed"]))
        if address != row["address"]:
            raise ValueError("Address/key mismatch")
        return {"unlocked": True, "wallet_id": row["id"], "address": address,
                "network": "BITCOIN_MAINNET_P2PKH", "address_match": True,
                "private_key_returned": False, "wif_returned": False,
                "transaction_signed": False, "transaction_broadcast": False}
    except Exception:
        raise HTTPException(401, "Incorrect password or corrupt Bitcoin vault")
    finally:
        if secret is not None:
            for i in range(len(secret)):
                secret[i] = 0

@router.post("/watch")
def add_watch(x: WatchAddress):
    net=x.network.upper()
    if net not in NETWORKS: raise HTTPException(400,"Unsupported EVM network")
    if not (len(x.address)==42 and x.address.startswith("0x") and all(ch in "0123456789abcdefABCDEF" for ch in x.address[2:])):
        raise HTTPException(400,"Invalid EVM address format")
    wid=secrets.token_hex(8)
    try:
        with db() as c: c.execute("INSERT INTO watch_addresses VALUES(?,?,?,?,?)",(wid,x.label,net,x.address,time.time()))
    except sqlite3.IntegrityError: raise HTTPException(409,"Address already watched on this network")
    return {"id":wid,"label":x.label,"network":net,"address":x.address}

@router.get("/watch")
def list_watch():
    with db() as c: rows=c.execute("SELECT id,label,network,address,created FROM watch_addresses ORDER BY created DESC").fetchall()
    return [dict(r) for r in rows]

@router.delete("/watch/{watch_id}")
def remove_watch(watch_id: str):
    with db() as c: cur=c.execute("DELETE FROM watch_addresses WHERE id=?",(watch_id,))
    if cur.rowcount==0: raise HTTPException(404,"Watch entry not found")
    return {"deleted":True}

@router.get("/status")
def wallet_status():
    with db() as c:
        vaults=c.execute("SELECT count(*) FROM vaults").fetchone()[0]
        watch=c.execute("SELECT count(*) FROM watch_addresses").fetchone()[0]
        bitcoin_vaults=c.execute("SELECT count(*) FROM bitcoin_vaults").fetchone()[0]
    return {"vault_wallets":vaults,"bitcoin_vaults":bitcoin_vaults,"watch_only_addresses":watch,"evm_networks":sorted(NETWORKS),
      "encrypted_local_keystore":True,"public_chain_broadcast":False,
      "btc_seed_wallet":"recovery lab only; BIP39 wordlist must be installed locally",
      "real_transfer_status":"not enabled until Bitcoin Core Regtest/Anvil local-node integration is executed and audited"}
