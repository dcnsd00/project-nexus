from mining import controller as mc


def test_miner_metrics_distinguish_local_api_from_pool_connectivity(monkeypatch):
    monkeypatch.setattr(mc, "_http_json", lambda url: {
        "hashrate": {"total": [1250.0, 1100.0, 900.0]},
        "results": {"shares_good": 12, "shares_failed": 2, "shares_total": 14},
    })
    monkeypatch.setattr(mc, "_state", {
        "api": "http://127.0.0.1:18080/1/summary",
        "status": "running",
        "miner_id": "xmrig",
        "miner_name": "XMRig",
        "pid": None,
    })
    monkeypatch.setattr(mc.shutil, "which", lambda name: None)
    metrics = mc._metrics()
    assert metrics["schema_version"] == 1
    assert metrics["miner_api"]["status"] == "connected"
    assert metrics["api_connected"] is True
    assert metrics["pool_connection"]["status"] == "unknown"
    assert metrics["pool_connection"]["evidence"] is None
    assert metrics["hashrate_hs"] == 1250.0
    assert metrics["hashrate_source"] == "miner_api"
    assert metrics["accepted_shares"] == 12
    assert metrics["rejected_shares"] == 2
    assert metrics["shares_source"] == "miner_api"
    assert metrics["sampled_at"] > 0


def test_miner_metrics_report_unavailable_api_without_inventing_pool_state(monkeypatch):
    monkeypatch.setattr(mc, "_http_json", lambda url: None)
    monkeypatch.setattr(mc, "_state", {
        "api": "http://127.0.0.1:18080/1/summary",
        "status": "running",
        "miner_id": "xmrig",
        "miner_name": "XMRig",
        "pid": None,
    })
    monkeypatch.setattr(mc.shutil, "which", lambda name: None)
    metrics = mc._metrics()
    assert metrics["miner_api"]["status"] == "unreachable_or_invalid"
    assert metrics["miner_api"]["connected"] is False
    assert metrics["pool_connection"]["status"] == "unknown"
    assert metrics["hashrate_hs"] is None


def test_miner_without_api_is_explicitly_not_supported(monkeypatch):
    monkeypatch.setattr(mc, "_state", {
        "api": None,
        "status": "running",
        "miner_id": "lolminer",
        "miner_name": "lolMiner",
        "pid": None,
    })
    monkeypatch.setattr(mc.shutil, "which", lambda name: None)
    metrics = mc._metrics()
    assert metrics["miner_api"]["status"] == "not_supported"
    assert metrics["miner_api"]["checked_at"] is None
    assert metrics["pool_connection"]["status"] == "unknown"
