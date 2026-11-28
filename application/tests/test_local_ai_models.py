"""Tests for NEXUS local open-weight model catalogue and runtime discovery."""
from fastapi.testclient import TestClient
import pytest

from modules import local_ai_models as models


def test_catalog_registers_lfm3_and_apache_licensed_gpt_oss_without_installing():
    catalog = models.model_catalog()
    profiles = {row["id"]: row for row in catalog["models"]}
    assert catalog["default_local_agent"] == "lfm3-text"
    assert catalog["count"] == len(models.MODEL_PROFILES)
    assert profiles["lfm3-text"]["ollama_model"] == "lfm3"
    assert profiles["lfm3-text"]["llamacpp_model"] == "LiquidAI/LFM3-1.7B-GGUF:Q4_K_M"
    assert profiles["lfm3-text"]["license"] == "LFM Open License v1.0"
    assert profiles["lfm3-text"]["license_family"] == "Apache-2.0-based-with-commercial-revenue-condition"
    assert profiles["gpt-oss-20b"]["license"] == "Apache License 2.0"
    assert profiles["gpt-oss-20b"]["minimum_system_memory_gb"] == 16
    assert profiles["qwen3-4b"]["ollama_model"] == "qwen3:4b"
    assert profiles["qwen3-4b"]["license"] == "Apache License 2.0"
    assert profiles["deepseek-r1-1-5b"]["ollama_model"] == "deepseek-r1:1.5b"
    assert profiles["deepseek-r1-1-5b"]["license"] == "MIT License"
    assert profiles["deepseek-r1-7b"]["approx_quantized_weights_gb"] == 4.7
    assert all(row["download_required"] is True for row in profiles.values())
    assert catalog["policy"].startswith("Catalogue only")


def test_model_catalog_returns_independent_rows_and_capability_arrays():
    first = models.model_catalog()
    first["models"][0]["modalities"].append("mutated")
    second = models.model_catalog()
    assert "mutated" not in second["models"][0]["modalities"]


def test_local_runtime_discovery_reports_ollama_and_llamacpp_without_starting_them(monkeypatch):
    calls = []

    def fake_get_json(url, timeout=2.0):
        calls.append(url)
        if url.endswith("/api/version"):
            return {"version": "0.40.13"}
        if url.endswith("/api/tags"):
            return {"models": [
                {"name": "lfm3:latest", "size": 1_100_000_000},
                {"name": "gpt-oss:20b", "size": 13_000_000_000},
            ]}
        if url.endswith("/v1/models"):
            return {"data": [{"id": "LiquidAI/LFM3-1.7B-GGUF:Q4_K_M"}]}
        raise AssertionError(f"unexpected local URL: {url}")

    monkeypatch.setattr(models, "_get_json", fake_get_json)
    result = models.local_runtime_status({
        "NEXUS_OLLAMA_BASE_URL": "http://127.0.0.1:11434",
        "NEXUS_LLAMACPP_BASE_URL": "http://localhost:8080",
    })
    assert result["any_runtime_reachable"] is True
    assert result["local_model_operational_verified"] is False
    ollama = result["runtimes"]["ollama"]
    assert ollama["status"] == "reachable"
    assert ollama["version"] == "0.40.13"
    assert [row["name"] for row in ollama["installed_models"]] == [
        "lfm3:latest", "gpt-oss:20b"
    ]
    assert result["runtimes"]["llamacpp"]["installed_models"] == [
        {"id": "LiquidAI/LFM3-1.7B-GGUF:Q4_K_M"}
    ]
    assert all(
        result["runtimes"][name]["model_downloads_started"] is False
        and result["runtimes"][name]["server_started_by_nexus"] is False
        for name in ("ollama", "llamacpp")
    )
    assert calls == [
        "http://127.0.0.1:11434/api/version",
        "http://127.0.0.1:11434/api/tags",
        "http://localhost:8080/v1/models",
    ]


def test_local_runtime_rejects_non_loopback_endpoints_without_network(monkeypatch):
    def no_network(url, timeout=2.0):
        raise AssertionError("non-loopback endpoints must be rejected before a request")

    monkeypatch.setattr(models, "_get_json", no_network)
    result = models.local_runtime_status({
        "NEXUS_OLLAMA_BASE_URL": "https://remote.example/api",
        "NEXUS_LLAMACPP_BASE_URL": "http://192.0.2.50:8080",
    })
    assert result["runtimes"]["ollama"]["status"] == "unavailable_or_invalid"
    assert result["runtimes"]["ollama"]["reason"] == "ollama_endpoint_must_be_loopback"
    assert result["runtimes"]["llamacpp"]["reason"] == "llamacpp_endpoint_must_be_loopback"
    assert result["any_runtime_reachable"] is False


def test_loopback_url_validation_rejects_credentials_query_and_redirect_targets():
    for raw in (
        "http://user:password@127.0.0.1:11434",
        "http://127.0.0.1:11434?token=abc",
        "http://127.0.0.1:11434#fragment",
        "ftp://127.0.0.1:11434",
    ):
        with pytest.raises(models.LocalModelRuntimeError):
            models._loopback_base_url(raw, "ollama")


def test_local_model_catalog_api_is_loopback_only_and_does_not_download_models(monkeypatch):
    from modules import ai_worker_coordinator as coordinator
    from nexus_master import app

    with TestClient(
        app, base_url="http://127.0.0.1", client=("127.0.0.1", 54380)
    ) as client:
        response = client.get("/api/nexus/workers/local-models")
    assert response.status_code == 200
    assert response.json()["default_local_agent"] == "lfm3-text"

    with TestClient(
        app, base_url="http://127.0.0.1", client=("192.0.2.80", 54380)
    ) as client:
        blocked = client.get("/api/nexus/workers/local-models")
    assert blocked.status_code == 403


def test_local_runtime_status_api_is_loopback_only_and_reports_no_autostart(monkeypatch):
    from modules import ai_worker_coordinator as coordinator
    from nexus_master import app

    expected = {
        "runtimes": {
            "ollama": {"status": "unavailable_or_invalid", "server_started_by_nexus": False},
            "llamacpp": {"status": "unavailable_or_invalid", "server_started_by_nexus": False},
        },
        "any_runtime_reachable": False,
        "local_model_operational_verified": False,
        "policy": "Loopback discovery only. A reachable API is not proof that a model can infer correctly.",
    }
    monkeypatch.setattr(coordinator, "local_runtime_status", lambda: expected)
    with TestClient(
        app, base_url="http://127.0.0.1", client=("127.0.0.1", 54381)
    ) as client:
        response = client.get("/api/nexus/workers/local-runtime-status")
    assert response.status_code == 200
    assert response.json() == expected

    with TestClient(
        app, base_url="http://127.0.0.1", client=("192.0.2.81", 54381)
    ) as client:
        blocked = client.get("/api/nexus/workers/local-runtime-status")
    assert blocked.status_code == 403
