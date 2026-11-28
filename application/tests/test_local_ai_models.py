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


def test_explicit_ollama_model_pull_uses_only_allowlisted_model_and_tracks_progress(monkeypatch):
    models._PULLS.clear()
    monkeypatch.setattr(
        models,
        "_get_json",
        lambda url, timeout=2.0: {"version": "test"} if url.endswith("/api/version") else {},
    )
    captured = {}

    class FakePullResponse:
        def __init__(self):
            self.lines = [
                b'{"status":"pulling manifest"}\\n',
                b'{"status":"downloading","total":100,"completed":100}\\n',
                b'{"status":"success"}\\n',
            ]

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def readline(self, limit):
            return self.lines.pop(0) if self.lines else b""

    def fake_open(request, timeout):
        captured["url"] = request.full_url
        captured["method"] = request.get_method()
        captured["payload"] = json.loads(request.data.decode("utf-8"))
        return FakePullResponse()

    monkeypatch.setattr(models, "_ollama_pull_open", fake_open)
    started = models.start_ollama_model_pull(
        "qwen3-4b",
        env={"NEXUS_OLLAMA_BASE_URL": "http://127.0.0.1:11434"},
    )
    thread = models._PULLS["qwen3-4b"]["thread"]
    thread.join(timeout=2.0)
    status = models.ollama_model_pull_status("qwen3-4b")

    assert captured["url"] == "http://127.0.0.1:11434/api/pull"
    assert captured["method"] == "POST"
    assert captured["payload"] == {"name": "qwen3:4b", "stream": True}
    assert status["status"] == "completed"
    assert status["model_downloaded"] is True
    assert status["progress_percent"] == 100.0
    assert status["operational_verified"] is False
    assert started["profile_id"] == "qwen3-4b"


def test_ollama_pull_rejects_profiles_not_in_explicit_download_allowlist():
    with pytest.raises(models.LocalModelRuntimeError, match="model_profile_not_allowlisted_for_ollama_pull"):
        models.start_ollama_model_pull("lfm3-vision", env={})


def test_ollama_pull_requires_an_already_running_loopback_service(monkeypatch):
    monkeypatch.setattr(
        models,
        "_get_json",
        lambda url, timeout=2.0: (_ for _ in ()).throw(models.LocalModelRuntimeError("local_runtime_timeout")),
    )
    with pytest.raises(models.LocalModelRuntimeError, match="local_runtime_timeout"):
        models.start_ollama_model_pull(
            "lfm3-text",
            env={"NEXUS_OLLAMA_BASE_URL": "http://127.0.0.1:11434"},
        )


def test_ollama_pull_rejects_non_loopback_runtime_before_request(monkeypatch):
    monkeypatch.setattr(
        models,
        "_get_json",
        lambda url, timeout=2.0: (_ for _ in ()).throw(AssertionError("network must not be called")),
    )
    with pytest.raises(models.LocalModelRuntimeError, match="ollama_endpoint_must_be_loopback"):
        models.start_ollama_model_pull(
            "lfm3-text",
            env={"NEXUS_OLLAMA_BASE_URL": "https://remote.example"},
        )


def test_ollama_pull_api_is_loopback_only_and_progress_is_read_only(monkeypatch):
    from modules import ai_worker_coordinator as coordinator
    from nexus_master import app

    expected = {
        "profile_id": "qwen3-4b",
        "model": "qwen3:4b",
        "status": "running",
        "operational_verified": False,
        "model_downloaded": False,
        "total_bytes": 100,
        "completed_bytes": 25,
        "progress_percent": 25.0,
        "last_message": "downloading",
        "started_at": "2026-11-28T00:00:00+00:00",
        "finished_at": None,
        "failure_type": None,
    }
    monkeypatch.setattr(coordinator, "start_ollama_model_pull", lambda profile_id: expected)
    monkeypatch.setattr(coordinator, "ollama_model_pull_status", lambda profile_id: expected)
    with TestClient(app, base_url="http://127.0.0.1",
                    client=("127.0.0.1", 54382)) as client:
        started = client.post("/api/nexus/workers/local-models/qwen3-4b/pull")
        status = client.get("/api/nexus/workers/local-models/pulls/qwen3-4b")
    assert started.status_code == 200
    assert status.status_code == 200
    assert status.json()["progress_percent"] == 25.0
    assert status.json()["operational_verified"] is False

    with TestClient(app, base_url="http://127.0.0.1",
                    client=("192.0.2.82", 54382)) as client:
        blocked = client.post("/api/nexus/workers/local-models/qwen3-4b/pull")
    assert blocked.status_code == 403
