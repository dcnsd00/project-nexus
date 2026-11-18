from modules import evm_node_telemetry as telemetry


def test_evm_snapshot_reports_base_chain_and_read_only_metrics(monkeypatch):
    monkeypatch.setenv("NEXUS_EVM_RPC_URL", "https://rpc.example.net/v1/test-key")
    calls = []
    values = {
        "eth_chainId": "0x2105", "eth_blockNumber": "0x1234",
        "eth_syncing": False, "net_peerCount": "0x8", "eth_gasPrice": "0x3b9aca00",
        "eth_getBlockByNumber": {"hash": "0xabc", "timestamp": "0x6553f100", "transactions": ["0x1", "0x2"]},
    }
    def fake(method, params=None):
        calls.append(method)
        return values[method]
    result = telemetry.evm_node_snapshot(rpc_factory=fake)
    assert result["rpc"]["status"] == "connected"
    assert result["network"] == {"chain_id": 8453, "name": "base"}
    assert result["latest_block"]["number"] == 0x1234
    assert result["sync"]["status"] == "not_syncing"
    assert result["peers"]["count"] == 8
    assert result["gas_price_wei"] == 1_000_000_000
    assert result["latest_block"]["transactions"] == 2
    assert result["writes_enabled"] is False
    assert "test-key" not in str(result)
    assert calls[:2] == ["eth_chainId", "eth_blockNumber"]


def test_evm_snapshot_is_not_configured_without_endpoint(monkeypatch):
    monkeypatch.delenv("NEXUS_EVM_RPC_URL", raising=False)
    result = telemetry.evm_node_snapshot()
    assert result["rpc"]["status"] == "not_configured"
    assert result["rpc"]["reachable"] is False
    assert result["network"] is None


def test_evm_snapshot_rejects_http_and_local_targets(monkeypatch):
    for url in ("http://rpc.example.net", "https://127.0.0.1:8545",
                "https://localhost:8545", "https://router.local"):
        monkeypatch.setenv("NEXUS_EVM_RPC_URL", url)
        result = telemetry.evm_node_snapshot(rpc_factory=lambda method, params=None: "0x1")
        assert result["rpc"]["status"] == "invalid_endpoint"
        assert result["rpc"]["reachable"] is False


def test_evm_snapshot_marks_rpc_failures(monkeypatch):
    monkeypatch.setenv("NEXUS_EVM_RPC_URL", "https://rpc.example.net")
    def fail(method, params=None):
        raise TimeoutError("provider offline")
    result = telemetry.evm_node_snapshot(rpc_factory=fail)
    assert result["rpc"]["status"] == "connection_failed"
    assert result["rpc"]["reachable"] is False
    assert "TimeoutError" in result["error"]


def test_evm_snapshot_redacts_provider_url_and_api_key_on_rpc_failure(monkeypatch):
    secret = "sensitive-provider-key"
    monkeypatch.setenv("NEXUS_EVM_RPC_URL", f"https://rpc.example.net/v1/{secret}?token={secret}")

    class ProviderError(Exception):
        pass

    def fail(method, params=None):
        raise ProviderError(f"request failed for https://rpc.example.net/v1/{secret}?token={secret}")

    result = telemetry.evm_node_snapshot(rpc_factory=fail)
    assert result["rpc"]["status"] == "connection_failed"
    assert "ProviderError" in result["error"]
    assert "redacted" in result["error"]
    assert secret not in str(result)
    assert "https://rpc.example.net" not in str(result)
