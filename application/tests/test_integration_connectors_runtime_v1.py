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
        lambda request, timeout: FakeResponse({"status": "ok", "service": "aioz-test"}),
    )

    result = registry.probe_connector("aioz")
    assert result["status"] == "reachable"
    assert result["operational_verified"] is True
    assert result["http_status"] == 200
    assert result["response_summary"]["keys"] == ["service", "status"]

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
    assert result["operational_verified"] is True
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
        lambda request, timeout: FakeResponse({"ok": True}),
    )
    registry.probe_connector("aioz")
    status = registry.integrations_status()
    assert status["total"] == 12
    assert status["live_verified"] == 1
    assert status["operational_verified"] == 1


def test_unknown_connector_is_rejected():
    with pytest.raises(registry.ConnectorError, match="unknown_connector"):
        registry.probe_connector("not-a-real-provider")
