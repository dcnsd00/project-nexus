import os, sys, json, hashlib, secrets
from pathlib import Path
from fastapi.testclient import TestClient
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
ROOT=Path(__file__).resolve().parents[1]
os.environ["NEXUS_DB"]="/tmp/nexus-wallet-recovery-016-core.db"
os.environ["NEXUS_WALLET_DB"]="/tmp/nexus-wallet-recovery-016-wallet.db"
sys.path.insert(0,str(ROOT)); sys.path.insert(0,str(ROOT/"modules"/"wallet_benchmark"))
from nexus_master import app
from nexus_wallet_benchmark import keccak256, evm_address

PASSWORD=secrets.token_urlsafe(32)
def web3_fixture():
    private=(7).to_bytes(32,"big"); salt=b"s"*16; iv=b"i"*16
    derived=hashlib.pbkdf2_hmac("sha256",PASSWORD.encode(),salt,1000,32)
    enc=Cipher(algorithms.AES(derived[:16]),modes.CTR(iv)).encryptor()
    ciphertext=enc.update(private)+enc.finalize()
    from nexus_wallet_benchmark import private_to_public
    address=evm_address(7)
    obj={"version":3,"address":address[2:],"crypto":{"cipher":"aes-128-ctr",
      "cipherparams":{"iv":iv.hex()},"ciphertext":ciphertext.hex(),
      "kdf":"pbkdf2","kdfparams":{"dklen":32,"salt":salt.hex(),"c":1000,"prf":"hmac-sha256"},
      "mac":keccak256(derived[16:32]+ciphertext).hex()}}
    return obj,address

def test_recovery_formats_endpoint():
    with TestClient(app) as c:
        r=c.get("/api/wallet/recovery/formats")
        assert r.status_code==200
        ids={x["id"] for x in r.json()["formats"]}
        assert {"WEB3_SECRET_STORAGE_V3","BIP38_0142","BIP39","NEXUS_AESGCM_V1"} <= ids

def test_detect_web3_format():
    obj,_=web3_fixture()
    with TestClient(app) as c:
        r=c.post("/api/wallet/recovery/detect",json={"payload":obj})
        assert r.status_code==200 and r.json()["format"]=="WEB3_SECRET_STORAGE_V3"

def test_web3_decrypt_import_reencrypts_without_key_export():
    obj,address=web3_fixture()
    vault_password=secrets.token_urlsafe(32)
    with TestClient(app) as c:
        r=c.post("/api/wallet/recovery/decrypt",json={"format":"WEB3_SECRET_STORAGE_V3","payload":obj,
          "password":PASSWORD,"vault_password":vault_password,"owner_authorized":True})
        assert r.status_code==200
        data=r.json(); assert data["address"]==address and data["re_encrypted_in_nexus_vault"]
        assert data["private_key_returned"] is False
        u=c.post("/api/wallet/vault/unlock",json={"wallet_id":data["wallet_id"],"password":vault_password})
        assert u.status_code==200 and u.json()["address"]==address

def test_web3_wrong_password_and_missing_authorization_rejected():
    obj,_=web3_fixture()
    with TestClient(app) as c:
        bad=c.post("/api/wallet/recovery/decrypt",json={"format":"WEB3_SECRET_STORAGE_V3","payload":obj,
          "password":"wrong-password","owner_authorized":True})
        assert bad.status_code==401
        noauth=c.post("/api/wallet/recovery/decrypt",json={"format":"WEB3_SECRET_STORAGE_V3","payload":obj,
          "password":PASSWORD,"owner_authorized":False})
        assert noauth.status_code==403

def test_unsupported_format_does_not_decrypt():
    with TestClient(app) as c:
        r=c.post("/api/wallet/recovery/decrypt",json={"format":"ELECTRUM_WALLET","payload":{},
          "password":PASSWORD,"owner_authorized":True})
        assert r.status_code==400

def test_local_wallet_search_detects_candidate_files(tmp_path):
    (tmp_path/"UTC--sample.json").write_text(json.dumps({"version":3,"crypto":{}}))
    (tmp_path/"notes.md").write_text("not a wallet")
    from nexus_wallet_search import search_wallet_files
    result=search_wallet_files(str(tmp_path))
    assert result["scanned_files"]==1
    assert result["results"][0]["format"]=="WEB3_SECRET_STORAGE_V3"

def test_search_endpoint_loopback_and_metadata_only(tmp_path):
    (tmp_path/"wallet.json").write_text(json.dumps({"version":3,"crypto":{}}))
    with TestClient(app) as c:
        r=c.post("/api/wallet/recovery/search",json={"root":str(tmp_path)})
        assert r.status_code==200 and r.json()["decryption_attempted"] is False

def bip38_fixture():
    from nexus_wallet_formats import _p2pkh_address
    from nexus_wallet_benchmark import base58check
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    import unicodedata
    from nexus_wallet_benchmark import SECP256K1_N
    scalar = secrets.randbelow(SECP256K1_N - 1) + 1
    secret=scalar.to_bytes(32,"big"); password="BIP38-Owner-Test"
    address=_p2pkh_address(secret,True)
    address_hash=hashlib.sha256(hashlib.sha256(address.encode("ascii")).digest()).digest()[:4]
    derived=hashlib.scrypt(unicodedata.normalize("NFC",password).encode(),salt=address_hash,
                           n=16384,r=8,p=8,dklen=64,maxmem=128*1024*1024)
    clear=bytes(a^b for a,b in zip(secret,derived[:32]))
    enc=Cipher(algorithms.AES(derived[32:]),modes.ECB()).encryptor()
    ciphertext=enc.update(clear[:16])+enc.update(clear[16:])+enc.finalize()
    return base58check(b"\x01\x42\xe0"+address_hash+ciphertext),password,address

def test_bip38_non_ec_decrypt_and_address_validation_without_key_export():
    encrypted,password,address=bip38_fixture()
    with TestClient(app) as c:
        r=c.post("/api/wallet/recovery/decrypt",json={"format":"BIP38_0142","payload":encrypted,
          "password":password,"owner_authorized":True})
        assert r.status_code==200
        d=r.json(); assert d["address"]==address and d["address_match"]=="ADDRESS_MATCH"
        assert d["private_key_returned"] is False and d["wif_returned"] is False


def test_bip38_imports_into_encrypted_bitcoin_vault_without_key_export():
    encrypted, password, address = bip38_fixture()
    vault_password = secrets.token_urlsafe(32)
    with TestClient(app) as c:
        imported = c.post("/api/wallet/recovery/import-bip38", json={
            "encrypted_key": encrypted, "password": password,
            "vault_password": vault_password, "owner_authorized": True
        })
        assert imported.status_code == 200, imported.text
        data = imported.json()
        assert data["address"] == address
        assert data["encrypted_in_nexus_bitcoin_vault"] is True
        assert data["private_key_returned"] is False
        assert data["wif_returned"] is False
        assert any(x["id"] == data["wallet_id"] for x in c.get("/api/wallet/bitcoin/vaults").json())
        opened = c.post("/api/wallet/bitcoin/vault/unlock", json={
            "wallet_id": data["wallet_id"], "password": vault_password
        })
        assert opened.status_code == 200, opened.text
        assert opened.json()["address"] == address
        assert opened.json()["private_key_returned"] is False


def test_bip38_import_wrong_password_or_missing_authorization_rejected():
    encrypted, password, _ = bip38_fixture()
    with TestClient(app) as c:
        bad = c.post("/api/wallet/recovery/import-bip38", json={
            "encrypted_key": encrypted, "password": "not-the-wallet-password",
            "vault_password": secrets.token_urlsafe(32), "owner_authorized": True
        })
        assert bad.status_code == 401
        noauth = c.post("/api/wallet/recovery/import-bip38", json={
            "encrypted_key": encrypted, "password": password,
            "vault_password": secrets.token_urlsafe(32), "owner_authorized": False
        })
        assert noauth.status_code == 403


def test_wallet_search_does_not_mistake_generic_dat_for_bitcoin_core(tmp_path):
    (tmp_path / "unrelated.dat").write_bytes(b"not a bitcoin core wallet")
    (tmp_path / "wallet.dat").write_bytes(b"candidate only")
    old_json = tmp_path / "old-keystore.json"
    old_json.write_text(json.dumps({"version": 3, "crypto": {}}))
    from nexus_wallet_search import search_wallet_files
    result = search_wallet_files(str(tmp_path), now_ts=2_000_000_000)
    by_name = {x["name"]: x for x in result["results"]}
    assert "unrelated.dat" not in by_name
    assert by_name["wallet.dat"]["format"] == "BITCOIN_CORE_WALLET_CANDIDATE"
    assert by_name["wallet.dat"]["status"] == "CANDIDATE_UNVERIFIED"
    assert by_name["old-keystore.json"]["format"] == "WEB3_SECRET_STORAGE_V3"
    assert by_name["old-keystore.json"]["file_age_is_not_chain_inactivity"] is True
    assert result["private_keys_extracted"] is False


def test_wallet_search_detects_bip38_candidate_without_decrypting(tmp_path):
    encrypted, _, _ = bip38_fixture()
    (tmp_path / "old-backup.txt").write_text("backup key: " + encrypted)
    from nexus_wallet_search import search_wallet_files
    result = search_wallet_files(str(tmp_path))
    assert result["candidate_count"] == 1
    assert result["results"][0]["format"] == "BITCOIN_BIP38_0142_OR_0143_CANDIDATE"
    assert result["results"][0]["decryption_attempted"] is False


def test_bitcoin_core_inspector_reports_8_to_10_year_inactivity_from_wallet_history(monkeypatch):
    import json as _json
    import nexus_wallet_formats as formats
    from datetime import datetime, timezone
    last_tx = int(datetime(2017, 6, 1, tzinfo=timezone.utc).timestamp())
    now = int(datetime(2026, 11, 10, tzinfo=timezone.utc).timestamp())
    calls = []

    class FakeResponse:
        def __init__(self, payload):
            self.payload = _json.dumps({"result": payload, "error": None}).encode()
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def read(self, limit=-1): return self.payload if limit < 0 else self.payload[:limit]

    def fake_urlopen(request, timeout=5):
        body = _json.loads(request.data.decode())
        method = body["method"]
        calls.append((method, body["params"]))
        if method == "getwalletinfo":
            result = {"walletname":"owner-backup","walletversion":169900,"descriptors":True,
                      "private_keys_enabled":True,"txcount":1}
        elif method == "getbalances":
            result = {"mine":{"trusted":0.25,"untrusted_pending":0,"immature":0}}
        elif method == "listaddressgroupings":
            result = [[ ["1BoatSLRHtKNngkdXEeobR76b53LETtpyT", 0.25, "owner" ] ]]
        elif method == "listtransactions":
            offset = body["params"][2]
            result = ([{"txid":"ab"*32,"time":last_tx,"category":"receive",
                        "amount":0.25,"confirmations":1000,"address":"1BoatSLRHtKNngkdXEeobR76b53LETtpyT"}]
                      if offset == 0 else [])
        else:
            raise AssertionError("unexpected RPC method: " + method)
        return FakeResponse(result)

    monkeypatch.setattr(formats, "urlopen", fake_urlopen)
    data = formats.bitcoin_core_inspect_wallet(
        "http://127.0.0.1:18443", "user", "rpc-pass", "owner-backup",
        owner_authorized=True, now_ts=now)
    assert data["activity_classification"] == "INACTIVE_8_TO_10_YEARS"
    assert 8 < data["inactive_years"] < 10
    assert data["balances_btc"]["trusted"] == "0.25"
    assert data["last_transaction_at"] == last_tx
    assert data["private_keys_read"] is False
    assert data["transaction_broadcast"] is False
    assert calls[-1][0] == "listtransactions"


def test_bitcoin_core_no_history_requires_rescan_caveat(monkeypatch):
    import json as _json
    import nexus_wallet_formats as formats
    from datetime import datetime, timezone
    now = int(datetime(2026, 11, 10, tzinfo=timezone.utc).timestamp())

    class FakeResponse:
        def __init__(self, payload):
            self.payload = _json.dumps({"result": payload, "error": None}).encode()
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def read(self, limit=-1): return self.payload if limit < 0 else self.payload[:limit]

    def fake_urlopen(request, timeout=5):
        method = _json.loads(request.data.decode())["method"]
        if method == "getwalletinfo": result = {"walletname":"old-backup","txcount":0}
        elif method == "getbalances": result = {"mine":{"trusted":0,"untrusted_pending":0,"immature":0}}
        elif method == "listaddressgroupings": result = []
        elif method == "listtransactions": result = []
        else: raise AssertionError(method)
        return FakeResponse(result)

    monkeypatch.setattr(formats, "urlopen", fake_urlopen)
    data = formats.bitcoin_core_inspect_wallet(
        "http://127.0.0.1:18443", "user", "rpc-pass", "old-backup",
        owner_authorized=True, now_ts=now)
    assert data["activity_classification"] == "NO_TRANSACTION_HISTORY"
    assert data["rescan_required_to_confirm_no_history"] is True
    assert "rescan/reindex" in data["history_completeness_note"]


def test_bitcoin_core_password_check_relocks_wallet(monkeypatch):
    import json as _json
    import nexus_wallet_formats as formats
    called = []

    class FakeResponse:
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def read(self, limit=-1): return b'{"result":true,"error":null}'

    def fake_urlopen(request, timeout=5):
        method = _json.loads(request.data.decode())["method"]
        called.append(method)
        return FakeResponse()

    monkeypatch.setattr(formats, "urlopen", fake_urlopen)
    result = formats.bitcoin_core_check_wallet_passphrase(
        "http://127.0.0.1:18443", "user", "rpc-pass", "owner-wallet",
        "correct local password", owner_authorized=True)
    assert called == ["walletpassphrase", "walletlock"]
    assert result["password_verified"] is True
    assert result["wallet_relocked_after_check"] is True
    assert result["currently_unlocked"] is False


def test_bitcoin_core_password_check_does_not_claim_success_if_relock_fails(monkeypatch):
    import json as _json
    import nexus_wallet_formats as formats

    class FakeResponse:
        def __init__(self, payload): self.payload = _json.dumps(payload).encode()
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def read(self, limit=-1): return self.payload if limit < 0 else self.payload[:limit]

    def fake_urlopen(request, timeout=5):
        method = _json.loads(request.data.decode())["method"]
        if method == "walletpassphrase":
            return FakeResponse({"result": True, "error": None})
        return FakeResponse({"result": None, "error": {"message": "walletlock failure"}})

    monkeypatch.setattr(formats, "urlopen", fake_urlopen)
    try:
        formats.bitcoin_core_check_wallet_passphrase(
            "http://127.0.0.1:18443", "user", "rpc-pass", "owner-wallet",
            "correct local password", owner_authorized=True)
    except formats.WalletFormatError as exc:
        assert "could not relock" in str(exc)
    else:
        raise AssertionError("NEXUS must not report success when walletlock fails")


def test_nexus_aesgcm_keystore_decrypt_maps_wrong_password_to_401_without_key_export():
    from nexus_wallet_manager import _encrypt_secret
    password = secrets.token_urlsafe(24)
    address = evm_address(7)
    keystore = json.loads(_encrypt_secret((7).to_bytes(32, "big"), password))
    payload = {"keystore": keystore, "address": address}

    with TestClient(app) as c:
        wrong = c.post("/api/wallet/recovery/decrypt", json={
            "format": "NEXUS_AESGCM_V1", "payload": payload,
            "password": "wrong-password", "owner_authorized": True,
        })
        assert wrong.status_code == 401
        assert "PASSWORD_INVALID" in wrong.json()["detail"]

        opened = c.post("/api/wallet/recovery/decrypt", json={
            "format": "NEXUS_AESGCM_V1", "payload": payload,
            "password": password, "owner_authorized": True,
        })
        assert opened.status_code == 200, opened.text
        data = opened.json()
        assert data["status"] == "DECRYPTION_SUCCESS"
        assert data["address"] == address
        assert data["address_match"] == "ADDRESS_MATCH"
        assert data["private_key_returned"] is False
        assert data["re_encrypted_in_nexus_vault"] is False


def test_bip39_checksum_and_one_missing_word_api_returns_only_missing_word():
    from mnemonic import Mnemonic
    from nexus_wallet_benchmark import bip39_seed, derive_path, make_path
    wordlist = Mnemonic("english").wordlist
    phrase = "abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon about"
    seed = bip39_seed(phrase, "")
    address = evm_address(derive_path(seed, make_path("EVM_ETHEREUM", 0)))
    with TestClient(app) as c:
        checked = c.post("/api/wallet/recovery/bip39/check", json={
            "mnemonic": phrase, "language": "english", "owner_authorized": True
        })
        assert checked.status_code == 200, checked.text
        assert checked.json()["mnemonic_checksum_valid"] is True
        assert checked.json()["seed_exported"] is False

        partial = " ".join(phrase.split()[:-1] + ["?"])
        recovered = c.post("/api/wallet/recovery/bip39/one-missing", json={
            "partial_mnemonic": partial, "expected_address": address,
            "format": "EVM_ETHEREUM", "language": "english",
            "passphrase": "", "address_index": 0, "owner_authorized": True
        })
        assert recovered.status_code == 200, recovered.text
        body = recovered.json()
        assert body["status"] == "ADDRESS_MATCH"
        assert body["match_count"] == 1
        assert body["matches"][0]["recovered_word"] == "about"
        assert body["mnemonic_exported"] is False
        assert "mnemonic" not in body["matches"][0]


def test_solana_keypair_validation_api_checks_public_half_without_export():
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives import serialization
    from nexus_wallet_benchmark import base58_encode
    seed = bytes(range(32))
    public = Ed25519PrivateKey.from_private_bytes(seed).public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw
    )
    keypair = list(seed + public)
    with TestClient(app) as c:
        valid = c.post("/api/wallet/recovery/solana/validate", json={"payload": keypair})
        assert valid.status_code == 200, valid.text
        body = valid.json()
        assert body["valid"] is True
        assert body["address"] == base58_encode(public)
        assert body["private_key_returned"] is False

        keypair[-1] ^= 1
        invalid = c.post("/api/wallet/recovery/solana/validate", json={"payload": keypair})
        assert invalid.status_code == 422


def test_wallet_page_exposes_bip39_and_solana_tools_without_persisting_inputs():
    with TestClient(app) as c:
        page = c.get("/wallet")
        assert page.status_code == 200
        assert 'id="bip39Phrase"' in page.text
        assert 'id="bip39Partial"' in page.text
        assert 'id="solanaKeypairFile"' in page.text
        assert "function recoverBip39Missing()" in page.text
        assert "function validateSolanaKeypair()" in page.text
