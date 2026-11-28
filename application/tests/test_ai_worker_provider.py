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

    monkeypatch.setattr(provider, "_transport_open", fake_urlopen)
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

    monkeypatch.setattr(provider, "_transport_open", fake_urlopen)
    result = provider.chat_completion([{"role": "user", "content": "Test"}])
    assert captured["url"] == "http://127.0.0.1:11434/api/chat"
    assert captured["payload"]["stream"] is False
    assert captured["payload"]["options"]["num_ctx"] == 8192
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

    monkeypatch.setattr(provider, "_transport_open", fail_urlopen)
    with pytest.raises(provider.AIProviderError, match="provider_http_500") as error:
        provider.chat_completion([{"role": "user", "content": "test"}])
    assert "sensitive response" not in str(error.value)


def test_transport_disables_proxy_environment_and_rejects_redirects(monkeypatch):
    from urllib.request import ProxyHandler, Request

    captured = {}

    class FakeOpener:
        def open(self, request, timeout):
            captured["url"] = request.full_url
            captured["timeout"] = timeout
            return FakeResponse({"ok": True})

    def fake_build_opener(*handlers):
        captured["handlers"] = handlers
        return FakeOpener()

    monkeypatch.setattr(provider, "build_opener", fake_build_opener)
    response = provider._transport_open(Request("http://127.0.0.1/test"), timeout=7)
    assert json.loads(response.read(100)) == {"ok": True}
    assert any(isinstance(handler, ProxyHandler) and handler.proxies == {}
               for handler in captured["handlers"])
    assert any(isinstance(handler, provider._NoRedirectHandler)
               for handler in captured["handlers"])


def test_redirect_handler_refuses_302_and_307():
    handler = provider._NoRedirectHandler()
    assert handler.redirect_request(None, None, 302, "Found", {}, "https://evil.invalid/") is None
    assert handler.redirect_request(None, None, 307, "Temporary Redirect", {}, "https://evil.invalid/") is None


def test_ollama_context_window_is_configurable_but_bounded(monkeypatch):
    monkeypatch.setenv("NEXUS_AI_PROVIDER", "ollama")
    monkeypatch.setenv("NEXUS_AI_MODEL", "qwen3:4b")
    monkeypatch.setenv("NEXUS_AI_CONTEXT_TOKENS", "4096")
    captured = {}

    def fake_urlopen(request, timeout):
        captured["payload"] = json.loads(request.data.decode("utf-8"))
        return FakeResponse({"message": {"content": "ok"}})

    monkeypatch.setattr(provider, "_transport_open", fake_urlopen)
    provider.chat_completion([{"role": "user", "content": "test"}])
    assert captured["payload"]["options"]["num_ctx"] == 4096

    monkeypatch.setenv("NEXUS_AI_CONTEXT_TOKENS", "512")
    with pytest.raises(provider.AIProviderError, match="context_tokens_out_of_range"):
        provider.chat_completion([{"role": "user", "content": "test"}])

    monkeypatch.setenv("NEXUS_AI_CONTEXT_TOKENS", "not-a-number")
    with pytest.raises(provider.AIProviderError, match="invalid_context_configuration"):
        provider.chat_completion([{"role": "user", "content": "test"}])


def test_ollama_allows_per_worker_model_overrides_for_specialist_routing():
    selected = provider.model_for_worker(
        "mining",
        default_model="lfm3",
        env={
            "NEXUS_AI_PROVIDER": "ollama",
            "NEXUS_AI_MODEL": "lfm3",
            "NEXUS_AI_MODEL_MINING": "qwen3:4b",
        },
    )
    assert selected == "qwen3:4b"


def test_llamacpp_lfm3_pins_worker_to_the_loaded_model():
    selected = provider.model_for_worker(
        "mining",
        default_model="LiquidAI/LFM3-1.7B-GGUF:Q4_K_M",
        env={
            "NEXUS_AI_PROVIDER": "lfm3-local",
            "NEXUS_LFM3_MODEL": "LiquidAI/LFM3-1.7B-GGUF:Q4_K_M",
            "NEXUS_AI_MODEL_MINING": "gpt-oss:20b",
        },
    )
    assert selected == "LiquidAI/LFM3-1.7B-GGUF:Q4_K_M"
