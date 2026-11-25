import pytest
from modules.crypto_engine.security import AuthenticationError, CryptoSecurity, SecurityInputError

@pytest.mark.parametrize("algorithm", ["aes_256_gcm", "chacha20_poly1305"])
def test_aead_round_trip_and_aad(algorithm):
    key = bytes(range(32))
    sealed = CryptoSecurity.encrypt(algorithm, key, b"nexus secret", associated_data=b"header-v1")
    assert len(sealed.nonce) == 12
    assert CryptoSecurity.decrypt(algorithm, key, sealed.nonce, sealed.ciphertext,
                                  associated_data=b"header-v1") == b"nexus secret"

@pytest.mark.parametrize("algorithm", ["aes_256_gcm", "chacha20_poly1305"])
def test_aead_rejects_tampering_and_wrong_aad(algorithm):
    key = b"k" * 32
    sealed = CryptoSecurity.encrypt(algorithm, key, b"payload", associated_data=b"metadata")
    tampered = sealed.ciphertext[:-1] + bytes([sealed.ciphertext[-1] ^ 1])
    with pytest.raises(AuthenticationError):
        CryptoSecurity.decrypt(algorithm, key, sealed.nonce, tampered, associated_data=b"metadata")
    with pytest.raises(AuthenticationError):
        CryptoSecurity.decrypt(algorithm, key, sealed.nonce, sealed.ciphertext, associated_data=b"other")

def test_hkdf_sha256_is_deterministic_and_context_separated():
    a = CryptoSecurity.hkdf_sha256(b"input key material", 32, salt=b"salt", info=b"wallet")
    b = CryptoSecurity.hkdf_sha256(b"input key material", 32, salt=b"salt", info=b"wallet")
    c = CryptoSecurity.hkdf_sha256(b"input key material", 32, salt=b"salt", info=b"edge")
    assert len(a) == 32 and a == b and a != c

def test_ed25519_sign_verify_and_reject_modified_message():
    private, public = CryptoSecurity.generate_ed25519_keypair()
    signature = CryptoSecurity.ed25519_sign(private, b"nexus task result")
    assert len(private) == 32 and len(public) == 32 and len(signature) == 64
    assert CryptoSecurity.ed25519_verify(public, b"nexus task result", signature)
    assert not CryptoSecurity.ed25519_verify(public, b"modified", signature)

def test_invalid_key_nonce_and_parameters_are_rejected():
    with pytest.raises(SecurityInputError):
        CryptoSecurity.encrypt("aes_256_gcm", b"short", b"data")
    with pytest.raises(SecurityInputError):
        CryptoSecurity.decrypt("aes_256_gcm", b"k" * 32, b"short", b"x" * 16)
    with pytest.raises(SecurityInputError):
        CryptoSecurity.hkdf_sha256(b"ikm", 8161)
    with pytest.raises(SecurityInputError):
        CryptoSecurity.encrypt("unknown", b"k" * 32, b"data")
