from __future__ import annotations
import json, secrets, time, sqlite3
from typing import Any
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from nexus_wallet_formats import (
    detect_wallet_format, decrypt_web3_v3, decrypt_bip38_non_ec,
    validate_solana_keypair, bip39_validate, load_bip39_wordlist,
    bip39_recover_one_missing_by_address, WalletFormatError,
    WalletPasswordError, WalletIntegrityError, RecoveryAuthorizationError,
    bitcoin_core_check_wallet_passphrase, bitcoin_core_inspect_wallet,
)
from nexus_wallet_manager import db, _encrypt_secret
from nexus_wallet_search import search_wallet_files
from nexus_keystore_recovery import (
    decrypt_and_verify_address, KeystoreError,
    KeystoreAuthenticationError,
)

router = APIRouter(prefix="/api/wallet/recovery", tags=["wallet-recovery"])

class DetectRequest(BaseModel):
    payload: Any

class DecryptRequest(BaseModel):
    format: str = Field(min_length=1, max_length=64)
    payload: Any
    password: str = Field(min_length=1, max_length=1024)
    vault_password: str | None = Field(default=None, min_length=1, max_length=1024)
    label: str = Field(default="Imported recovery wallet", min_length=1, max_length=64)
    owner_authorized: bool = False

class ImportBIP38Request(BaseModel):
    encrypted_key: str = Field(min_length=58, max_length=58)
    password: str = Field(min_length=1, max_length=256)
    vault_password: str = Field(min_length=12, max_length=256)
    label: str = Field(default="Recovered Bitcoin wallet", min_length=1, max_length=64)
    owner_authorized: bool = False

class BIP39CheckRequest(BaseModel):
    mnemonic: str = Field(min_length=12, max_length=512)
    language: str = "english"
    owner_authorized: bool = False

class WalletSearchRequest(BaseModel):
    root: str = Field(min_length=3, max_length=1024)
    max_files: int = Field(default=5000, ge=1, le=20000)
    max_depth: int = Field(default=8, ge=0, le=16)

class BitcoinCoreCheckRequest(BaseModel):
    rpc_url: str = "http://127.0.0.1:18443"
    username: str = ""
    rpc_password: str = ""
    wallet_name: str = Field(min_length=1, max_length=128)
    wallet_passphrase: str = Field(min_length=1, max_length=1024)
    owner_authorized: bool = False

class BitcoinCoreInspectRequest(BaseModel):
    rpc_url: str = "http://127.0.0.1:18443"
    username: str = ""
    rpc_password: str = ""
    wallet_name: str = Field(min_length=1, max_length=128)
    owner_authorized: bool = False
    max_transactions: int = Field(default=10000, ge=1, le=10000)

class BIP39MissingRequest(BaseModel):
    partial_mnemonic: str = Field(min_length=12, max_length=512)
    expected_address: str = Field(min_length=10, max_length=128)
    format: str
    language: str = "english"
    passphrase: str = ""
    address_index: int = Field(default=0, ge=0, le=1_000_000)
    owner_authorized: bool = False

def _local_only(request: Request):
    host = request.client.host if request.client else ""
    if host not in {"127.0.0.1", "::1", "localhost", "testclient"}:
        raise HTTPException(403, "Wallet recovery API accepts loopback clients only")

def _authorized(value: bool):
    if value is not True:
        raise HTTPException(403, "Confirmă că wallet-ul îți aparține sau ai autorizare explicită")

@router.get("/formats")
def recovery_formats():
    return {
        "formats": [
            {"id":"NEXUS_AESGCM_V1", "status":"SUPPORTED", "operation":"decrypt existing NEXUS vault"},
            {"id":"WEB3_SECRET_STORAGE_V3", "status":"SUPPORTED", "operation":"decrypt + import into encrypted NEXUS EVM vault"},
            {"id":"BIP38_0142", "status":"SUPPORTED_NON_EC", "operation":"decrypt owner-provided key and re-encrypt into a dedicated NEXUS Bitcoin vault; no raw key export"},
            {"id":"BIP39", "status":"SUPPORTED_WITH_WORDLIST", "operation":"checksum, seed derivation and one missing word with owner address/path"},
            {"id":"SOLANA_KEYPAIR_JSON", "status":"VALIDATION_ONLY", "operation":"validate 64-byte Ed25519 keypair"},
            {"id":"BITCOIN_CORE_WALLET_DAT", "status":"LOCAL_READ_ONLY_INSPECT", "operation":"explicitly loaded owner wallet via loopback RPC; inspect balances, public addresses and recorded transaction history"},
            {"id":"ELECTRUM_WALLET", "status":"VENDOR_TOOL_REQUIRED", "operation":"official Electrum GUI/CLI"},
            {"id":"METAMASK_BROWSER_VAULT", "status":"VENDOR_TOOL_REQUIRED", "operation":"MetaMask-supported recovery"},
            {"id":"MONERO_WALLET_FILE", "status":"VENDOR_TOOL_REQUIRED", "operation":"official Monero CLI/GUI"},
            {"id":"BIP38_0143_EC_MULTIPLY", "status":"INACTIVE", "operation":"not implemented"},
            {"id":"EIP2335_BLS_KEYSTORE", "status":"INACTIVE", "operation":"not implemented"},
        ],
        "password_policy":"Password/passphrase is entered at runtime; never stored or logged",
        "search_scope":"local files supplied by owner; no blockchain-wide private-key search or password brute force",
    }

@router.post("/detect")
def detect_format(x: DetectRequest, request: Request):
    _local_only(request)
    try:
        return {"status":"FORMAT_DETECTED", **detect_wallet_format(x.payload)}
    except Exception:
        return {"status":"UNSUPPORTED_FORMAT", "format":"UNKNOWN"}

@router.post("/decrypt")
def decrypt_and_import(x: DecryptRequest, request: Request):
    _local_only(request); _authorized(x.owner_authorized)
    result = None
    secret_buffer = None
    try:
        if x.format == "WEB3_SECRET_STORAGE_V3":
            if not isinstance(x.payload, dict): raise WalletFormatError("Web3 keystore must be a JSON object")
            result = decrypt_web3_v3(x.payload, x.password, owner_authorized=True)
            secret_buffer = bytearray(result["private_key"])
            address = result["address"]
            # Re-encrypt directly into NEXUS's local vault. Reuse source password only
            # when it satisfies NEXUS's 12-character minimum; otherwise require a separate vault password.
            vault_password = x.vault_password or x.password
            if len(vault_password) < 12:
                raise HTTPException(422, "NEXUS vault password must contain at least 12 characters; provide vault_password")
            blob = _encrypt_secret(bytes(secret_buffer), vault_password)
            wallet_id = secrets.token_hex(8)
            with db() as c:
                c.execute("INSERT INTO vaults VALUES(?,?,?,?,?)", (wallet_id, x.label, address, blob, time.time()))
            return {"status":"DECRYPTION_SUCCESS", "format":result["format"], "address":address,
                    "wallet_id":wallet_id, "address_match":"ADDRESS_MATCH",
                    "re_encrypted_in_nexus_vault":True, "private_key_returned":False,
                    "broadcast_enabled":False}
        if x.format == "NEXUS_AESGCM_V1":
            obj = x.payload.get("keystore", x.payload) if isinstance(x.payload, dict) else None
            if not isinstance(obj, dict): raise WalletFormatError("NEXUS keystore must be a JSON object")
            expected = x.payload.get("address") if isinstance(x.payload, dict) else None
            if not expected: raise WalletFormatError("Expected address is required for NEXUS keystore verification")
            verified = decrypt_and_verify_address(json.dumps(obj), x.password, expected)
            return {"status":"DECRYPTION_SUCCESS", "format":"NEXUS_AESGCM_V1",
                    "address":verified["address"], "address_match":"ADDRESS_MATCH",
                    "private_key_returned":False, "re_encrypted_in_nexus_vault":False}
        if x.format == "BIP38_0142":
            if not isinstance(x.payload, str): raise WalletFormatError("BIP38 payload must be the encrypted 6P... string")
            result = decrypt_bip38_non_ec(x.payload.strip(), x.password, owner_authorized=True)
            return {"status":"DECRYPTION_SUCCESS", "format":result["format"], "address":result["address"],
                    "address_match":"ADDRESS_MATCH", "compressed":result["compressed"],
                    "private_key_returned":False, "wif_returned":False,
                    "note":"Cheia a fost verificată în memorie și nu a fost exportată sau salvată."}
        raise HTTPException(400, "Formatul nu este acceptat de acest endpoint")
    except HTTPException:
        raise
    except (WalletPasswordError, KeystoreAuthenticationError) as e:
        raise HTTPException(401, f"PASSWORD_INVALID: {e}")
    except (WalletFormatError, WalletIntegrityError, RecoveryAuthorizationError, KeystoreError) as e:
        raise HTTPException(422, f"DECRYPTION_FAILED: {e}")
    except Exception as e:
        raise HTTPException(422, f"DECRYPTION_FAILED: {type(e).__name__}")
    finally:
        if secret_buffer is not None:
            for i in range(len(secret_buffer)): secret_buffer[i] = 0
        if result and isinstance(result, dict):
            result.pop("private_key", None); result.pop("wif", None)

@router.post("/import-bip38")
def import_bip38_to_vault(x: ImportBIP38Request, request: Request):
    """Decrypt one owner-supplied BIP38 key in memory and re-encrypt it at rest in NEXUS."""
    _local_only(request); _authorized(x.owner_authorized)
    result = None
    secret_buffer = None
    try:
        result = decrypt_bip38_non_ec(x.encrypted_key.strip(), x.password, owner_authorized=True)
        secret_buffer = bytearray(result["private_key"])
        blob = _encrypt_secret(bytes(secret_buffer), x.vault_password)
        wallet_id = secrets.token_hex(8)
        with db() as c:
            c.execute("INSERT INTO bitcoin_vaults VALUES(?,?,?,?,?,?)",
                      (wallet_id, x.label, result["address"], int(result["compressed"]), blob, time.time()))
        return {"status":"DECRYPTION_SUCCESS", "format":"BIP38_NON_EC",
                "wallet_id":wallet_id, "address":result["address"],
                "network":"BITCOIN_MAINNET_P2PKH", "address_match":"ADDRESS_MATCH",
                "encrypted_in_nexus_bitcoin_vault":True,
                "private_key_returned":False, "wif_returned":False,
                "transaction_signed":False, "transaction_broadcast":False}
    except WalletPasswordError as e:
        raise HTTPException(401, f"PASSWORD_INVALID: {e}")
    except sqlite3.IntegrityError:
        raise HTTPException(409, "This Bitcoin address is already stored in the NEXUS vault")
    except (WalletFormatError, WalletIntegrityError, RecoveryAuthorizationError) as e:
        raise HTTPException(422, f"DECRYPTION_FAILED: {e}")
    finally:
        if secret_buffer is not None:
            for i in range(len(secret_buffer)):
                secret_buffer[i] = 0
        if isinstance(result, dict):
            result.pop("private_key", None); result.pop("wif", None)

@router.post("/solana/validate")
def validate_solana(x: DetectRequest, request: Request):
    _local_only(request)
    try:
        result = validate_solana_keypair(x.payload)
        return {"status":"ADDRESS_MATCH", **result}
    except (WalletFormatError, WalletIntegrityError) as e:
        raise HTTPException(422, str(e))

@router.post("/bip39/check")
def check_bip39(x: BIP39CheckRequest, request: Request):
    _local_only(request); _authorized(x.owner_authorized)
    try:
        words = load_bip39_wordlist(x.language)
        result = bip39_validate(x.mnemonic, words)
        return {"status":"ADDRESS_MATCH" if result["valid"] else "PASSWORD_INVALID",
                "mnemonic_checksum_valid":result["valid"], "reason":result["reason"],
                "word_count":result.get("word_count"), "seed_exported":False}
    except WalletFormatError as e:
        raise HTTPException(422, str(e))

@router.post("/bip39/one-missing")
def recover_bip39_missing(x: BIP39MissingRequest, request: Request):
    _local_only(request); _authorized(x.owner_authorized)
    try:
        words = load_bip39_wordlist(x.language)
        matches = bip39_recover_one_missing_by_address(
            x.partial_mnemonic, words, x.expected_address, x.format,
            x.passphrase, x.address_index, owner_authorized=True)
        # Return only the missing word and public derivation metadata.
        # The completed mnemonic is intentionally not sent back over the API.
        safe_matches = [
            {"recovered_word": item["recovered_word"], "address": item["address"],
             "format": item["format"], "path": item["path"]}
            for item in matches
        ]
        return {"status":"ADDRESS_MATCH" if safe_matches else "ADDRESS_MISMATCH",
                "match_count":len(safe_matches), "matches":safe_matches,
                "private_key_exported":False, "seed_exported":False,
                "mnemonic_exported":False}
    except WalletFormatError as e:
        raise HTTPException(422, str(e))


@router.post("/search")
def search_local_wallet_files(x: WalletSearchRequest, request: Request):
    _local_only(request)
    try:
        result=search_wallet_files(x.root, x.max_files, x.max_depth)
        return {"status":"SEARCH_COMPLETE", **result,
                "content_inspection":"bounded JSON structure and encrypted BIP38 marker detection only",
                "decryption_attempted":False, "private_keys_extracted":False}
    except (OSError, ValueError) as e:
        raise HTTPException(422, str(e))


@router.post("/bitcoin-core/inspect")
def inspect_bitcoin_core_wallet(x: BitcoinCoreInspectRequest, request: Request):
    _local_only(request); _authorized(x.owner_authorized)
    try:
        result=bitcoin_core_inspect_wallet(
            x.rpc_url, x.username, x.rpc_password, x.wallet_name,
            owner_authorized=True, max_transactions=x.max_transactions)
        return {"status":"INSPECTION_COMPLETE", **result}
    except (WalletFormatError, RecoveryAuthorizationError) as e:
        raise HTTPException(422, str(e))

@router.post("/bitcoin-core/check")
def check_bitcoin_core_passphrase(x: BitcoinCoreCheckRequest, request: Request):
    _local_only(request); _authorized(x.owner_authorized)
    try:
        result=bitcoin_core_check_wallet_passphrase(
            x.rpc_url, x.username, x.rpc_password, x.wallet_name,
            x.wallet_passphrase, owner_authorized=True)
        return {"status":"DECRYPTION_SUCCESS", **result,
                "private_key_returned":False, "transaction_broadcast":False}
    except WalletPasswordError as e:
        raise HTTPException(401, f"PASSWORD_INVALID: {e}")
    except (WalletFormatError, RecoveryAuthorizationError) as e:
        raise HTTPException(422, str(e))
