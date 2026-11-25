"""Read-only structural audit for NEXUS local vault databases.
Never decrypts, exports, prints or modifies key material."""
from __future__ import annotations
import json, re, sqlite3, sys
from pathlib import Path

EXPECTED = {"v", "kdf", "salt", "nonce", "ciphertext"}
ADDRESS = re.compile(r"^0x[0-9a-fA-F]{40}$")
BTC_P2PKH = re.compile(r"^1[1-9A-HJ-NP-Za-km-z]{25,34}$")


def _valid_envelope(blob: str) -> bool:
    try:
        env = json.loads(blob)
        return (set(env) == EXPECTED and env.get("v") == 1 and
                env.get("kdf") == "scrypt-n32768-r8-p1" and
                len(__import__('base64').b64decode(env["salt"], validate=True)) == 16 and
                len(__import__('base64').b64decode(env["nonce"], validate=True)) == 12 and
                len(__import__('base64').b64decode(env["ciphertext"], validate=True)) >= 48)
    except Exception:
        return False


def audit(path: str | Path) -> dict:
    p = Path(path)
    if not p.exists():
        return {"path": str(p), "exists": False, "status": "MISSING"}
    db = sqlite3.connect(f"file:{p.resolve()}?mode=ro", uri=True)
    db.row_factory = sqlite3.Row
    try:
        integrity = db.execute("PRAGMA integrity_check").fetchone()[0]
        tables = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        result = {"path": str(p), "exists": True, "integrity": integrity,
                  "vault_table_present": "vaults" in tables,
                  "watch_table_present": "watch_addresses" in tables,
                  "vault_count": 0, "watch_count": 0, "valid_envelopes": 0,
                  "invalid_envelopes": 0, "bitcoin_vault_table_present": "bitcoin_vaults" in tables,
                  "bitcoin_vault_count": 0, "valid_bitcoin_envelopes": 0,
                  "invalid_bitcoin_envelopes": 0, "plaintext_key_fields_present": False,
                  "decrypted": False, "modified": False}
        if "vaults" in tables:
            cols = {r[1] for r in db.execute('PRAGMA table_info("vaults")')}
            result["plaintext_key_fields_present"] = bool(cols & {"private_key", "seed_phrase", "mnemonic", "secret"})
            for row in db.execute("SELECT address, keystore FROM vaults"):
                result["vault_count"] += 1
                ok = _valid_envelope(row["keystore"]) and bool(ADDRESS.fullmatch(row["address"]))
                result["valid_envelopes" if ok else "invalid_envelopes"] += 1
        if "watch_addresses" in tables:
            result["watch_count"] = db.execute("SELECT count(*) FROM watch_addresses").fetchone()[0]
        if "bitcoin_vaults" in tables:
            btc_cols = {r[1] for r in db.execute('PRAGMA table_info("bitcoin_vaults")')}
            result["plaintext_key_fields_present"] = result["plaintext_key_fields_present"] or bool(
                btc_cols & {"private_key", "seed_phrase", "mnemonic", "secret", "wif"})
            for row in db.execute("SELECT address, keystore FROM bitcoin_vaults"):
                result["bitcoin_vault_count"] += 1
                ok = _valid_envelope(row["keystore"]) and bool(BTC_P2PKH.fullmatch(row["address"]))
                result["valid_bitcoin_envelopes" if ok else "invalid_bitcoin_envelopes"] += 1
        result["status"] = "PASS" if (integrity == "ok" and
            result["invalid_envelopes"] == 0 and result["invalid_bitcoin_envelopes"] == 0 and
            not result["plaintext_key_fields_present"]) else "REVIEW"
        return result
    finally:
        db.close()

if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("database")
    args = ap.parse_args()
    out = audit(args.database)
    print(json.dumps(out, indent=2))
    sys.exit(0 if out.get("status") == "PASS" else 1)
