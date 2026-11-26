import json

import pytest

from modules import ai_worker_provider as provider


class FakeResponse:
    def __init__(self, payload):
        self.payload = json.dumps(payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self, limit):
        return self.payload


def test_provider_is_disabled_by_default_and_does_not_invoke_network():
    status = provider.provider_status(env={})
    assert status["provider_status"] == "unconfigured"
    assert status["configured_model_providers"] == 0
    assert status["model_invocation_enabled"] is False


def test_ollama_local_configuration_uses_loopback_native_chat_endpoint(monkeypatch):
    monkeypatch.setenv("NEXUS_AI_PROVIDER", "ollama")
    monkeypatch.setenv("NEXUS_AI_MODEL", "llama3.2:1b")
    monkeypatch.delenv("NEXUS_AI_BASE_URL", raising=False)
    monkeypatch.delenv("NEXUS_AI_API_KEY", raising=False)
    status = provider.provider_status()
    assert status["provider_status"] == "configured_not_live_verified"
    assert status["model_invocation_enabled"] is True
    assert status["remote"] is False
    assert status["api_key_configured"] is False
    assert status["endpoint"] == "http://127.0.0.1:11434/api"


def test_openai_compatible_local_chat_is_text_only_and_parses_response(monkeypatch):
    monkeypatch.setenv("NEXUS_AI_PROVIDER", "openai_compatible")
    monkeypatch.setenv("NEXUS_AI_MODEL", "local-test-model")
    monkeypatch.setenv("NEXUS_AI_BASE_URL", "http://127.0.0.1:1234/v1")
    captured = {}

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["timeout"] = timeout
        captured["headers"] = {k.lower(): v for k, v in request.header_items()}
        captured["payload"] = json.loads(request.data.decode("utf-8"))
        return FakeResponse({
            "choices": [{"message": {"role": "assistant", "content": "NEXUS analysis"}}],
            "usage": {"prompt_tokens": 12, "completion_tokens": 8},
        })

    monkeypatch.setattr(provider, "urlopen", fake_urlopen)
    result = provider.chat_completion([
        {"role": "system", "content": "You are a mining specialist."},
        {"role": "user", "content": "Compare two benchmark profiles."},
    ])
    assert captured["url"] == "http://127.0.0.1:1234/v1/chat/completions"
    assert "tools" not in captured["payload"]
    assert "tool_choice" not in captured["payload"]
    assert result["content"] == "NEXUS analysis"
    assert result["prompt_tokens"] == 12
    assert result["completion_tokens"] == 8
    assert result["tools_available"] is False
    assert result["side_effects_performed"] is False


def test_ollama_uses_native_api_shape_without_tools(monkeypatch):
    monkeypatch.setenv("NEXUS_AI_PROVIDER", "ollama")
    monkeypatch.setenv("NEXUS_AI_MODEL", "tiny-test")
    captured = {}

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["payload"] = json.loads(request.data.decode("utf-8"))
        return FakeResponse({
            "message": {"role": "assistant", "content": "Local model response"},
            "prompt_eval_count": 4,
            "eval_count": 6,
        })

    monkeypatch.setattr(provider, "urlopen", fake_urlopen)
    result = provider.chat_completion([{"role": "user", "content": "Test"}])
    assert captured["url"] == "http://127.0.0.1:11434/api/chat"
    assert captured["payload"]["stream"] is False
    assert "tools" not in captured["payload"]
    assert result["content"] == "Local model response"
    assert result["prompt_tokens"] == 4
    assert result["completion_tokens"] == 6


def test_remote_endpoint_requires_explicit_flag_allowlist_https_and_key():
    base = {
        "NEXUS_AI_PROVIDER": "openai_compatible",
        "NEXUS_AI_MODEL": "test-model",
        "NEXUS_AI_BASE_URL": "https://api.example.net/v1",
    }
    assert provider.provider_status(env=base)["model_invocation_enabled"] is False

    enabled = {
        **base,
        "NEXUS_AI_ALLOW_REMOTE": "1",
        "NEXUS_AI_REMOTE_HOST_ALLOWLIST": "api.example.net",
        "NEXUS_AI_API_KEY": "not-a-real-secret",
    }
    status = provider.provider_status(env=enabled)
    assert status["model_invocation_enabled"] is True
    assert status["remote"] is True
    assert "not-a-real-secret" not in repr(status)


def test_remote_endpoint_rejects_unlisted_host_and_non_https():
    allow = {
        "NEXUS_AI_PROVIDER": "openai_compatible",
        "NEXUS_AI_MODEL": "test-model",
        "NEXUS_AI_ALLOW_REMOTE": "1",
        "NEXUS_AI_REMOTE_HOST_ALLOWLIST": "api.example.net",
        "NEXUS_AI_API_KEY": "not-a-real-secret",
    }
    unlisted = provider.provider_status(env={
        **allow, "NEXUS_AI_BASE_URL": "https://attacker.example/v1"
    })
    non_https = provider.provider_status(env={
        **allow, "NEXUS_AI_BASE_URL": "http://api.example.net/v1"
    })
    assert unlisted["model_invocation_enabled"] is False
    assert unlisted["configuration_error"] == "remote_host_not_allowlisted"
    assert non_https["model_invocation_enabled"] is False
    assert non_https["configuration_error"] == "remote_provider_requires_https_443"


def test_invalid_messages_and_provider_http_errors_are_sanitized(monkeypatch):
    monkeypatch.setenv("NEXUS_AI_PROVIDER", "ollama")
    monkeypatch.setenv("NEXUS_AI_MODEL", "tiny-test")
    with pytest.raises(provider.AIProviderError, match="empty_message"):
        provider.chat_completion([{"role": "user", "content": ""}])

    from urllib.error import HTTPError

    def fail_urlopen(request, timeout):
        raise HTTPError(request.full_url, 500, "sensitive response", {}, None)

    monkeypatch.setattr(provider, "urlopen", fail_urlopen)
    with pytest.raises(provider.AIProviderError, match="provider_http_500") as error:
        provider.chat_completion([{"role": "user", "content": "test"}])
    assert "sensitive response" not in str(error.value)
