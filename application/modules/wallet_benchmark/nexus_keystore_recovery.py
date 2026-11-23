from __future__ import annotations
import base64, binascii, hashlib, json
from dataclasses import dataclass
from typing import Any
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from nexus_wallet_benchmark import SECP256K1_N, evm_address

AAD = b"NEXUS-LOCAL-KEYSTORE-v1"
MAX_BLOB_BYTES = 64 * 1024
MAX_PASSWORD_BYTES = 1024

class KeystoreError(ValueError): pass
class KeystoreFormatError(KeystoreError): pass
class KeystoreAuthenticationError(KeystoreError): pass
class KeystoreKeyError(KeystoreError): pass

def _b64decode(value: Any, name: str, expected: int | None = None) -> bytes:
    if not isinstance(value, str) or not value:
        raise KeystoreFormatError(f"{name} missing")
    try:
        raw = base64.b64decode(value, validate=True)
    except (binascii.Error, ValueError):
        raise KeystoreFormatError(f"{name} invalid base64")
    if expected is not None and len(raw) != expected:
        raise KeystoreFormatError(f"{name} must be {expected} bytes")
    return raw

def parse_keystore(blob: str) -> dict:
    if not isinstance(blob, str) or len(blob.encode("utf-8")) > MAX_BLOB_BYTES:
        raise KeystoreFormatError("keystore too large or invalid")
    try:
        obj = json.loads(blob)
    except Exception:
        raise KeystoreFormatError("invalid JSON")
    if not isinstance(obj, dict) or obj.get("v") != 1 or obj.get("kdf") != "scrypt-n32768-r8-p1":
        raise KeystoreFormatError("unsupported keystore version or KDF")
    salt = _b64decode(obj.get("salt"), "salt", 16)
    nonce = _b64decode(obj.get("nonce"), "nonce", 12)
    ciphertext = _b64decode(obj.get("ciphertext"), "ciphertext")
    if len(ciphertext) != 48:  # 32-byte key + 16-byte GCM tag
        raise KeystoreFormatError("ciphertext length invalid")
    return {"salt": salt, "nonce": nonce, "ciphertext": ciphertext}

def decrypt_keystore(blob: str, password: str) -> bytes:
    if not isinstance(password, str) or not password:
        raise KeystoreAuthenticationError("password required")
    if len(password.encode("utf-8")) > MAX_PASSWORD_BYTES:
        raise KeystoreAuthenticationError("password too long")
    obj = parse_keystore(blob)
    key = hashlib.scrypt(password.encode("utf-8"), salt=obj["salt"],
                         n=2**15, r=8, p=1, dklen=32, maxmem=128*1024*1024)
    try:
        plaintext = AESGCM(key).decrypt(obj["nonce"], obj["ciphertext"], AAD)
    except Exception:
        raise KeystoreAuthenticationError("wrong password or authenticated data mismatch")
    if len(plaintext) != 32:
        raise KeystoreKeyError("decrypted private key has invalid length")
    scalar = int.from_bytes(plaintext, "big")
    if not 1 <= scalar < SECP256K1_N:
        raise KeystoreKeyError("decrypted private key is outside secp256k1 range")
    return plaintext

def decrypt_and_verify_address(blob: str, password: str, expected_address: str) -> dict:
    secret = bytearray(decrypt_keystore(blob, password))
    try:
        actual = evm_address(int.from_bytes(secret, "big"))
        if not isinstance(expected_address, str) or actual.lower() != expected_address.lower():
            raise KeystoreKeyError("decrypted key does not match expected address")
        return {"decrypted": True, "address_verified": True, "address": actual,
                "private_key_returned": False}
    finally:
        for index in range(len(secret)):
            secret[index] = 0
