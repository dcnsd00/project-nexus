import asyncio
import sqlite3
import sys
from pathlib import Path

import pytest

CORE_ROOT = Path(__file__).resolve().parents[1] / "core" / "PROJECT-NEXUS-LOCAL"
if str(CORE_ROOT) not in sys.path:
    sys.path.insert(0, str(CORE_ROOT))

from app import lfm3_local


class FakeResponse:
    def __init__(self, payload, status_error=None):
        self.payload = payload
        self.status_error = status_error

    def raise_for_status(self):
        if self.status_error:
            raise self.status_error

    def json(self):
        return self.payload


class FakeClient:
    def __init__(self, response):
        self.response = response
        self.request = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def post(self, url, *, json, headers):
        self.request = {"url": url, "json": json, "headers": headers}
        return self.response


def test_default_endpoint_is_loopback_and_tool_execution_is_not_enabled():
    client = FakeClient(FakeResponse({
        "choices": [{"message": {"content": "Local response"}}]
    }))
    result = asyncio.run(lfm3_local.generate(
        "Check status",
        "security",
        env={},
        client_factory=lambda **kwargs: client,
    ))
    assert result == "Local response"
    assert client.request["url"] == "http://127.0.0.1:8080/v1/chat/completions"
    assert client.request["json"]["model"] == "LiquidAI/LFM3-1.7B"
    assert "tools" not in client.request["json"]
    assert "Authorization" not in client.request["headers"]
    assert "explicit owner approval" in client.request["json"]["messages"][0]["content"].lower()


def test_explicit_local_v1_endpoint_is_not_duplicated():
    endpoint = lfm3_local._endpoint("http://localhost:8080/v1")
    assert endpoint == "http://localhost:8080/v1/chat/completions"


def test_remote_endpoint_requires_explicit_opt_in_and_https():
    with pytest.raises(lfm3_local.LFM3ConfigurationError):
        lfm3_local._endpoint("http://10.0.0.4:8080")
    with pytest.raises(lfm3_local.LFM3ConfigurationError):
        lfm3_local._endpoint("http://10.0.0.4:8080", allow_remote=True)
    assert lfm3_local._endpoint(
        "https://lfm3.internal.example", allow_remote=True
    ) == "https://lfm3.internal.example/v1/chat/completions"


def test_prompt_and_generation_limits_are_enforced():
    with pytest.raises(lfm3_local.LFM3ConfigurationError):
        asyncio.run(lfm3_local.generate("x" * 12001, env={}))
    with pytest.raises(lfm3_local.LFM3ConfigurationError):
        asyncio.run(lfm3_local.generate(
            "hello", env={"NEXUS_LFM3_MAX_TOKENS": "99999"}
        ))


def test_optional_api_key_is_sent_only_as_bearer_header():
    client = FakeClient(FakeResponse({
        "choices": [{"message": {"content": "ok"}}]
    }))
    asyncio.run(lfm3_local.generate(
        "hello",
        env={"NEXUS_LFM3_API_KEY": "local-test-key"},
        client_factory=lambda **kwargs: client,
    ))
    assert client.request["headers"]["Authorization"] == "Bearer local-test-key"


def test_invalid_provider_response_is_rejected():
    client = FakeClient(FakeResponse({"unexpected": "shape"}))
    with pytest.raises(lfm3_local.LFM3ProviderError):
        asyncio.run(lfm3_local.generate(
            "hello", env={}, client_factory=lambda **kwargs: client
        ))


def test_provider_status_reports_configuration_without_claiming_runtime_health():
    status = lfm3_local.provider_status({
        "NEXUS_AI_PROVIDER": "lfm3-local",
        "NEXUS_LFM3_BASE_URL": "http://127.0.0.1:8080",
        "NEXUS_LFM3_MODEL": "LiquidAI/LFM3-1.7B",
    })
    assert status["provider"] == "lfm3-local"
    assert status["configured"] is True
    assert status["endpoint_valid"] is True
    assert "runtime_healthy" not in status


def test_core_chat_can_select_lfm3_without_openai_key(monkeypatch, tmp_path):
    from app import main as core_main

    monkeypatch.setattr(core_main, "DB", str(tmp_path / "nexus_lfm3_test.db"))
    monkeypatch.setenv("NEXUS_AI_PROVIDER", "lfm3-local")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    core_main.init()

    async def fake_generate(message, domain):
        assert message == "summarize edge status"
        assert domain == "security"
        return "LFM3 local test response"

    monkeypatch.setattr(core_main.lfm3_local, "generate", fake_generate)
    result = asyncio.run(core_main.chat(
        core_main.Chat(message="summarize edge status", domain="security")
    ))
    assert result == {
        "reply": "LFM3 local test response",
        "ai_configured": True,
        "provider": "lfm3-local",
    }
    with sqlite3.connect(core_main.DB) as connection:
        rows = connection.execute(
            "SELECT role, content, domain FROM chat ORDER BY id"
        ).fetchall()
    assert rows == [
        ("user", "summarize edge status", "security"),
        ("assistant", "LFM3 local test response", "security"),
    ]
