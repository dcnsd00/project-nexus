import json, sqlite3
from pathlib import Path
from tools_audit_vault import audit


def test_vault_audit_is_read_only_and_checks_envelope(tmp_path):
    db = tmp_path / "vault.db"
    c = sqlite3.connect(db)
    c.execute("CREATE TABLE vaults(id TEXT,label TEXT,address TEXT,keystore TEXT,created REAL)")
    c.execute("CREATE TABLE watch_addresses(id TEXT,label TEXT,network TEXT,address TEXT,created REAL)")
    env = {"v":1,"kdf":"scrypt-n32768-r8-p1","salt":"AAAAAAAAAAAAAAAAAAAAAA==","nonce":"AAAAAAAAAAAAAAAA","ciphertext":"AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"}
    c.execute("INSERT INTO vaults VALUES(?,?,?,?,?)",("id","test","0x"+"1"*40,json.dumps(env),0))
    c.commit(); c.close()
    before = db.read_bytes()
    result = audit(db)
    after = db.read_bytes()
    assert result["status"] == "PASS"
    assert result["valid_envelopes"] == 1 and result["decrypted"] is False
    assert result["modified"] is False and before == after


def test_vault_audit_flags_malformed_keystore(tmp_path):
    db = tmp_path / "bad.db"
    c = sqlite3.connect(db)
    c.execute("CREATE TABLE vaults(id TEXT,label TEXT,address TEXT,keystore TEXT,created REAL)")
    c.execute("INSERT INTO vaults VALUES('id','bad','0x' || printf('%040d',1),'not-json',0)")
    c.commit(); c.close()
    result = audit(db)
    assert result["status"] == "REVIEW" and result["invalid_envelopes"] == 1


def test_vault_audit_checks_encrypted_bitcoin_vault_without_decrypting(tmp_path):
    db = tmp_path / "bitcoin-vault.db"
    c = sqlite3.connect(db)
    c.execute("CREATE TABLE vaults(id TEXT,label TEXT,address TEXT,keystore TEXT,created REAL)")
    c.execute("CREATE TABLE watch_addresses(id TEXT,label TEXT,network TEXT,address TEXT,created REAL)")
    c.execute("CREATE TABLE bitcoin_vaults(id TEXT,label TEXT,address TEXT,compressed INTEGER,keystore TEXT,created REAL)")
    env = {"v":1,"kdf":"scrypt-n32768-r8-p1","salt":"AAAAAAAAAAAAAAAAAAAAAA==","nonce":"AAAAAAAAAAAAAAAA","ciphertext":"AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"}
    c.execute("INSERT INTO bitcoin_vaults VALUES(?,?,?,?,?,?)", ("btc1", "test", "1BoatSLRHtKNngkdXEeobR76b53LETtpyT", 1, json.dumps(env), 0))
    c.commit(); c.close()
    before = db.read_bytes()
    result = audit(db)
    assert result["status"] == "PASS"
    assert result["bitcoin_vault_count"] == 1
    assert result["valid_bitcoin_envelopes"] == 1
    assert result["decrypted"] is False and result["modified"] is False
    assert db.read_bytes() == before
