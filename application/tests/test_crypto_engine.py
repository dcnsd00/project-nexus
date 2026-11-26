import hashlib
import pytest
from fastapi.testclient import TestClient
from modules.crypto_engine import CryptoEngine, CryptoInputError

engine = CryptoEngine()

@pytest.mark.parametrize("algorithm,expected", [
    ("sha256", "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"),
    ("sha512", "cf83e1357eefb8bdf1542850d66d8007d620e4050b5715dc83f4a921d36ce9ce47d0d13c5d85f2b0ff8318d2877eec2f63b931bd47417a81a538327af927da3e"),
    ("sha3_256", "a7ffc6f8bf1ed76651c14756a061d662f580ff4de43b49fa82d80a4b80f8434a"),
    ("sha3_512", "a69f73cca23a9ac5c8b567dc185a756e97c982164fe25859e0d1dcc1475c80a615b2123af1f5f94c11e3e9402c3ac558f500199d95b6d3e301758586281dcd26"),
    ("blake2b_512", hashlib.blake2b(b"").hexdigest()),
    ("blake2s_256", hashlib.blake2s(b"").hexdigest()),
])
def test_known_empty_message_vectors(algorithm, expected):
    assert engine.digest_hex(algorithm, b"") == expected

@pytest.mark.parametrize("message,expected", [
    (
        b"abc",
        "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad",
    ),
    (
        b"abcdbcdecdefdefgefghfghighijhijkijkljklmklmnlmnomnopnopq",
        "248d6a61d20638e5b8c026930c3e6039a33ce45964ff2167f6ecedd419db06c1",
    ),
])
def test_sha256_fips_180_4_known_vectors(message, expected):
    assert engine.digest_hex("sha256", message) == expected


def test_sha256d_is_double_sha256():
    assert engine.digest("sha256d", b"abc") == hashlib.sha256(hashlib.sha256(b"abc").digest()).digest()

def test_shake_output_length():
    assert len(engine.digest("shake256", b"abc", 73)) == 73

def test_experimental_composite_is_deterministic_and_domain_separated():
    a = engine.digest("hybrid_sha256_blake2b", b"abc")
    assert a == engine.digest("hybrid_sha256_blake2b", b"abc")
    assert a != engine.digest("hybrid_sha256_blake2b", b"abcd")
    row = next(x for x in engine.algorithms() if x["name"] == "hybrid_sha256_blake2b")
    assert row["security_status"] == "experimental_do_not_use_for_consensus"

def test_hmac_sha256_matches_stdlib():
    import hmac
    assert engine.hmac_sha256(b"key", b"data") == hmac.new(b"key", b"data", hashlib.sha256).digest()

@pytest.mark.parametrize("algorithm", ["sha256", "sha512", "sha3_256", "blake2b_512", "sha256d", "shake128"])
def test_benchmark_returns_measured_fields(algorithm):
    result = engine.benchmark(algorithm, payload_bytes=64, iterations=20, output_bytes=32 if algorithm == "shake128" else None)
    assert result["iterations"] == 20
    assert result["hashes_per_second"] > 0
    assert result["mib_per_second"] >= 0
    assert result["measurement"].startswith("local microbenchmark")

def test_invalid_algorithm_rejected():
    with pytest.raises(CryptoInputError): engine.digest("made_up", b"x")

def test_input_and_output_limits():
    with pytest.raises(CryptoInputError): engine.digest("sha256", b"x" * (engine.MAX_INPUT_BYTES + 1))
    with pytest.raises(CryptoInputError): engine.digest("shake256", b"x", engine.MAX_OUTPUT_BYTES + 1)

def test_hash_api_and_benchmark_api():
    from nexus_master import app
    with TestClient(app) as client:
        assert client.get("/api/crypto/algorithms").status_code == 200
        h = client.post("/api/crypto/hash", json={"algorithm":"sha256", "data":"abc"})
        assert h.status_code == 200 and h.json()["digest_hex"] == hashlib.sha256(b"abc").hexdigest()
        b = client.post("/api/crypto/benchmark", json={"algorithm":"sha256", "payload_bytes":32, "iterations":10})
        assert b.status_code == 200 and b.json()["iterations"] == 10

def test_invalid_api_encoding_is_rejected():
    from nexus_master import app
    with TestClient(app) as client:
        r = client.post("/api/crypto/hash", json={"algorithm":"sha256", "data":"not hex", "encoding":"hex"})
        assert r.status_code == 400
