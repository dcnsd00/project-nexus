from modules import rcsc_service as rcsc
from pathlib import Path
import tempfile

GENESIS_HEADER = (
    "01000000" + "00"*32 +
    "3ba3edfd7a7b12b27ac72c3e67768f617fc81bc3888a51323a9fb8aa4b1e5e4a" +
    "29ab5f49" + "ffff001d" + "1dac2b7c"
)
GENESIS_TXID = "4a5e1e4baab89f3a32518a88c31bc87f618f76673e2cc77ab2127b7afdeda33b"

def test_genesis_header_pow_and_fields():
    parsed = rcsc.verify_header(GENESIS_HEADER)
    assert parsed["nonce"] == 2083236893
    assert parsed["pow_valid"] is True
    assert parsed["block_hash"] == "000000000019d6689c085ae165831e934ff763ae46a2a6c172b3f1b60a8ce26f"
    assert parsed["nonce_binary"] == format(2083236893, "032b")

def test_genesis_merkle_root():
    from nexus_rcsc.bitcoin import verify_merkle_root
    result = verify_merkle_root(GENESIS_TXID, [GENESIS_TXID])
    assert result["merkle_root_valid"] is True

def test_subsidy_halving():
    from nexus_rcsc.bitcoin import subsidy_sats
    assert subsidy_sats(0) == 5_000_000_000
    assert subsidy_sats(210_000) == 2_500_000_000
    assert subsidy_sats(840_000) == 312_500_000

def test_rcsc_api_routes_registered():
    import nexus_master
    paths = set(nexus_master.app.openapi()["paths"])
    assert "/api/research/rcsc/status" in paths
    assert "/api/research/rcsc/collect" in paths
    assert "/api/research/rcsc/analyze" in paths
    assert "/api/research/rcsc/verify-header" in paths


def test_rcsc_api_status_and_header_endpoint():
    from fastapi.testclient import TestClient
    import nexus_master
    client = TestClient(nexus_master.app)
    status = client.get("/api/research/rcsc/status")
    assert status.status_code == 200
    assert status.json()["integrated"] is True
    verified = client.post("/api/research/rcsc/verify-header", json={"header_hex": GENESIS_HEADER})
    assert verified.status_code == 200
    assert verified.json()["pow_valid"] is True

def test_collector_rebuilds_merkle_and_separates_fees():
    from nexus_rcsc.collector import MempoolClient
    class FixtureClient(MempoolClient):
        def __init__(self):
            super().__init__(base_url="https://fixture.invalid", pause_seconds=0)
        def get_text(self, path):
            if path == "blocks/tip/height": return "0"
            if path.endswith("/header"): return GENESIS_HEADER
            if path.endswith("/txid/0"): return GENESIS_TXID
            raise AssertionError(path)
        def get_json(self, path):
            if path == "blocks/0":
                return [{"height":0,"id":"000000000019d6689c085ae165831e934ff763ae46a2a6c172b3f1b60a8ce26f","timestamp":1231006505,"version":1,"merkle_root":GENESIS_TXID,"previousblockhash":"00"*32,"nonce":2083236893,"bits":486604799,"difficulty":1.0,"tx_count":1,"size":285,"weight":1140}]
            if path.endswith("/status"): return {"in_best_chain":True}
            if path.startswith("tx/"): return {"vout":[{"value":5_000_000_000}],"vin":[{"scriptsig":"04ffff001d","scriptsig_asm":"coinbase","witness":[],"is_coinbase":True}]}
            if path.endswith("/txids"): return [GENESIS_TXID]
            if path.endswith("/txs/0"): return [{"txid":GENESIS_TXID,"fee":0}]
            raise AssertionError(path)
    records = FixtureClient().fetch_recent(1)
    row = records[0]
    assert row["pow_valid"] is True
    assert row["merkle_root_valid"] is True
    assert row["fees_complete"] is True
    assert row["transaction_fees_sats"] == 0
    assert row["coinbase_total_sats"] == 5_000_000_000


def test_rcsc_status_declares_chronological_holdout_capability():
    status = rcsc.status()
    assert status["capabilities"]["chronological_holdout"] is True
    assert status["capabilities"]["holdout_minimum_records"] == 200


def test_rcsc_analysis_marks_small_sample_holdout_insufficient(monkeypatch):
    # A small sample must never be presented as a validated holdout result.
    records = [
        {"height": height, "nonce": height, "pow_valid": True,
         "transaction_fees_sats": 0, "fees_complete": True,
         "merkle_root_valid": True}
        for height in range(20)
    ]
    monkeypatch.setattr(rcsc, "stored_records", lambda limit=1000: records)
    monkeypatch.setattr(rcsc, "_save", lambda kind, payload: "test-run")
    result = rcsc.run_analysis(100)
    holdout = result["result"]["chronological_holdout"]
    assert holdout["status"] == "insufficient_data"
    assert holdout["independent_replication"].startswith("not performed")


def test_rcsc_holdout_uses_declared_200_record_minimum(monkeypatch):
    records = [
        {"height": height, "nonce": height, "pow_valid": True,
         "transaction_fees_sats": 0, "fees_complete": True,
         "merkle_root_valid": True}
        for height in range(666)
    ]
    monkeypatch.setattr(rcsc, "stored_records", lambda limit=1000: records)
    monkeypatch.setattr(rcsc, "_save", lambda kind, payload: "test-run")
    monkeypatch.setattr(rcsc, "reward_conditioned_nonce_tests", lambda *a, **k: {"status": "fixture"})
    result = rcsc.run_analysis(1000)["result"]["chronological_holdout"]
    assert result["actual_holdout_records"] == 200
    assert result["minimum_holdout_records"] == 200
    assert result["status"] == "evaluated"


def test_rcsc_holdout_below_declared_minimum_is_insufficient(monkeypatch):
    records = [
        {"height": height, "nonce": height, "pow_valid": True,
         "transaction_fees_sats": 0, "fees_complete": True,
         "merkle_root_valid": True}
        for height in range(663)
    ]
    monkeypatch.setattr(rcsc, "stored_records", lambda limit=1000: records)
    monkeypatch.setattr(rcsc, "_save", lambda kind, payload: "test-run")
    monkeypatch.setattr(rcsc, "reward_conditioned_nonce_tests", lambda *a, **k: {"status": "fixture"})
    result = rcsc.run_analysis(1000)["result"]["chronological_holdout"]
    assert result["actual_holdout_records"] == 199
    assert result["minimum_holdout_records"] == 200
    assert result["status"] == "insufficient_data"


def test_collector_rejects_incomplete_txid_list_for_merkle_and_fees():
    from nexus_rcsc.collector import MempoolClient

    class IncompleteTxidClient(MempoolClient):
        def __init__(self):
            super().__init__(base_url="https://fixture.invalid", pause_seconds=0)
        def get_text(self, path):
            if path == "blocks/tip/height": return "0"
            if path.endswith("/header"): return GENESIS_HEADER
            if path.endswith("/txid/0"): return GENESIS_TXID
            raise AssertionError(path)
        def get_json(self, path):
            if path == "blocks/0":
                return [{"height":0,"id":"000000000019d6689c085ae165831e934ff763ae46a2a6c172b3f1b60a8ce26f","timestamp":1231006505,"version":1,"merkle_root":GENESIS_TXID,"previousblockhash":"00"*32,"nonce":2083236893,"bits":486604799,"difficulty":1.0,"tx_count":2,"size":285,"weight":1140}]
            if path.endswith("/status"): return {"in_best_chain":True}
            if path.startswith("tx/"): return {"vout":[{"value":5_000_000_000}],"vin":[{"scriptsig":"04ffff001d","scriptsig_asm":"coinbase","witness":[],"is_coinbase":True}]}
            if path.endswith("/txids"): return [GENESIS_TXID]
            raise AssertionError(path)

    row = IncompleteTxidClient().fetch_recent(1)[0]
    assert row["txids_complete"] is False
    assert row["merkle_root_valid"] is False
    assert row["fees_complete"] is False
    assert row["transaction_fees_sats"] is None
    assert row["fee_collection_errors"]


def test_collector_rejects_fee_page_with_wrong_txid_order():
    from nexus_rcsc.collector import MempoolClient
    second_txid = "11" * 32

    class WrongFeePageClient(MempoolClient):
        def __init__(self):
            super().__init__(base_url="https://fixture.invalid", pause_seconds=0)
        def get_text(self, path):
            if path == "blocks/tip/height": return "0"
            if path.endswith("/header"): return GENESIS_HEADER
            if path.endswith("/txid/0"): return GENESIS_TXID
            raise AssertionError(path)
        def get_json(self, path):
            if path == "blocks/0":
                return [{"height":0,"id":"000000000019d6689c085ae165831e934ff763ae46a2a6c172b3f1b60a8ce26f","timestamp":1231006505,"version":1,"merkle_root":GENESIS_TXID,"previousblockhash":"00"*32,"nonce":2083236893,"bits":486604799,"difficulty":1.0,"tx_count":2,"size":285,"weight":1140}]
            if path.endswith("/status"): return {"in_best_chain":True}
            if path.startswith("tx/"): return {"vout":[{"value":5_000_000_000}],"vin":[{"scriptsig":"04ffff001d","scriptsig_asm":"coinbase","witness":[],"is_coinbase":True}]}
            if path.endswith("/txids"): return [GENESIS_TXID, second_txid]
            if path.endswith("/txs/0"): return [{"txid":second_txid,"fee":100},{"txid":GENESIS_TXID,"fee":0}]
            raise AssertionError(path)

    row = WrongFeePageClient().fetch_recent(1)[0]
    assert row["txids_complete"] is True
    assert row["merkle_root_valid"] is False
    assert row["fees_complete"] is False
    assert row["transaction_fees_sats"] is None
    assert "do not match canonical txid order" in row["fee_collection_errors"][0]


def test_collector_requires_coinbase_txid_at_index_zero():
    from nexus_rcsc.collector import MempoolClient
    second_txid = "22" * 32

    class CoinbaseOrderClient(MempoolClient):
        def __init__(self):
            super().__init__(base_url="https://fixture.invalid", pause_seconds=0)
        def get_text(self, path):
            if path == "blocks/tip/height": return "0"
            if path.endswith("/header"): return GENESIS_HEADER
            if path.endswith("/txid/0"): return GENESIS_TXID
            raise AssertionError(path)
        def get_json(self, path):
            if path == "blocks/0":
                return [{"height":0,"id":"000000000019d6689c085ae165831e934ff763ae46a2a6c172b3f1b60a8ce26f","timestamp":1231006505,"version":1,"merkle_root":GENESIS_TXID,"previousblockhash":"00"*32,"nonce":2083236893,"bits":486604799,"difficulty":1.0,"tx_count":2,"size":285,"weight":1140}]
            if path.endswith("/status"): return {"in_best_chain":True}
            if path.startswith("tx/"): return {"vout":[{"value":5_000_000_000}],"vin":[{"scriptsig":"04ffff001d","scriptsig_asm":"coinbase","witness":[],"is_coinbase":True}]}
            if path.endswith("/txids"): return [second_txid, GENESIS_TXID]
            raise AssertionError(path)

    row = CoinbaseOrderClient().fetch_recent(1)[0]
    assert row["txids_coinbase_first"] is False
    assert row["txids_complete"] is False
    assert row["merkle_root_valid"] is False
    assert row["fees_complete"] is False



def test_mempool_client_does_not_retry_permanent_http_errors(monkeypatch):
    import urllib.error
    from email.message import Message
    from nexus_rcsc.collector import MempoolClient

    calls = {"count": 0}
    def fail(request, timeout):
        calls["count"] += 1
        headers = Message()
        raise urllib.error.HTTPError(request.full_url, 404, "Not Found", headers, None)

    monkeypatch.setattr("urllib.request.urlopen", fail)
    client = MempoolClient(base_url="https://fixture.invalid", retries=3, pause_seconds=0)
    try:
        client.get_text("missing")
        assert False, "expected RuntimeError"
    except RuntimeError as exc:
        assert "HTTP 404" in str(exc)
    assert calls["count"] == 1


def test_mempool_client_retries_rate_limit_then_succeeds(monkeypatch):
    import urllib.error
    from email.message import Message
    from nexus_rcsc.collector import MempoolClient

    calls = {"count": 0}
    class Response:
        def __enter__(self): return self
        def __exit__(self, *args): return None
        def read(self): return b'{"ok": true}'

    def respond(request, timeout):
        calls["count"] += 1
        if calls["count"] == 1:
            headers = Message()
            headers["Retry-After"] = "0"
            raise urllib.error.HTTPError(request.full_url, 429, "Too Many Requests", headers, None)
        return Response()

    monkeypatch.setattr("urllib.request.urlopen", respond)
    client = MempoolClient(base_url="https://fixture.invalid", retries=2, pause_seconds=0)
    assert client.get_json("fixture") == {"ok": True}
    assert calls["count"] == 2


def test_mempool_client_retries_invalid_json_body(monkeypatch):
    from nexus_rcsc.collector import MempoolClient

    calls = {"count": 0}
    class Response:
        def __init__(self, body): self.body = body
        def __enter__(self): return self
        def __exit__(self, *args): return None
        def read(self): return self.body

    def respond(request, timeout):
        calls["count"] += 1
        return Response(b"{broken" if calls["count"] == 1 else b'{"ok": true}')

    monkeypatch.setattr("urllib.request.urlopen", respond)
    monkeypatch.setattr("time.sleep", lambda _: None)
    client = MempoolClient(base_url="https://fixture.invalid", retries=2, pause_seconds=0)
    assert client.get_json("fixture") == {"ok": True}
    assert calls["count"] == 2


def test_collection_persists_only_self_consistent_best_chain_pow(monkeypatch, tmp_path):
    valid = {
        "height": 100, "block_hash_reported": "ab" * 32,
        "pow_valid": True, "reported_hash_matches_header": True,
        "reported_fields_match_header": True, "in_best_chain": True,
    }
    invalid = {**valid, "height": 101, "reported_hash_matches_header": False}
    class FixtureClient:
        def __init__(self, **kwargs): pass
        def fetch_recent(self, count, start_height): return [valid, invalid]
    monkeypatch.setattr(rcsc, "MempoolClient", FixtureClient)
    monkeypatch.setattr(rcsc, "DB_PATH", tmp_path / "rcsc.sqlite3")
    result = rcsc.collect(2)
    assert result["returned"] == 2
    assert result["records_saved"] == 1
    assert result["records_rejected"] == 1
    stored = rcsc.stored_records(10)
    assert [row["height"] for row in stored] == [100]


def test_collection_rejects_invalid_start_height():
    import pytest
    with pytest.raises(ValueError, match="start_height"):
        rcsc.collect(1, start_height=-1)
    with pytest.raises(ValueError, match="start_height"):
        rcsc.collect(1, start_height=True)


def test_collection_reorg_replaces_changed_height_and_descendants(monkeypatch, tmp_path):
    def block(height, block_hash, parent_hash):
        return {
            "height": height, "block_hash_reported": block_hash,
            "previous_block_hash_reported": parent_hash,
            "pow_valid": True, "reported_hash_matches_header": True,
            "reported_fields_match_header": True, "in_best_chain": True,
        }

    old_chain = [block(1, "11" * 32, "00" * 32),
                 block(2, "22" * 32, "11" * 32),
                 block(3, "33" * 32, "22" * 32)]
    new_chain = [block(2, "aa" * 32, "11" * 32),
                 block(3, "bb" * 32, "aa" * 32)]
    batches = [old_chain, new_chain]

    class FixtureClient:
        def __init__(self, **kwargs): pass
        def fetch_recent(self, count, start_height): return batches.pop(0)

    monkeypatch.setattr(rcsc, "MempoolClient", FixtureClient)
    monkeypatch.setattr(rcsc, "DB_PATH", tmp_path / "reorg.sqlite3")
    first = rcsc.collect(3)
    assert first["records_saved"] == 3
    assert first["reorg_detected"] is False

    second = rcsc.collect(2)
    assert second["reorg_detected"] is True
    assert second["reorg_from_height"] == 2
    stored = {row["height"]: row["block_hash_reported"] for row in rcsc.stored_records(10)}
    assert stored == {1: "11" * 32, 2: "aa" * 32, 3: "bb" * 32}


def test_collection_rejects_non_contiguous_batch(monkeypatch, tmp_path):
    records = [
        {"height": 10, "block_hash_reported": "10" * 32, "previous_block_hash_reported": "00" * 32,
         "pow_valid": True, "reported_hash_matches_header": True,
         "reported_fields_match_header": True, "in_best_chain": True},
        {"height": 11, "block_hash_reported": "11" * 32, "previous_block_hash_reported": "ff" * 32,
         "pow_valid": True, "reported_hash_matches_header": True,
         "reported_fields_match_header": True, "in_best_chain": True},
    ]

    class FixtureClient:
        def __init__(self, **kwargs): pass
        def fetch_recent(self, count, start_height): return records

    monkeypatch.setattr(rcsc, "MempoolClient", FixtureClient)
    monkeypatch.setattr(rcsc, "DB_PATH", tmp_path / "broken-chain.sqlite3")
    result = rcsc.collect(2)
    assert result["records_saved"] == 0
    assert result["records_rejected"] == 2
    assert result["broken_chain_links"]
    assert rcsc.stored_records(10) == []


def test_collection_rejects_window_with_mismatched_stored_anchor(monkeypatch, tmp_path):
    def block(height, block_hash, parent_hash):
        return {
            "height": height, "block_hash_reported": block_hash,
            "previous_block_hash_reported": parent_hash,
            "pow_valid": True, "reported_hash_matches_header": True,
            "reported_fields_match_header": True, "in_best_chain": True,
        }

    initial = [block(20, "20" * 32, "19" * 32), block(21, "21" * 32, "20" * 32)]
    # The fetched window begins at 21, but its parent no longer matches stored height 20.
    changed_window = [block(21, "aa" * 32, "ff" * 32), block(22, "bb" * 32, "aa" * 32)]
    # Expanded overlap still cannot find a shared stored ancestor.
    batches = [initial, changed_window, [] , [] , [] , []]

    class FixtureClient:
        def __init__(self, **kwargs): pass
        def fetch_recent(self, count, start_height): return batches.pop(0)

    monkeypatch.setattr(rcsc, "MempoolClient", FixtureClient)
    monkeypatch.setattr(rcsc, "DB_PATH", tmp_path / "anchor.sqlite3")
    rcsc.collect(2)
    result = rcsc.collect(2)
    assert result["anchor_verified"] is False
    assert result["anchor_mismatch"]["height"] == 20
    assert result["recovery_status"] == "common_ancestor_not_found_fail_closed"
    assert result["records_saved"] == 0
    stored = {row["height"]: row["block_hash_reported"] for row in rcsc.stored_records(10)}
    assert stored == {20: "20" * 32, 21: "21" * 32}


def test_collection_expands_overlap_and_recovers_from_reorg(monkeypatch, tmp_path):
    def block(height, block_hash, parent_hash):
        return {"height":height,"block_hash_reported":block_hash,
                "previous_block_hash_reported":parent_hash,"pow_valid":True,
                "reported_hash_matches_header":True,"reported_fields_match_header":True,
                "in_best_chain":True}
    old = [block(18,"18"*32,"17"*32),block(19,"19"*32,"18"*32),
           block(20,"20"*32,"19"*32),block(21,"21"*32,"20"*32)]
    narrow = [block(21,"aa"*32,"cc"*32),block(22,"bb"*32,"aa"*32)]
    expanded = [block(19,"19"*32,"18"*32),block(20,"cc"*32,"19"*32),
                block(21,"aa"*32,"cc"*32),block(22,"bb"*32,"aa"*32)]
    batches = [old, narrow, expanded]
    class FixtureClient:
        def __init__(self, **kwargs): pass
        def fetch_recent(self, count, start_height): return batches.pop(0)
    monkeypatch.setattr(rcsc,"MempoolClient",FixtureClient)
    monkeypatch.setattr(rcsc,"DB_PATH",tmp_path/"recover.sqlite3")
    rcsc.collect(4)
    result = rcsc.collect(2)
    assert result["recovery_status"] == "common_ancestor_found"
    assert result["common_ancestor_height"] == 19
    assert result["reorg_from_height"] == 20
    stored = {r["height"]:r["block_hash_reported"] for r in rcsc.stored_records(20)}
    assert stored == {18:"18"*32,19:"19"*32,20:"cc"*32,21:"aa"*32,22:"bb"*32}


def test_common_ancestor_recovery_preserves_original_newer_window(monkeypatch, tmp_path):
    """Backward overlap must be merged with the initial fetch's newer tip window."""
    def block(height, block_hash, parent_hash):
        return {"height": height, "block_hash_reported": block_hash,
                "previous_block_hash_reported": parent_hash, "pow_valid": True,
                "reported_hash_matches_header": True, "reported_fields_match_header": True,
                "in_best_chain": True}

    old = [block(18, "18"*32, "17"*32), block(19, "19"*32, "18"*32),
           block(20, "20"*32, "19"*32), block(21, "21"*32, "20"*32)]
    initial_new = [block(22, "bb"*32, "aa"*32), block(23, "cc"*32, "bb"*32)]
    backward_overlap = [block(21, "aa"*32, "dd"*32), block(20, "dd"*32, "19"*32),
                        block(19, "19"*32, "18"*32)]
    batches = [old, initial_new, backward_overlap]

    class FixtureClient:
        def __init__(self, **kwargs): pass
        def fetch_recent(self, count, start_height): return batches.pop(0)

    monkeypatch.setattr(rcsc, "MempoolClient", FixtureClient)
    monkeypatch.setattr(rcsc, "DB_PATH", tmp_path / "recover-tip.sqlite3")
    rcsc.collect(4)
    result = rcsc.collect(2)
    assert result["recovery_status"] == "common_ancestor_found"
    assert result["common_ancestor_height"] == 19
    stored = {r["height"]: r["block_hash_reported"] for r in rcsc.stored_records(20)}
    assert stored == {18:"18"*32, 19:"19"*32, 20:"dd"*32, 21:"aa"*32,
                      22:"bb"*32, 23:"cc"*32}


def test_sqlite_database_context_closes_connection_and_commits(monkeypatch, tmp_path):
    monkeypatch.setattr(rcsc, "DB_PATH", tmp_path / "lifecycle.sqlite3")
    with rcsc._database() as db:
        db.execute("INSERT INTO runs VALUES (?,?,?,?)", ("commit-check", "now", "test", "{}"))
    try:
        db.execute("SELECT 1")
        raise AssertionError("SQLite connection remained open after context exit")
    except Exception as exc:
        import sqlite3
        assert isinstance(exc, sqlite3.ProgrammingError)
    with rcsc._database() as check:
        assert check.execute("SELECT COUNT(*) FROM runs WHERE run_id='commit-check'").fetchone()[0] == 1


def test_sqlite_database_context_rolls_back_and_closes_on_error(monkeypatch, tmp_path):
    import sqlite3
    monkeypatch.setattr(rcsc, "DB_PATH", tmp_path / "rollback.sqlite3")
    try:
        with rcsc._database() as db:
            db.execute("INSERT INTO runs VALUES (?,?,?,?)", ("rollback-check", "now", "test", "{}"))
            raise RuntimeError("simulated interruption")
    except RuntimeError:
        pass
    try:
        db.execute("SELECT 1")
        raise AssertionError("SQLite connection remained open after exception")
    except sqlite3.ProgrammingError:
        pass
    with rcsc._database() as check:
        assert check.execute("SELECT COUNT(*) FROM runs WHERE run_id='rollback-check'").fetchone()[0] == 0
