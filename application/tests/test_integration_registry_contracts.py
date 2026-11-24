"""Contract tests for the read-only provider registry."""
from modules.integration_registry import PROVIDERS, connector_status


def test_provider_catalog_has_unique_stable_ids():
    rows = connector_status(env={})
    ids = [row["id"] for row in rows]
    assert ids
    assert len(ids) == len(set(ids))
    assert set(ids) == {provider["id"] for provider in PROVIDERS}


def test_empty_environment_reports_every_provider_unconfigured():
    rows = connector_status(env={})
    assert all(row["status"] == "not_configured" for row in rows)
    assert all(row["live_connection_verified"] is False for row in rows)
    assert all(row["writes_enabled"] is False for row in rows)


def test_partial_provider_configuration_does_not_claim_readiness():
    row = next(item for item in connector_status(env={
        "NEXUS_ACURAST_API_URL": "https://example.invalid"
    }) if item["id"] == "acurast")
    assert row["status"] == "not_configured"
    assert row["configured_fields"] == 1
    assert row["required_fields"] == 2
    assert row["missing_configuration"] == ["NEXUS_ACURAST_API_TOKEN"]


def test_complete_credentials_are_pending_validation_and_never_echoed():
    secret = "test-only-secret-never-return-this"
    row = next(item for item in connector_status(env={
        "NEXUS_ACURAST_API_URL": "https://example.invalid",
        "NEXUS_ACURAST_API_TOKEN": secret,
    }) if item["id"] == "acurast")
    assert row["status"] == "configured_pending_adapter_validation"
    assert row["configured_fields"] == row["required_fields"] == 2
    assert row["live_connection_verified"] is False
    assert row["writes_enabled"] is False
    assert secret not in repr(row)
