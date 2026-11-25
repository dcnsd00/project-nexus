"""Integrated RCSC service: read-only Bitcoin collection, validation and analysis."""
from __future__ import annotations
import json, os, sqlite3, threading, uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from modules.data_paths import data_path

ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / "research" / "rcsc" / "nexus_rcsc"
import sys
if str(PKG) not in sys.path:
    sys.path.insert(0, str(PKG))
from nexus_rcsc.bitcoin import parse_header, subsidy_sats, verify_merkle_root
from nexus_rcsc.collector import MempoolClient
from nexus_rcsc.analysis import analyze
from nexus_rcsc.associations import reward_conditioned_nonce_tests

DB_PATH = Path(os.environ.get("NEXUS_RCSC_DB", str(data_path("db", "nexus_rcsc.sqlite3")))).expanduser().resolve()
_LOCK = threading.RLock()
HOLDOUT_MINIMUM_RECORDS = 200

def _connect():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(DB_PATH, timeout=30, isolation_level="DEFERRED")
    db.execute("PRAGMA busy_timeout=30000")
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA synchronous=FULL")
    db.execute("CREATE TABLE IF NOT EXISTS blocks (height INTEGER PRIMARY KEY, block_hash TEXT UNIQUE NOT NULL, collected_utc TEXT NOT NULL, record_json TEXT NOT NULL)")
    db.execute("CREATE TABLE IF NOT EXISTS runs (run_id TEXT PRIMARY KEY, created_utc TEXT NOT NULL, kind TEXT NOT NULL, payload_json TEXT NOT NULL)")
    return db

@contextmanager
def _database():
    """Commit or roll back one unit of work and always close its SQLite handle."""
    db = _connect()
    try:
        with db:
            yield db
    finally:
        db.close()

def status() -> dict[str, Any]:
    with _database() as db:
        blocks = db.execute("SELECT COUNT(*) FROM blocks").fetchone()[0]
        runs = db.execute("SELECT COUNT(*) FROM runs").fetchone()[0]
    return {"module":"RCSC - SHA256 Structure Research Engine", "integrated":True,
            "database":str(DB_PATH.relative_to(ROOT)) if DB_PATH.is_relative_to(ROOT) else str(DB_PATH),
            "stored_blocks":blocks,"stored_runs":runs,
            "capabilities":{"public_block_collection":True,"header_sha256d_pow_validation":True,
             "coinbase_subsidy":True,"full_txid_merkle_rebuild":True,"exact_fee_sum_from_tx_pages":True,
             "nonce_hex_byte_analysis":True,"reward_nonce_association":True,
             "chronological_holdout":True,"holdout_minimum_records":HOLDOUT_MINIMUM_RECORDS,
             "stored_chain_anchor_verification":True,"automatic_common_ancestor_recovery":True},
            "network_policy":"Read-only public block data; no wallet secrets, transactions or mining actions.",
            "limitations":["Statistical associations are exploratory, not predictions.","Provider data must be independently replicated before strong conclusions."]}

def _save(kind: str, payload: dict[str, Any]) -> str:
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S") + "_" + uuid.uuid4().hex[:10]
    with _database() as db:
        db.execute("INSERT INTO runs VALUES (?,?,?,?)", (run_id, datetime.now(timezone.utc).isoformat(), kind, json.dumps(payload, ensure_ascii=False)))
    return run_id

def _record_is_analysis_eligible(record: dict[str, Any]) -> bool:
    """Only persist blocks with a self-consistent PoW header on the best chain."""
    return (
        isinstance(record.get("height"), int) and not isinstance(record.get("height"), bool)
        and record.get("pow_valid") is True
        and record.get("reported_hash_matches_header") is True
        and record.get("reported_fields_match_header") is True
        and record.get("in_best_chain") is True
        and not record.get("collection_error")
    )

def collect(count: int = 10, start_height: int | None = None, base_url: str | None = None) -> dict[str, Any]:
    if isinstance(count, bool) or not isinstance(count, int) or not 1 <= count <= 200:
        raise ValueError("count trebuie să fie între 1 și 200 pentru colectare API")
    if start_height is not None and (isinstance(start_height, bool) or not isinstance(start_height, int) or start_height < 0):
        raise ValueError("start_height trebuie să fie un întreg nenegativ sau None")
    client = MempoolClient(base_url=base_url or "https://mempool.space/api")
    records = client.fetch_recent(count=count, start_height=start_height)
    eligible = [record for record in records if _record_is_analysis_eligible(record)]
    rejected = len(records) - len(eligible)
    # Never persist a batch whose records do not form one contiguous parent chain.
    ordered = sorted(eligible, key=lambda item: item["height"])
    broken_links = []
    for previous, current in zip(ordered, ordered[1:]):
        if current.get("height") != previous.get("height") + 1 or current.get("previous_block_hash_reported") != previous.get("block_hash_reported"):
            broken_links.append({"height": current.get("height"), "expected_parent": previous.get("block_hash_reported"),
                                 "reported_parent": current.get("previous_block_hash_reported")})
    if broken_links:
        rejected += len(eligible)
        eligible = []
        ordered = []
    inserted = 0
    reorg_from_height = None
    anchor_height = ordered[0]["height"] - 1 if ordered else None
    anchor_hash_expected = ordered[0].get("previous_block_hash_reported") if ordered else None
    anchor_hash_stored = None
    anchor_verified = True
    anchor_mismatch = None
    common_ancestor_height = None
    recovery_attempts = 0
    recovery_status = "not_needed"
    with _LOCK, _connect() as db:
        # Anchor a partial collection window to the already persisted chain.
        # If the parent immediately below the window disagrees, the common
        # ancestor is outside this window: fail closed and require deeper overlap.
        if ordered and anchor_height >= 0:
            anchor = db.execute("SELECT block_hash FROM blocks WHERE height=?", (anchor_height,)).fetchone()
            if anchor:
                anchor_hash_stored = anchor[0]
                anchor_verified = anchor_hash_stored == anchor_hash_expected
                if not anchor_verified:
                    anchor_mismatch = {"height": anchor_height, "stored_hash": anchor_hash_stored,
                                       "collected_parent_hash": anchor_hash_expected}
                    recovery_status = "searching_common_ancestor"
                    # Expand the overlap backwards in bounded steps. A candidate
                    # fork is accepted only after a stored block hash is found
                    # again and every block from that ancestor to the new tip is
                    # independently eligible and parent-linked.
                    requested = max(2, min(200, count * 2))
                    recovered = False
                    # Preserve the original tip window: the backward overlap request
                    # starts at anchor_height and therefore may not include newer blocks.
                    original_window = list(ordered)
                    while requested <= 200 and not recovered:
                        recovery_attempts += 1
                        try:
                            expanded = client.fetch_recent(count=requested, start_height=anchor_height)
                        except Exception:
                            expanded = []
                        expanded_eligible = [r for r in expanded if _record_is_analysis_eligible(r)]
                        # Merge historical overlap with the original newer window.
                        # Original-window records take precedence at equal heights.
                        merged_by_height = {r["height"]: r for r in expanded_eligible}
                        merged_by_height.update({r["height"]: r for r in original_window})
                        expanded_ordered = [merged_by_height[h] for h in sorted(merged_by_height)]
                        stored_hashes = {h: bh for h, bh in db.execute(
                            "SELECT height, block_hash FROM blocks WHERE height <= ? ORDER BY height",
                            (anchor_height,)).fetchall()}
                        shared = [r for r in expanded_ordered
                                  if r["height"] <= anchor_height
                                  and stored_hashes.get(r["height"]) == r.get("block_hash_reported")]
                        if shared:
                            ancestor = max(shared, key=lambda item: item["height"])
                            candidate = [r for r in expanded_ordered if r["height"] > ancestor["height"]]
                            chain_ok = bool(candidate)
                            previous_record = ancestor
                            for current_record in candidate:
                                if (current_record["height"] != previous_record["height"] + 1
                                    or current_record.get("previous_block_hash_reported") != previous_record.get("block_hash_reported")):
                                    chain_ok = False
                                    break
                                previous_record = current_record
                            if chain_ok:
                                common_ancestor_height = ancestor["height"]
                                ordered = candidate
                                reorg_from_height = common_ancestor_height + 1
                                recovery_status = "common_ancestor_found"
                                recovered = True
                        if not recovered:
                            if requested == 200:
                                break
                            requested = min(200, requested * 2)
                    if not recovered:
                        rejected += len(eligible)
                        ordered = []
                        recovery_status = "common_ancestor_not_found_fail_closed"
        # Detect the earliest height whose canonical hash differs from the stored hash.
        for record in ordered:
            existing = db.execute("SELECT block_hash FROM blocks WHERE height=?", (record["height"],)).fetchone()
            if existing and existing[0] != record["block_hash_reported"]:
                reorg_from_height = record["height"] if reorg_from_height is None else min(reorg_from_height, record["height"])
        # A changed block invalidates every stored descendant until recollected from
        # the canonical provider chain. Delete and replace atomically in this transaction.
        if reorg_from_height is not None:
            db.execute("DELETE FROM blocks WHERE height >= ?", (reorg_from_height,))
        for record in ordered:
            block_hash = record["block_hash_reported"]
            db.execute("INSERT INTO blocks(height,block_hash,collected_utc,record_json) VALUES(?,?,?,?) ON CONFLICT(height) DO UPDATE SET block_hash=excluded.block_hash,collected_utc=excluded.collected_utc,record_json=excluded.record_json",
                       (record["height"], block_hash, datetime.now(timezone.utc).isoformat(), json.dumps(record)))
            inserted += 1
    run_id = _save("collection", {"requested":count,"returned":len(records),"records_saved":inserted,"records_rejected":rejected,
                                   "reorg_detected":reorg_from_height is not None,"reorg_from_height":reorg_from_height,
                                   "anchor_verified":anchor_verified,"anchor_height":anchor_height,
                                   "anchor_mismatch":anchor_mismatch,"common_ancestor_height":common_ancestor_height,
                                   "recovery_attempts":recovery_attempts,"recovery_status":recovery_status,
                                   "broken_chain_links":broken_links})
    return {"run_id":run_id,"requested":count,"returned":len(records),"records_saved":inserted,
            "records_rejected":rejected,"reorg_detected":reorg_from_height is not None,
            "reorg_from_height":reorg_from_height,"anchor_verified":anchor_verified,
            "anchor_height":anchor_height,"anchor_mismatch":anchor_mismatch,
            "common_ancestor_height":common_ancestor_height,"recovery_attempts":recovery_attempts,
            "recovery_status":recovery_status,"broken_chain_links":broken_links,
            "verified_pow":sum(r.get("pow_valid") is True and r.get("reported_hash_matches_header") is True for r in eligible),
            "merkle_verified":sum(r.get("merkle_root_valid") is True for r in eligible),
            "fee_complete":sum(r.get("fees_complete") is True for r in eligible),
            "records_with_errors":sum(bool(r.get("collection_error")) for r in records),"records":records}

def stored_records(limit: int = 1000) -> list[dict[str, Any]]:
    if not 1 <= limit <= 5000: raise ValueError("limit trebuie să fie 1..5000")
    with _database() as db:
        rows = db.execute("SELECT record_json FROM blocks ORDER BY height DESC LIMIT ?", (limit,)).fetchall()
    return [json.loads(row[0]) for row in rows]

def run_analysis(limit: int = 1000) -> dict[str, Any]:
    records = stored_records(limit)
    result = analyze(records)
    result["merkle_verified_count"] = sum(r.get("merkle_root_valid") is True for r in records)
    result["fee_complete_count"] = sum(r.get("fees_complete") is True for r in records)
    result["fee_total_sats_mean"] = (sum(r["transaction_fees_sats"] for r in records if r.get("fees_complete")) / max(1,sum(r.get("fees_complete") is True for r in records))) if any(r.get("fees_complete") for r in records) else None
    ordered = sorted((r for r in records if isinstance(r.get("height"), int)), key=lambda r: int(r["height"]))
    cut = int(len(ordered) * 0.70)
    train, holdout = ordered[:cut], ordered[cut:]
    result["chronological_holdout"] = {
        "status": "evaluated" if len(holdout) >= HOLDOUT_MINIMUM_RECORDS else "insufficient_data",
        "minimum_holdout_records": HOLDOUT_MINIMUM_RECORDS,
        "actual_holdout_records": len(holdout),
        "split": "first 70% of heights=train; latest 30%=holdout",
        "train_height_range": [train[0]["height"], train[-1]["height"]] if train else None,
        "holdout_height_range": [holdout[0]["height"], holdout[-1]["height"]] if holdout else None,
        "train_association_screen": reward_conditioned_nonce_tests(train, permutations=499, min_stratum_size=30),
        "holdout_association_screen": reward_conditioned_nonce_tests(holdout, permutations=499, min_stratum_size=30),
        "independent_replication": "not performed; same public source and same collected dataset"
    }
    result["validation_design"] = {"chronological_holdout":True,"independent_replication":False,
       "warning":"Holdout association is exploratory. It is not a prediction model or proof of SHA-256 weakness."}
    run_id = _save("analysis", result)
    return {"run_id":run_id,"result":result}

def verify_header(header_hex: str) -> dict[str, Any]:
    parsed = parse_header(header_hex)
    parsed["nonce_binary"] = format(parsed["nonce"], "032b")
    parsed["nonce_bytes_le_hex"] = bytes.fromhex(header_hex)[76:80].hex()
    return parsed

def get_run(run_id: str) -> dict[str, Any] | None:
    with _database() as db:
        row = db.execute("SELECT created_utc,kind,payload_json FROM runs WHERE run_id=?", (run_id,)).fetchone()
    return {"run_id":run_id,"created_utc":row[0],"kind":row[1],"payload":json.loads(row[2])} if row else None
