from modules import blockchain_node_telemetry as telemetry


class FakeRPC:
    def __init__(self, cfg):
        self.cfg = cfg
        self.calls = []

    def call(self, method, params=None):
        self.calls.append(method)
        values = {
            "getblockchaininfo": {
                "chain": "regtest", "blocks": 120, "headers": 120,
                "initialblockdownload": False, "verificationprogress": 1.0,
                "pruned": False, "chainwork": "00ff",
            },
            "getnetworkinfo": {
                "version": 280000, "subversion": "/Satoshi:28.0.0/",
                "protocolversion": 70016,
            },
            "getpeerinfo": [{"inbound": False}, {"inbound": True}],
            "getmempoolinfo": {"size": 3, "bytes": 1200, "usage": 4096, "total_fee": 0.0001},
        }
        return values[method]


def test_bitcoin_node_snapshot_reports_measured_rpc_state(monkeypatch, tmp_path):
    cookie = tmp_path / ".cookie"
    cookie.write_text("user:secret")
    monkeypatch.setenv("NEXUS_BITCOIN_RPC_COOKIE_FILE", str(cookie))
    monkeypatch.delenv("NEXUS_BITCOIN_RPC_COOKIE", raising=False)
    monkeypatch.setenv("NEXUS_BITCOIN_RPC_URL", "http://127.0.0.1:18443")
    monkeypatch.setattr(telemetry.shutil, "which", lambda name: None)
    captured = {}
    def factory(cfg):
        captured.update(cfg)
        return FakeRPC(cfg)
    result = telemetry.bitcoin_node_snapshot(rpc_factory=factory)
    assert result["rpc"]["status"] == "connected"
    assert result["rpc"]["reachable"] is True
    assert result["network"]["chain"] == "regtest"
    assert result["sync"]["blocks"] == 120
    assert result["sync"]["blocks_behind_headers"] == 0
    assert result["peers"] == {"count": 2, "inbound": 1, "outbound": 1}
    assert result["mempool"]["transactions"] == 3
    assert "password" not in result["rpc"]
    assert captured["credentials_available"] is True


def test_bitcoin_node_snapshot_does_not_claim_connected_without_credentials(monkeypatch):
    monkeypatch.delenv("NEXUS_BITCOIN_RPC_COOKIE_FILE", raising=False)
    monkeypatch.delenv("NEXUS_BITCOIN_RPC_COOKIE", raising=False)
    monkeypatch.delenv("NEXUS_BITCOIN_RPC_USER", raising=False)
    monkeypatch.delenv("NEXUS_BITCOIN_RPC_PASSWORD", raising=False)
    monkeypatch.setenv("APPDATA", "/nonexistent/nexus-test")
    monkeypatch.setattr(telemetry.shutil, "which", lambda name: None)
    result = telemetry.bitcoin_node_snapshot()
    assert result["rpc"]["status"] == "not_configured"
    assert result["rpc"]["reachable"] is False
    assert result["network"] is None


def test_bitcoin_node_snapshot_blocks_non_loopback_rpc(monkeypatch):
    monkeypatch.setenv("NEXUS_BITCOIN_RPC_URL", "http://192.0.2.10:8332")
    monkeypatch.setenv("NEXUS_BITCOIN_RPC_USER", "test")
    monkeypatch.setenv("NEXUS_BITCOIN_RPC_PASSWORD", "secret")
    monkeypatch.setattr(telemetry.shutil, "which", lambda name: None)
    result = telemetry.bitcoin_node_snapshot()
    assert result["rpc"]["status"] == "blocked_non_loopback_endpoint"
    assert result["rpc"]["reachable"] is False


def test_bitcoin_node_snapshot_marks_rpc_failure(monkeypatch, tmp_path):
    cookie = tmp_path / ".cookie"
    cookie.write_text("user:secret")
    monkeypatch.setenv("NEXUS_BITCOIN_RPC_COOKIE_FILE", str(cookie))
    monkeypatch.setenv("NEXUS_BITCOIN_RPC_URL", "http://127.0.0.1:18443")
    monkeypatch.setattr(telemetry.shutil, "which", lambda name: None)
    class BrokenRPC:
        def __init__(self, cfg): pass
        def call(self, method, params=None): raise TimeoutError("offline")
    result = telemetry.bitcoin_node_snapshot(rpc_factory=lambda cfg: BrokenRPC(cfg))
    assert result["rpc"]["status"] == "connection_failed"
    assert result["rpc"]["reachable"] is False
    assert "TimeoutError" in result["error"]
