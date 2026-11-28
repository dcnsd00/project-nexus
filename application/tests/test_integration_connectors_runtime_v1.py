"""Contract tests for NEXUS guarded read-only external connectors."""
import json

import pytest

from modules import integration_registry as registry


class FakeResponse:
    def __init__(self, payload, status=200, content_type="application/json"):
        self.payload = json.dumps(payload).encode("utf-8")
        self.status = status
        self.headers = {"Content-Type": content_type}

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def getcode(self):
        return self.status

    def read(self, limit):
        return self.payload[:limit]


def test_all_twelve_connectors_have_read_only_adapter_and_resource_contracts():
    rows = registry.connector_status(env={})
    assert len(rows) == 12
    assert all(row["adapter_registered"] for row in rows)
    assert all(row["mode"] == "read_only" for row in rows)
    assert all(row["writes_enabled"] is False for row in rows)
    assert all(row["operational_verified"] is False for row in rows)
    assert all(row["resources"] for row in rows)


def test_configured_health_probe_verifies_only_after_a_real_adapter_response(monkeypatch):
    monkeypatch.setenv("NEXUS_AIOZ_API_URL", "https://api.aioz.example/v1")
    monkeypatch.setenv("NEXUS_CONNECTOR_ALLOWED_HOSTS_AIOZ", "api.aioz.example")
    monkeypatch.setenv("NEXUS_AIOZ_HEALTH_PATH", "health")
    monkeypatch.setattr(
        registry,
        "_transport_open",
        lambda request, timeout: FakeResponse({
            "jsonrpc": "2.0",
            "id": 1,
            "result": {
                "node_info": {"network": "aioz-mainnet"},
                "sync_info": {"latest_block_height": "1"},
            },
        }),
    )

    result = registry.probe_connector("aioz")
    assert result["status"] == "reachable"
    assert result["operational_verified"] is True
    assert result["http_status"] == 200
    assert result["response_summary"]["keys"] == ["id", "jsonrpc", "result"]

    aioz = next(row for row in registry.connector_status() if row["id"] == "aioz")
    assert aioz["status"] == "live_verified"
    assert aioz["operational_verified"] is True
    assert aioz["last_http_status"] == 200


def test_resource_read_uses_configured_path_and_never_enables_writes(monkeypatch):
    monkeypatch.setenv("NEXUS_ACURAST_API_URL", "https://api.acurast.example/v2")
    monkeypatch.setenv("NEXUS_ACURAST_API_TOKEN", "unit-test-connector-secret")
    monkeypatch.setenv("NEXUS_CONNECTOR_ALLOWED_HOSTS_ACURAST", "api.acurast.example")
    monkeypatch.setenv("NEXUS_ACURAST_REWARDS_PATH", "account/rewards")
    monkeypatch.setenv("NEXUS_ACURAST_API_TOKEN_HEADER", "X-API-Key")
    captured = {}

    def fake_transport(request, timeout):
        captured["url"] = request.full_url
        captured["headers"] = {k.lower(): v for k, v in request.header_items()}
        captured["method"] = request.get_method()
        return FakeResponse({"total": 18, "unit": "points"})

    monkeypatch.setattr(registry, "_transport_open", fake_transport)
    result = registry.read_connector_resource("acurast", "rewards")
    assert captured["url"] == "https://api.acurast.example/v2/account/rewards"
    assert captured["method"] == "GET"
    assert captured["headers"]["x-api-key"] == "Bearer unit-test-connector-secret"
    assert result["data"] == {"total": 18, "unit": "points"}
    assert result["read_only"] is True
    assert result["status"] == "read_succeeded_contract_pending"
    assert result["operational_verified"] is False
    assert result["contract_verified"] is False
    assert "unit-test-connector-secret" not in repr(result)


def test_remote_connector_requires_https_and_exact_host_allowlist(monkeypatch):
    monkeypatch.setenv("NEXUS_AIOZ_API_URL", "http://api.aioz.example/v1")
    monkeypatch.setenv("NEXUS_AIOZ_HEALTH_PATH", "health")
    monkeypatch.setenv("NEXUS_CONNECTOR_ALLOWED_HOSTS_AIOZ", "api.aioz.example")
    with pytest.raises(registry.ConnectorError, match="remote_connector_requires_https_443"):
        registry.probe_connector("aioz")

    monkeypatch.setenv("NEXUS_AIOZ_API_URL", "https://attacker.example/v1")
    with pytest.raises(registry.ConnectorError, match="connector_host_not_allowlisted"):
        registry.probe_connector("aioz")


def test_connector_resource_rejects_traversal_and_untrusted_url_paths(monkeypatch):
    monkeypatch.setenv("NEXUS_NODLE_API_URL", "https://api.nodle.example")
    monkeypatch.setenv("NEXUS_CONNECTOR_ALLOWED_HOSTS_NODLE", "api.nodle.example")
    monkeypatch.setenv("NEXUS_NODLE_REWARDS_PATH", "../../admin")
    with pytest.raises(registry.ConnectorError, match="invalid_connector_resource_path"):
        registry.read_connector_resource("nodle", "rewards")

    monkeypatch.setenv("NEXUS_NODLE_REWARDS_PATH", "https://attacker.example/data")
    with pytest.raises(registry.ConnectorError, match="invalid_connector_resource_path"):
        registry.read_connector_resource("nodle", "rewards")


def test_connector_fails_closed_on_non_json_and_oversized_response(monkeypatch):
    monkeypatch.setenv("NEXUS_THETA_API_URL", "https://api.theta.example")
    monkeypatch.setenv("NEXUS_CONNECTOR_ALLOWED_HOSTS_THETA", "api.theta.example")
    monkeypatch.setenv("NEXUS_THETA_HEALTH_PATH", "health")
    monkeypatch.setattr(
        registry,
        "_transport_open",
        lambda request, timeout: FakeResponse("healthy", content_type="text/plain"),
    )
    with pytest.raises(registry.ConnectorError, match="connector_expected_json_content_type"):
        registry.probe_connector("theta")

    class OversizedResponse(FakeResponse):
        def read(self, limit):
            return b"x" * limit

    monkeypatch.setattr(
        registry,
        "_transport_open",
        lambda request, timeout: OversizedResponse({}),
    )
    with pytest.raises(registry.ConnectorError, match="connector_response_too_large"):
        registry.probe_connector("theta")


def test_connector_http_errors_are_sanitized(monkeypatch):
    from urllib.error import HTTPError

    monkeypatch.setenv("NEXUS_GRASS_API_URL", "https://api.grass.example")
    monkeypatch.setenv("NEXUS_GRASS_API_TOKEN", "unit-test-secret")
    monkeypatch.setenv("NEXUS_CONNECTOR_ALLOWED_HOSTS_GRASS", "api.grass.example")
    monkeypatch.setenv("NEXUS_GRASS_HEALTH_PATH", "health")

    def fail(request, timeout):
        raise HTTPError(request.full_url, 401, "private token rejected", {}, None)

    monkeypatch.setattr(registry, "_transport_open", fail)
    with pytest.raises(registry.ConnectorError, match="connector_http_401") as exc:
        registry.probe_connector("grass")
    assert "private token rejected" not in str(exc.value)
    assert "unit-test-secret" not in str(exc.value)


def test_integration_status_counts_live_connector_only_after_success(monkeypatch):
    monkeypatch.setenv("NEXUS_AIOZ_API_URL", "https://api.aioz.example")
    monkeypatch.setenv("NEXUS_CONNECTOR_ALLOWED_HOSTS_AIOZ", "api.aioz.example")
    monkeypatch.setenv("NEXUS_AIOZ_HEALTH_PATH", "health")
    monkeypatch.setattr(
        registry,
        "_transport_open",
        lambda request, timeout: FakeResponse({
            "jsonrpc": "2.0",
            "id": 1,
            "result": {"node_info": {"network": "aioz-mainnet"}, "sync_info": {"latest_block_height": "1"}},
        }),
    )
    registry.probe_connector("aioz")
    status = registry.integrations_status()
    assert status["total"] == 12
    assert status["live_verified"] == 1
    assert status["operational_verified"] == 1


def test_unknown_connector_is_rejected():
    with pytest.raises(registry.ConnectorError, match="unknown_connector"):
        registry.probe_connector("not-a-real-provider")


def test_all_twelve_configured_connector_health_endpoints_can_be_probed(monkeypatch):
    registry._LIVE_VERIFICATION.clear()
    for item in registry.PROVIDERS:
        suffix = item["id"].upper()
        hostname = f"api-{item['id'].replace('_', '-')}.example"
        if item.get("env"):
            monkeypatch.setenv(item["env"][0], f"https://{hostname}/v1")
        monkeypatch.setenv(f"NEXUS_CONNECTOR_ALLOWED_HOSTS_{suffix}", hostname)
        monkeypatch.setenv(f"NEXUS_{suffix}_HEALTH_PATH", "health")
        for key in item.get("env", ())[1:]:
            monkeypatch.setenv(key, f"test-credential-{item['id']}")

    def provider_response(request, timeout):
        url = request.full_url
        if "aioz" in url:
            payload = {"jsonrpc": "2.0", "id": 1, "result": {
                "node_info": {"network": "aioz-mainnet"},
                "sync_info": {"latest_block_height": "1"},
            }}
        elif "theta" in url:
            payload = {"jsonrpc": "2.0", "id": 1, "result": "0x169"}
        elif "helium" in url:
            payload = {"items": [], "cursor": None}
        elif "geodnet" in url:
            payload = {"code": 1000, "msg": "OK", "data": []}
        elif "anyone" in url:
            payload = {"all": 1, "offline": 0, "online": 1}
        elif "weatherxm" in url:
            payload = {"total": 1, "online": 1}
        elif "akash" in url:
            payload = []
        elif "nosana" in url:
            payload = {"total": 0, "byState": {}}
        else:
            payload = {"status": "ok"}
        return FakeResponse(payload)

    monkeypatch.setattr(registry, "_transport_open", provider_response)
    result = registry.run_connector_self_test()
    assert result["status"] == "partial"
    assert result["operational_verified"] is False
    assert result["connectors_tested"] == 12
    assert result["connectors_passed"] == 8
    assert result["connectors_reachable"] == 12
    assert result["connectors_contract_pending"] == 4
    assert result["connectors_failed_or_unconfigured"] == 0
    assert sum(row["status"] == "contract_pending" for row in result["results"]) == 4
    assert sum(row["status"] == "passed" for row in result["results"]) == 8
    assert result["read_only"] is True
    assert result["writes_enabled"] is False
    assert sum(row["operational_verified"] for row in registry.connector_status()) == 8


def test_connector_live_self_test_api_is_loopback_only(monkeypatch):
    from fastapi.testclient import TestClient
    from nexus_master import app

    expected = {
        "status": "partial",
        "operational_verified": False,
        "connectors_tested": 12,
        "connectors_passed": 0,
        "connectors_reachable": 0,
        "connectors_contract_pending": 0,
        "connectors_failed_or_unconfigured": 12,
        "read_only": True,
        "writes_enabled": False,
        "results": [],
    }
    monkeypatch.setattr(registry, "run_connector_self_test", lambda: expected)
    with TestClient(app, base_url="http://127.0.0.1",
                    client=("127.0.0.1", 54332)) as client:
        response = client.post("/api/integrations/self-test")
    assert response.status_code == 200
    assert response.json() == expected

    with TestClient(app, base_url="http://127.0.0.1",
                    client=("192.0.2.32", 54332)) as client:
        blocked = client.post("/api/integrations/self-test")
    assert blocked.status_code == 403


def test_official_public_connector_defaults_and_contract_metadata_are_registered():
    rows = {row["id"]: row for row in registry.connector_status(env={})}
    expected = {
        "aioz": ("https://rpc-dataseed.aioz.network", "official_rpc_documented"),
        "theta": ("https://eth-rpc-api.thetatoken.org", "official_json_rpc_documented"),
        "helium_iot": ("https://entities.nft.helium.io", "official_entity_api_documented"),
        "geodnet": ("https://rawdata.geodnet.com", "official_basic_auth_station_api_documented"),
        "anyone": ("https://api.ec.anyone.tech", "official_public_rest_documented"),
        "weatherxm": ("https://api.weatherxm.com", "official_openapi_documented"),
        "akash": ("https://console-api.akash.network", "official_public_read_only_network_data_api_documented"),
        "nosana": ("https://api.nosana.com", "official_api_documented"),
    }
    for provider_id, (base_url, contract_state) in expected.items():
        row = rows[provider_id]
        assert row["default_url_used"] is True
        assert row["contract_state"] == contract_state
        assert registry._PROVIDER_BY_ID[provider_id]["default_base_url"] == base_url
        assert row["operational_verified"] is False


def test_theta_uses_only_read_only_json_rpc_post_methods(monkeypatch):
    captured = {}

    def fake_transport(request, timeout):
        captured["url"] = request.full_url
        captured["method"] = request.get_method()
        captured["payload"] = json.loads(request.data.decode("utf-8"))
        return FakeResponse({"jsonrpc": "2.0", "id": 1, "result": "0x169"})

    monkeypatch.setattr(registry, "_transport_open", fake_transport)
    result = registry.probe_connector("theta")
    assert captured["url"] == "https://eth-rpc-api.thetatoken.org/rpc"
    assert captured["method"] == "POST"
    assert captured["payload"] == {
        "jsonrpc": "2.0", "method": "eth_chainId", "params": [], "id": 1
    }
    assert result["operational_verified"] is True

    resource = registry.read_connector_resource("theta", "public_chain")
    assert resource["data"]["result"] == "0x169"
    assert captured["payload"]["method"] == "eth_blockNumber"


def test_geodnet_uses_documented_basic_auth_without_exposing_credentials(monkeypatch):
    monkeypatch.setenv("NEXUS_GEODNET_USERNAME", "geo-user")
    monkeypatch.setenv("NEXUS_GEODNET_PASSWORD", "geo-password")
    captured = {}

    def fake_transport(request, timeout):
        captured["url"] = request.full_url
        captured["authorization"] = request.get_header("Authorization")
        return FakeResponse({"code": 1000, "msg": "OK", "data": []})

    monkeypatch.setattr(registry, "_transport_open", fake_transport)
    result = registry.probe_connector("geodnet")
    assert captured["url"] == "https://rawdata.geodnet.com/api/rawdata/v1/stations"
    assert captured["authorization"].startswith("Basic ")
    assert "geo-user" not in captured["authorization"]
    assert "geo-password" not in repr(result)
    assert result["operational_verified"] is True


def test_documented_default_public_apis_are_allowlisted_without_user_supplied_host_override(monkeypatch):
    responses = {
        "aioz": {"jsonrpc": "2.0", "id": 1, "result": {
            "node_info": {"network": "aioz-mainnet"}, "sync_info": {"latest_block_height": "1"}
        }},
        "theta": {"jsonrpc": "2.0", "id": 1, "result": "0x169"},
        "helium_iot": {"items": [], "cursor": None},
        "anyone": {"all": 1, "offline": 0, "online": 1},
        "weatherxm": {"total": 1, "online": 1},
        "akash": [],
        "nosana": {"total": 0, "byState": {}},
    }
    def fake_transport(request, timeout):
        provider_id = next(key for key, item in registry._PROVIDER_BY_ID.items()
                           if item.get("default_base_url") and item["default_base_url"] in request.full_url)
        return FakeResponse(responses[provider_id])

    monkeypatch.setenv("NEXUS_NOSANA_API_TOKEN", "nos-test-token")
    monkeypatch.setattr(registry, "_transport_open", fake_transport)
    for provider_id in responses:
        result = registry.probe_connector(provider_id)
        assert result["operational_verified"] is True


def test_documented_connector_contract_mismatch_does_not_mark_provider_live(monkeypatch):
    registry._LIVE_VERIFICATION.clear()
    monkeypatch.setattr(
        registry,
        "_transport_open",
        lambda request, timeout: FakeResponse({"status": "ok"}),
    )
    with pytest.raises(registry.ConnectorError, match="connector_response_contract_mismatch"):
        registry.probe_connector("theta")
    theta = next(row for row in registry.connector_status() if row["id"] == "theta")
    assert theta["operational_verified"] is False


def test_nosana_requires_api_key_even_when_official_base_url_is_default():
    item = registry._PROVIDER_BY_ID["nosana"]
    with pytest.raises(registry.ConnectorError, match="connector_not_configured"):
        registry._config(item, {})
