import hashlib, unittest
from research.crypto_lab import digest_hex, verify_candidate, derive_key_pbkdf2, key_material_check
from research.hypothesis_lab import run_null_hypothesis_experiment
from core.algorithm_registry import PROFILES, get_profile, format_payout_identity
from research.special_math import avalanche_experiment, hamming_distance, HYPOTHESES

class CryptoLabTests(unittest.TestCase):
    def test_sha256_vector(self):
        self.assertEqual(digest_hex('SHA-256', b'abc'), hashlib.sha256(b'abc').hexdigest())
    def test_sha512_vector(self):
        self.assertEqual(digest_hex('SHA-512', b'abc'), hashlib.sha512(b'abc').hexdigest())
    def test_candidate_verification(self):
        target=hashlib.sha256(b'known candidate').hexdigest()
        self.assertTrue(verify_candidate('SHA-256', b'known candidate', target))
        self.assertFalse(verify_candidate('SHA-256', b'other', target))
    def test_pbkdf2_key_derivation(self):
        salt='00112233445566778899aabbccddeeff'
        key=derive_key_pbkdf2('correct horse battery staple', salt, 100000, 32)
        self.assertEqual(len(bytes.fromhex(key)),32)
    def test_key_material(self):
        x=key_material_check('00'*32,'AES-256-GCM','11'*12,'22'*16)
        self.assertTrue(x['key_length_valid'])
        self.assertEqual(x['nonce_bytes'],12)
    def test_hypothesis_reproducible(self):
        self.assertEqual(run_null_hypothesis_experiment(1000,42),run_null_hypothesis_experiment(1000,42))
    def test_payout_asset_switch_format(self):
        self.assertEqual(format_payout_identity('wallet.worker','BTC'),'BTC:wallet.worker')
        self.assertEqual(format_payout_identity('XMR:wallet.worker','BTC'),'XMR:wallet.worker')
    def test_profiles_are_classified(self):
        self.assertEqual(get_profile('cpu_randomx').status,'LIVE_BACKEND')
        self.assertEqual(get_profile('sha256d_lab').status,'RESEARCH_ONLY')
    def test_avalanche_and_hamming_math(self):
        self.assertEqual(hamming_distance(b'\x00',b'\xff'),8)
        a=avalanche_experiment('SHA-256',32,100,7)
        b=avalanche_experiment('SHA-256',32,100,7)
        self.assertEqual(a,b)
        self.assertEqual(a['expected_mean'],128)
        self.assertGreaterEqual(len(HYPOTHESES),5)
    def test_aes_gcm_roundtrip_when_optional_dependency_exists(self):
        try:
            from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        except ImportError:
            self.skipTest('cryptography optional dependency not installed')
        import os, base64
        from research.crypto_lab import decrypt_aes_gcm
        key=os.urandom(32); nonce=os.urandom(12); aad=b'mmx-test'; plain=b'known plaintext'
        ciphertext=AESGCM(key).encrypt(nonce,plain,aad)
        result=decrypt_aes_gcm(base64.b64encode(ciphertext).decode(),key.hex(),nonce.hex(),base64.b64encode(aad).decode())
        self.assertEqual(result,plain)

if __name__ == '__main__': unittest.main()
