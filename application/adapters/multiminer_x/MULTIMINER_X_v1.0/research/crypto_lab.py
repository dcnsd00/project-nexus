"""Offline hash identification, digest verification, and key derivation helpers.
SHA-256/SHA-512 are one-way hash functions, not encryption; this module never
claims to decrypt a digest or recover a private key from a public hash.
"""
from __future__ import annotations
import base64, hashlib, hmac, os
from dataclasses import dataclass

HASHES = {"SHA-256": hashlib.sha256, "SHA-512": hashlib.sha512,
          "SHA3-256": hashlib.sha3_256, "BLAKE2b-512": hashlib.blake2b}

def digest_hex(algorithm: str, data: bytes) -> str:
    try: fn = HASHES[algorithm]
    except KeyError as exc: raise ValueError("Unsupported digest algorithm") from exc
    return fn(data).hexdigest()

def verify_candidate(algorithm: str, candidate: bytes, target_hex: str) -> bool:
    target = target_hex.strip().lower()
    if len(target) != HASHES[algorithm]().digest_size * 2:
        raise ValueError("Digest length does not match selected algorithm")
    try: bytes.fromhex(target)
    except ValueError as exc: raise ValueError("Target must be hexadecimal") from exc
    return hmac.compare_digest(digest_hex(algorithm, candidate), target)

def derive_key_pbkdf2(password: str, salt_hex: str, iterations: int = 600_000, key_bytes: int = 32) -> str:
    if not 100_000 <= iterations <= 5_000_000: raise ValueError("PBKDF2 iterations must be 100k..5m")
    if key_bytes not in (16, 24, 32): raise ValueError("AES key size must be 16, 24, or 32 bytes")
    salt = bytes.fromhex(salt_hex)
    if len(salt) < 16: raise ValueError("Use a salt of at least 16 bytes")
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations, dklen=key_bytes).hex()

def decrypt_aes_gcm(ciphertext_b64: str, key_hex: str, nonce_hex: str, aad_b64: str = "") -> bytes:
    """Decrypt AES-GCM only when the caller already has the correct key and nonce.
    Requires `cryptography`; no key guessing, brute force, or wallet access.
    ciphertext_b64 must contain ciphertext concatenated with the 16-byte tag.
    """
    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    except ImportError as exc:
        raise RuntimeError("Install dependency: python -m pip install cryptography") from exc
    key, nonce = bytes.fromhex(key_hex), bytes.fromhex(nonce_hex)
    if len(key) not in (16, 24, 32): raise ValueError("AES key must be 16/24/32 bytes")
    if len(nonce) != 12: raise ValueError("AES-GCM nonce must be 12 bytes")
    ct = base64.b64decode(ciphertext_b64, validate=True)
    aad = base64.b64decode(aad_b64, validate=True) if aad_b64 else None
    return AESGCM(key).decrypt(nonce, ct, aad)

def key_material_check(key_hex: str, cipher: str, nonce_hex: str = "", salt_hex: str = "") -> dict:
    key = bytes.fromhex(key_hex)
    valid = len(key) in (16, 24, 32) if cipher.startswith("AES") else len(key) > 0
    return {"cipher": cipher, "key_bytes": len(key), "key_length_valid": valid,
            "nonce_bytes": len(bytes.fromhex(nonce_hex)) if nonce_hex else None,
            "salt_bytes": len(bytes.fromhex(salt_hex)) if salt_hex else None,
            "required_material": ["cipher", "key", "nonce/IV", "authentication tag (AEAD)", "AAD if used", "KDF + salt + iterations if password-derived"]}
