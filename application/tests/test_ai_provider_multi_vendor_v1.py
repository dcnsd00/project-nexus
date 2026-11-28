"""Native protocol contract tests for NEXUS AI provider adapters."""
import json

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


def test_anthropic_native_messages_protocol_and_secret_safety(monkeypatch):
    monkeypatch.setenv("NEXUS_AI_PROVIDER", "anthropic")
    monkeypatch.setenv("NEXUS_AI_MODEL", "claude-opus-test")
    monkeypatch.setenv("NEXUS_AI_ALLOW_REMOTE", "1")
    monkeypatch.setenv("NEXUS_AI_REMOTE_HOST_ALLOWLIST", "api.anthropic.com")
    monkeypatch.setenv("NEXUS_AI_API_KEY", "unit-test-secret")
    captured = {}

    def fake_transport(request, timeout):
        captured["url"] = request.full_url
        captured["headers"] = {k.lower(): v for k, v in request.header_items()}
        captured["payload"] = json.loads(request.data.decode("utf-8"))
        return FakeResponse({
            "content": [{"type": "text", "text": "Claude adapter OK"}],
            "usage": {"input_tokens": 11, "output_tokens": 7},
        })

    monkeypatch.setattr(provider, "_transport_open", fake_transport)
    result = provider.chat_completion([
        {"role": "system", "content": "NEXUS system rules."},
        {"role": "user", "content": "Check adapter."},
    ])
    assert captured["url"] == "https://api.anthropic.com/v1/messages"
    assert captured["headers"]["authorization"] == "Bearer unit-test-secret"
    assert captured["headers"]["anthropic-version"] == "2026-10-21"
    assert captured["payload"]["system"] == "NEXUS system rules."
    assert captured["payload"]["messages"] == [{"role": "user", "content": "Check adapter."}]
    assert "tools" not in captured["payload"]
    assert result["content"] == "Claude adapter OK"
    assert result["provider"] == "anthropic"
    assert result["prompt_tokens"] == 11
    assert result["completion_tokens"] == 7
    assert "unit-test-secret" not in repr(provider.provider_status())


def test_gemini_native_generate_content_protocol(monkeypatch):
    monkeypatch.setenv("NEXUS_AI_PROVIDER", "gemini")
    monkeypatch.setenv("NEXUS_AI_MODEL", "gemini-3.8-flash")
    monkeypatch.setenv("NEXUS_AI_ALLOW_REMOTE", "1")
    monkeypatch.setenv("NEXUS_AI_REMOTE_HOST_ALLOWLIST", "generativelanguage.googleapis.com")
    monkeypatch.setenv("NEXUS_AI_API_KEY", "unit-test-gemini-secret")
    captured = {}

    def fake_transport(request, timeout):
        captured["url"] = request.full_url
        captured["headers"] = {k.lower(): v for k, v in request.header_items()}
        captured["payload"] = json.loads(request.data.decode("utf-8"))
        return FakeResponse({
            "candidates": [{
                "content": {"parts": [{"text": "Gemini adapter"}, {"text": " works"}]}
            }],
            "usageMetadata": {"promptTokenCount": 13, "candidatesTokenCount": 9},
        })

    monkeypatch.setattr(provider, "_transport_open", fake_transport)
    result = provider.chat_completion([
        {"role": "system", "content": "Follow NEXUS safety rules."},
        {"role": "user", "content": "Check adapter."},
        {"role": "assistant", "content": "Previous result."},
    ])
    assert captured["url"] == (
        "https://generativelanguage.googleapis.com/v1beta/"
        "models/gemini-3.8-flash:generateContent"
    )
    assert captured["headers"]["x-goog-api-key"] == "unit-test-gemini-secret"
    assert "authorization" not in captured["headers"]
    assert captured["payload"]["systemInstruction"]["parts"][0]["text"] == "Follow NEXUS safety rules."
    assert captured["payload"]["contents"][1]["role"] == "model"
    assert "tools" not in captured["payload"]
    assert result["content"] == "Gemini adapter works"
    assert result["provider"] == "gemini"
    assert result["prompt_tokens"] == 13
    assert result["completion_tokens"] == 9


def test_openai_native_default_uses_official_chat_completions_contract(monkeypatch):
    monkeypatch.setenv("NEXUS_AI_PROVIDER", "openai")
    monkeypatch.setenv("NEXUS_AI_MODEL", "gpt-test")
    monkeypatch.setenv("NEXUS_AI_ALLOW_REMOTE", "1")
    monkeypatch.setenv("NEXUS_AI_REMOTE_HOST_ALLOWLIST", "api.openai.com")
    monkeypatch.setenv("NEXUS_AI_API_KEY", "unit-test-openai-secret")
    captured = {}

    def fake_transport(request, timeout):
        captured["url"] = request.full_url
        captured["payload"] = json.loads(request.data.decode("utf-8"))
        return FakeResponse({
            "choices": [{"message": {"role": "assistant", "content": "OpenAI adapter OK"}}],
            "usage": {"prompt_tokens": 5, "completion_tokens": 4},
        })

    monkeypatch.setattr(provider, "_transport_open", fake_transport)
    result = provider.chat_completion([{"role": "user", "content": "test"}])
    assert captured["url"] == "https://api.openai.com/v1/chat/completions"
    assert captured["payload"]["model"] == "gpt-test"
    assert "tools" not in captured["payload"]
    assert result["content"] == "OpenAI adapter OK"
    assert result["provider"] == "openai"


def test_known_openai_compatible_vendors_are_supported_with_explicit_host_allowlist():
    vendors = {
        "groq": "api.groq.com",
        "openrouter": "openrouter.ai",
        "mistral": "api.mistral.ai",
        "together": "api.together.xyz",
        "deepseek": "api.deepseek.com",
        "fireworks": "api.fireworks.ai",
        "cerebras": "api.cerebras.ai",
    }
    for name, host in vendors.items():
        config = provider._safe_config({
            "NEXUS_AI_PROVIDER": name,
            "NEXUS_AI_MODEL": "vendor-model",
            "NEXUS_AI_BASE_URL": f"https://{host}/v1",
            "NEXUS_AI_ALLOW_REMOTE": "1",
            "NEXUS_AI_REMOTE_HOST_ALLOWLIST": host,
            "NEXUS_AI_API_KEY": "test-secret",
        })
        assert config.provider == name
        assert config.protocol == "openai_compatible"
        assert config.endpoint == "chat/completions"


def test_native_vendor_rejects_wrong_host_even_when_allowlisted():
    status = provider.provider_status(env={
        "NEXUS_AI_PROVIDER": "anthropic",
        "NEXUS_AI_MODEL": "claude-test",
        "NEXUS_AI_BASE_URL": "https://attacker.example/v1",
        "NEXUS_AI_ALLOW_REMOTE": "1",
        "NEXUS_AI_REMOTE_HOST_ALLOWLIST": "attacker.example",
        "NEXUS_AI_API_KEY": "test-secret",
    })
    assert status["model_invocation_enabled"] is False
    assert status["configuration_error"] == "provider_host_mismatch_use_openai_compatible"


def test_provider_status_reports_registered_protocols_but_not_live_success(monkeypatch):
    monkeypatch.setenv("NEXUS_AI_PROVIDER", "ollama")
    monkeypatch.setenv("NEXUS_AI_MODEL", "llama3.2:1b")
    status = provider.provider_status()
    assert status["provider_status"] == "configured_not_live_verified"
    assert status["protocol"] == "ollama"
    assert status["model_invocation_enabled"] is True
    assert status["supported_providers"] == [
        "openai", "anthropic", "gemini", "ollama", "openai_compatible",
        "groq", "openrouter", "mistral", "together", "deepseek", "fireworks", "cerebras",
    ]


def test_provider_live_probe_marks_only_the_exact_config_as_verified(monkeypatch):
    monkeypatch.setenv("NEXUS_AI_PROVIDER", "ollama")
    monkeypatch.setenv("NEXUS_AI_MODEL", "probe-model")
    monkeypatch.delenv("NEXUS_AI_BASE_URL", raising=False)
    monkeypatch.delenv("NEXUS_AI_API_KEY", raising=False)
    monkeypatch.setattr(
        provider,
        "_transport_open",
        lambda request, timeout: FakeResponse({
            "message": {"content": "NEXUS_PROVIDER_HEALTH_OK"},
            "prompt_eval_count": 8,
            "eval_count": 2,
        }),
    )

    result = provider.probe_ai_provider()
    assert result["operational_verified"] is True
    assert result["status"] == "live_verified"
    assert result["provider"] == "ollama"
    assert provider.provider_status()["operational_verified"] is True

    monkeypatch.setenv("NEXUS_AI_MODEL", "different-model")
    assert provider.provider_status()["operational_verified"] is False


def test_provider_live_probe_fails_if_model_does_not_return_exact_marker(monkeypatch):
    monkeypatch.setenv("NEXUS_AI_PROVIDER", "ollama")
    monkeypatch.setenv("NEXUS_AI_MODEL", "probe-model")
    monkeypatch.setattr(
        provider,
        "_transport_open",
        lambda request, timeout: FakeResponse({
            "message": {"content": "I can help with that."},
        }),
    )
    import pytest
    with pytest.raises(provider.AIProviderError, match="provider_probe_response_mismatch"):
        provider.probe_ai_provider()


def test_provider_live_test_api_is_loopback_only_and_reports_real_probe(monkeypatch):
    from fastapi.testclient import TestClient
    from nexus_master import app

    monkeypatch.setenv("NEXUS_AI_PROVIDER", "ollama")
    monkeypatch.setenv("NEXUS_AI_MODEL", "probe-model")
    monkeypatch.setattr(
        provider,
        "_transport_open",
        lambda request, timeout: FakeResponse({
            "message": {"content": "NEXUS_PROVIDER_HEALTH_OK"},
        }),
    )
    with TestClient(app, base_url="http://127.0.0.1",
                    client=("127.0.0.1", 54220)) as client:
        response = client.post("/api/nexus/workers/provider-test")
    assert response.status_code == 200
    assert response.json()["operational_verified"] is True
    assert response.json()["tools_available"] is False

    with TestClient(app, base_url="http://127.0.0.1",
                    client=("192.0.2.25", 54220)) as client:
        blocked = client.post("/api/nexus/workers/provider-test")
    assert blocked.status_code == 403


def test_lfm3_local_provider_uses_loopback_llamacpp_server_without_api_key(monkeypatch):
    monkeypatch.setenv("NEXUS_AI_PROVIDER", "lfm3-local")
    monkeypatch.delenv("NEXUS_AI_MODEL", raising=False)
    monkeypatch.delenv("NEXUS_AI_BASE_URL", raising=False)
    monkeypatch.delenv("NEXUS_LFM3_BASE_URL", raising=False)
    monkeypatch.delenv("NEXUS_AI_API_KEY", raising=False)
    monkeypatch.delenv("NEXUS_LFM3_API_KEY", raising=False)
    config = provider._safe_config(dict(__import__("os").environ))
    assert config.provider == "lfm3"
    assert config.protocol == "openai_compatible"
    assert config.model == "LiquidAI/LFM3-1.7B-GGUF:Q4_K_M"
    assert config.base_url == "http://127.0.0.1:8080/v1"
    assert config.endpoint == "chat/completions"
    assert config.remote is False
    assert config.api_key is None


def test_lfm3_local_provider_sends_openai_compatible_chat_request(monkeypatch):
    monkeypatch.setenv("NEXUS_AI_PROVIDER", "lfm3-local")
    monkeypatch.setenv("NEXUS_LFM3_BASE_URL", "http://127.0.0.1:8080")
    monkeypatch.setenv("NEXUS_LFM3_MODEL", "LiquidAI/LFM3-1.7B-GGUF:Q4_K_M")
    captured = {}

    def fake_transport(request, timeout):
        captured["url"] = request.full_url
        captured["headers"] = {k.lower(): v for k, v in request.header_items()}
        captured["payload"] = json.loads(request.data.decode("utf-8"))
        return FakeResponse({
            "choices": [{"message": {"role": "assistant", "content": "LFM3 local inference OK"}}],
            "usage": {"prompt_tokens": 12, "completion_tokens": 8},
        })

    monkeypatch.setattr(provider, "_transport_open", fake_transport)
    result = provider.chat_completion([{"role": "user", "content": "Check local inference."}])
    assert captured["url"] == "http://127.0.0.1:8080/v1/chat/completions"
    assert captured["payload"]["model"] == "LiquidAI/LFM3-1.7B-GGUF:Q4_K_M"
    assert captured["payload"]["stream"] is False
    assert "tools" not in captured["payload"]
    assert "authorization" not in captured["headers"]
    assert result["content"] == "LFM3 local inference OK"
    assert result["provider"] == "lfm3"
    assert result["remote"] is False


def test_lfm3_remote_endpoint_remains_opt_in_and_allowlisted():
    base = {
        "NEXUS_AI_PROVIDER": "lfm3-local",
        "NEXUS_LFM3_MODEL": "LiquidAI/LFM3-1.7B",
        "NEXUS_LFM3_BASE_URL": "https://lfm3.example.net/v1",
        "NEXUS_LFM3_API_KEY": "unit-test-key",
    }
    blocked = provider.provider_status(env=base)
    assert blocked["model_invocation_enabled"] is False

    enabled = {
        **base,
        "NEXUS_LFM3_ALLOW_REMOTE": "1",
        "NEXUS_LFM3_REMOTE_HOST_ALLOWLIST": "lfm3.example.net",
    }
    allowed = provider.provider_status(env=enabled)
    assert allowed["model_invocation_enabled"] is True
    assert allowed["remote"] is True
    assert allowed["api_key_configured"] is True
