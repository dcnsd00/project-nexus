"""NEXUS authenticated encryption, key derivation, and Ed25519 signatures.

Uses reviewed primitives from the cryptography package. Keys are never persisted.
"""
from __future__ import annotations
import os
from dataclasses import dataclass
from cryptography.exceptions import InvalidSignature, InvalidTag
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from cryptography.hazmat.primitives.ciphers.aead import AESGCM, ChaCha20Poly1305
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

class SecurityInputError(ValueError):
    """Invalid key, nonce, payload, or parameter."""

class AuthenticationError(ValueError):
    """Ciphertext or associated data failed authentication."""

@dataclass(frozen=True)
class SealedMessage:
    algorithm: str
    nonce: bytes
    ciphertext: bytes

class CryptoSecurity:
    """Explicit API for authenticated encryption, HKDF-SHA256, and Ed25519."""
    KEY_BYTES = 32
    NONCE_BYTES = 12
    MAX_DATA_BYTES = 16 * 1024 * 1024
    MAX_INFO_BYTES = 1024

    @staticmethod
    def _bytes(name: str, value: bytes, *, max_bytes: int) -> bytes:
        if not isinstance(value, bytes):
            raise SecurityInputError(f"{name} must be bytes")
        if len(value) > max_bytes:
            raise SecurityInputError(f"{name} exceeds the configured size limit")
        return value

    @classmethod
    def _key(cls, key: bytes) -> bytes:
        key = cls._bytes("key", key, max_bytes=cls.KEY_BYTES)
        if len(key) != cls.KEY_BYTES:
            raise SecurityInputError("key must be exactly 32 bytes")
        return key

    @classmethod
    def hkdf_sha256(cls, input_key_material: bytes, length: int, *,
                    salt: bytes | None = None, info: bytes = b"NEXUS-HKDF-v1") -> bytes:
        ikm = cls._bytes("input_key_material", input_key_material, max_bytes=cls.MAX_DATA_BYTES)
        if not ikm:
            raise SecurityInputError("input_key_material must not be empty")
        if not isinstance(length, int) or isinstance(length, bool) or not 1 <= length <= 8160:
            raise SecurityInputError("length must be an integer from 1 to 8160 bytes")
        if salt is not None:
            salt = cls._bytes("salt", salt, max_bytes=cls.MAX_DATA_BYTES)
        info = cls._bytes("info", info, max_bytes=cls.MAX_INFO_BYTES)
        return HKDF(algorithm=hashes.SHA256(), length=length, salt=salt, info=info).derive(ikm)

    @classmethod
    def encrypt(cls, algorithm: str, key: bytes, plaintext: bytes, *,
                associated_data: bytes = b"") -> SealedMessage:
        key = cls._key(key)
        plaintext = cls._bytes("plaintext", plaintext, max_bytes=cls.MAX_DATA_BYTES)
        aad = cls._bytes("associated_data", associated_data, max_bytes=cls.MAX_DATA_BYTES)
        name = algorithm.strip().lower() if isinstance(algorithm, str) else ""
        nonce = os.urandom(cls.NONCE_BYTES)
        if name == "aes_256_gcm":
            ciphertext = AESGCM(key).encrypt(nonce, plaintext, aad)
        elif name == "chacha20_poly1305":
            ciphertext = ChaCha20Poly1305(key).encrypt(nonce, plaintext, aad)
        else:
            raise SecurityInputError("algorithm must be aes_256_gcm or chacha20_poly1305")
        return SealedMessage(name, nonce, ciphertext)

    @classmethod
    def decrypt(cls, algorithm: str, key: bytes, nonce: bytes, ciphertext: bytes, *,
                associated_data: bytes = b"") -> bytes:
        key = cls._key(key)
        nonce = cls._bytes("nonce", nonce, max_bytes=cls.NONCE_BYTES)
        if len(nonce) != cls.NONCE_BYTES:
            raise SecurityInputError("nonce must be exactly 12 bytes")
        ciphertext = cls._bytes("ciphertext", ciphertext, max_bytes=cls.MAX_DATA_BYTES + 16)
        if len(ciphertext) < 16:
            raise SecurityInputError("ciphertext must include the 16-byte authentication tag")
        aad = cls._bytes("associated_data", associated_data, max_bytes=cls.MAX_DATA_BYTES)
        name = algorithm.strip().lower() if isinstance(algorithm, str) else ""
        try:
            if name == "aes_256_gcm":
                return AESGCM(key).decrypt(nonce, ciphertext, aad)
            if name == "chacha20_poly1305":
                return ChaCha20Poly1305(key).decrypt(nonce, ciphertext, aad)
        except InvalidTag as exc:
            raise AuthenticationError("authentication failed; ciphertext, key, nonce, or AAD is invalid") from exc
        raise SecurityInputError("algorithm must be aes_256_gcm or chacha20_poly1305")

    @staticmethod
    def generate_ed25519_keypair() -> tuple[bytes, bytes]:
        private = Ed25519PrivateKey.generate()
        private_raw = private.private_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PrivateFormat.Raw,
            encryption_algorithm=serialization.NoEncryption())
        public_raw = private.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw)
        return private_raw, public_raw

    @staticmethod
    def ed25519_sign(private_key: bytes, message: bytes) -> bytes:
        if not isinstance(private_key, bytes) or len(private_key) != 32:
            raise SecurityInputError("Ed25519 private key must be exactly 32 raw bytes")
        if not isinstance(message, bytes) or len(message) > CryptoSecurity.MAX_DATA_BYTES:
            raise SecurityInputError("message must be bytes within the 16 MiB limit")
        return Ed25519PrivateKey.from_private_bytes(private_key).sign(message)

    @staticmethod
    def ed25519_verify(public_key: bytes, message: bytes, signature: bytes) -> bool:
        if not isinstance(public_key, bytes) or len(public_key) != 32:
            raise SecurityInputError("Ed25519 public key must be exactly 32 raw bytes")
        if not isinstance(message, bytes) or len(message) > CryptoSecurity.MAX_DATA_BYTES:
            raise SecurityInputError("message must be bytes within the 16 MiB limit")
        if not isinstance(signature, bytes) or len(signature) != 64:
            raise SecurityInputError("Ed25519 signature must be exactly 64 bytes")
        try:
            Ed25519PublicKey.from_public_bytes(public_key).verify(signature, message)
            return True
        except InvalidSignature:
            return False
