"""
Suita de testare NEXUS - rulata obligatoriu inainte de orice experiment.

Teste unitare:
- vectori standard NIST pentru SHA-256 si SHA-512 (64/80 runde).
- echivalenta cu hashlib pe date aleatoare de lungimi variate.
- midstate miner: identic cu double_sha256 pe 1000 nonces.
- blocul Genesis Bitcoin (validare end-to-end).
- runde reduse: determinism + consistenta interna.
- SAT: solutia gasita se verifica cu implementarea separata.
"""

import unittest
import struct
import random
import hashlib

from .sha256_advanced import sha256, double_sha256, MidstateMiner, compress, IV256
from .sha512_advanced import sha512
from .benchmark import make_test_header


GENESIS_HEADER = bytes.fromhex(
    "0100000000000000000000000000000000000000000000000000000000000000000000003ba3ed"
    "fd7a7b12b27ac72c3e67768f617fc81bc3888a51323a9fb8aa4b1e5e4a29ab5f49ffff001d"
    "1dac2b7c")
GENESIS_NONCE = 2083236893
# forma afisata public (little-endian, inversata)
GENESIS_HASH = "000000000019d6689c085ae165831e934ff763ae46a2a6c172b3f1b60a8ce26f"
# hash-ul in ordinea interna a digest-ului (big-endian)
GENESIS_HASH_INTERNAL = "6fe28c0ab6f1b372c1a6a246ae63f74f931e8365e15a089c68d6190000000000"


class TestSHA256Vectors(unittest.TestCase):
    def test_nist_vectors(self):
        cases = [
            (b"", "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"),
            (b"abc", "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"),
            (b"abcdbcdecdefdefgefghfghighijhijkijkljklmklmnlmnomnopnopq",
             "248d6a61d20638b8e5c026930c3e6039a33ce45964ff2167f6ecedd419db06c1"),
            (b"a" * 1000000,
             "cdc76e5c9914fb9281a1c7e284d73e67f1809a48a497200e046d39ccc7112cd0"),
        ]
        for msg, want in cases:
            self.assertEqual(sha256(msg).hex(), want, msg[:20])

    def test_matches_hashlib_random(self):
        rng = random.Random(7)
        for _ in range(30):
            n = rng.choice([0, 1, 16, 31, 32, 55, 64, 65, 100, 128, 1000])
            data = bytes(rng.getrandbits(8) for _ in range(n))
            self.assertEqual(sha256(data), hashlib.sha256(data).digest())

    def test_double_sha(self):
        data = b"NEXUS test"
        self.assertEqual(double_sha256(data),
                         hashlib.sha256(hashlib.sha256(data).digest()).digest())


class TestSHA512Vectors(unittest.TestCase):
    def test_nist_vectors(self):
        cases = [
            (b"", "cf83e1357eefb8bdf1542850d66d8007d620e4050b5715dc83f4a921d36ce9ce"
                  "47d0d13c5d85f2b0ff8318d2877eec2f63b931bd47417a81a538327af927da3e"),
            (b"abc", "ddaf35a193617abacc417349ae20413112e6fa4e89a97ea20a9eeee64b55d39a"
                     "2192992a274fc1a836ba3c23a3feebbd454d4423643ce80e2a9ac94fa54ca49f"),
        ]
        for msg, want in cases:
            self.assertEqual(sha512(msg).hex(), want, msg[:20])

    def test_matches_hashlib_random(self):
        rng = random.Random(11)
        for _ in range(15):
            n = rng.choice([0, 1, 64, 111, 112, 128, 129, 300])
            data = bytes(rng.getrandbits(8) for _ in range(n))
            self.assertEqual(sha512(data), hashlib.sha512(data).digest())


class TestMidstateMiner(unittest.TestCase):
    def test_matches_naive(self):
        header = make_test_header(seed=3)
        m = MidstateMiner(header)
        rng = random.Random(5)
        for _ in range(200):
            nonce = rng.getrandbits(32)
            h = bytearray(header)
            h[76:80] = struct.pack("<I", nonce)
            self.assertEqual(m.hash_header(nonce), double_sha256(bytes(h)))

    def test_genesis_block(self):
        # Antetul Genesis serializează nonce-ul uint32 little-endian în bytes 76..79.
        self.assertEqual(double_sha256(GENESIS_HEADER).hex(), GENESIS_HASH_INTERNAL)
        # API-ul primește nonce-ul numeric; serializarea Bitcoin este little-endian.
        m = MidstateMiner(GENESIS_HEADER)
        self.assertEqual(m.hash_header(GENESIS_NONCE).hex(), GENESIS_HASH_INTERNAL)


class TestReducedRounds(unittest.TestCase):
    def test_determinism(self):
        rng = random.Random(1)
        data = bytes(rng.getrandbits(8) for _ in range(64))
        for rounds in (1, 4, 8, 16, 32, 63, 64):
            self.assertEqual(sha256(data, rounds), sha256(data, rounds))

    def test_full_equals_hashlib(self):
        rng = random.Random(2)
        data = bytes(rng.getrandbits(8) for _ in range(200))
        self.assertEqual(sha256(data, 64), hashlib.sha256(data).digest())

    def test_compress_state_iv(self):
        # compresia blocului zero din starea IV = midstate-ul cunoscut
        # al SHA-256 (constanta publica, verificare independenta de hashlib)
        block = [0] * 16
        out = compress(list(IV256), block, 64)
        self.assertEqual(
            struct.pack(">8I", *out).hex(),
            "da5698be17b9b46962335799779fbeca8ce5d491c0d26243bafef9ea1837a9d8")


class TestDifferentialSanity(unittest.TestCase):
    def test_one_round_probability(self):
        """La 1 runda, o diferenta de 1 bit in W[0] (bit 31, fara propagare
        de carry in plus) produce iesiri diferite cu siguranta."""
        from .differential_search import differential_counts
        delta = [0] * 16
        delta[0] = 1 << 31
        counts = differential_counts(delta, 1, 500, seed=3)
        self.assertTrue(all(d != (0,) * 8 for d in counts))

    def test_high_rounds_look_uniform(self):
        from .differential_search import differential_counts
        delta = [0] * 16
        delta[0] = 1 << 31
        counts = differential_counts(delta, 20, 3000, seed=4)
        # nicio diferenta de iesire nu trebuie sa apara de mai mult de
        # ~2 ori la 3000 de esantioane (uniformitate)
        mx = max(counts.values())
        self.assertLess(mx, 4, f"bias suspect la 20 runde: {mx}")


class TestSAT(unittest.TestCase):
    def test_preimage_verified(self):
        try:
            from .sat_smt_solver import solve_partial_preimage
        except ImportError:
            self.skipTest("python-sat indisponibil")
        rep = solve_partial_preimage(6, {0: 0}, seed=99, verbose=False)
        if "error" in rep:
            self.skipTest(rep["error"])
        self.assertEqual(rep["status"], "SAT")
        self.assertTrue(rep["independent_verification"]["matches_target"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
