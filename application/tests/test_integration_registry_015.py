from fastapi.testclient import TestClient
from nexus_master import app
from modules.integration_registry import connector_status


def test_provider_registry_reports_truthful_unconfigured_state():
    rows = connector_status({})
    assert len(rows) == 12
    assert all(r["status"] == "not_configured" for r in rows)
    assert all(r["live_connection_verified"] is False for r in rows)
    assert all(r["writes_enabled"] is False for r in rows)


def test_provider_config_does_not_claim_live_without_adapter_validation():
    rows = connector_status({"NEXUS_GRASS_API_URL":"https://example.invalid", "NEXUS_GRASS_API_TOKEN":"placeholder"})
    grass = next(r for r in rows if r["id"] == "grass")
    assert grass["status"] == "configured_pending_adapter_validation"
    assert grass["live_connection_verified"] is False


def test_integrations_api_surface():
    with TestClient(app) as client:
        catalog = client.get("/api/integrations/catalog")
        status = client.get("/api/integrations/status")
    assert catalog.status_code == 200 and catalog.json()["count"] == 12
    assert status.status_code == 200 and status.json()["live_verified"] == 0
