import os, sys, secrets
from pathlib import Path
from fastapi.testclient import TestClient
ROOT=Path(__file__).resolve().parents[1]
os.environ["NEXUS_DB"]="/tmp/nexus-final-36u7x9dk/core.db"
os.environ["NEXUS_WALLET_DB"]="/tmp/nexus-final-36u7x9dk/wallet.db"
sys.path.insert(0,str(ROOT))
from nexus_master import app

def test_wallet_status():
    with TestClient(app) as c:
        r=c.get("/api/wallet/status")
        assert r.status_code==200
        assert r.json()["public_chain_broadcast"] is False

def test_create_and_unlock_local_vault():
    with TestClient(app) as c:
        d=c.post("/api/wallet/vault/create",json={"label":"test","password":"Correct-Horse-77!Long"})
        assert d.status_code==200
        x=d.json()
        assert x["keystore_encrypted"] and not x["private_key_returned"]
        u=c.post("/api/wallet/vault/unlock",json={"wallet_id":x["wallet_id"],"password":"Correct-Horse-77!Long"})
        assert u.status_code==200 and u.json()["unlocked"]
        assert u.json()["broadcast_enabled"] is False

def test_wrong_password_rejected():
    with TestClient(app) as c:
        d=c.post("/api/wallet/vault/create",json={"label":"test2","password":"Correct-Horse-77!Long"}).json()
        u=c.post("/api/wallet/vault/unlock",json={"wallet_id":d["wallet_id"],"password":"Wrong-Horse-77!Long"})
        assert u.status_code==401

def test_watch_only_address_add_and_list():
    with TestClient(app) as c:
        addr="0x"+secrets.token_hex(20)
        d=c.post("/api/wallet/watch",json={"label":"watch","network":"BASE","address":addr})
        assert d.status_code==200
        assert any(x["address"]==addr for x in c.get("/api/wallet/watch").json())

def test_invalid_network_rejected():
    with TestClient(app) as c:
        d=c.post("/api/wallet/watch",json={"label":"watch","network":"MAINNET","address":"0x"+"b"*40})
        assert d.status_code==400

def test_wallet_page_served():
    with TestClient(app) as c:
        d=c.get("/wallet")
        assert d.status_code==200 and "NEXUS Wallet" in d.text

def test_wallet_schema_migrates_bitcoin_vault_table_at_app_startup(monkeypatch, tmp_path):
    import sqlite3
    import nexus_wallet_manager as wm
    db_path = tmp_path / 'wallet-startup.db'
    monkeypatch.setattr(wm, 'DB', db_path)
    with TestClient(app):
        assert db_path.exists()
        conn = sqlite3.connect(db_path)
        tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        conn.close()
    assert {'vaults', 'watch_addresses', 'bitcoin_vaults'} <= tables
