"""Opt-in text-only provider adapters for NEXUS specialist workers.

Native protocols: OpenAI Chat Completions, Anthropic Messages, Gemini
generateContent and Ollama /api/chat. OpenAI-compatible endpoints also support
Groq, OpenRouter, Mistral, Together, DeepSeek, Fireworks and Cerebras.
Remote calls require explicit enablement, HTTPS, exact hostname allowlisting
and an API key. No tools/function calls are sent to the model.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import ipaddress
import json
import os
import threading
from typing import Any, Mapping
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlsplit, urlunsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener


MAX_MESSAGES = 12
MAX_TOTAL_MESSAGE_CHARS = 40_000
MAX_RESPONSE_CHARS = 30_000
LIVE_VERIFICATION_MAX_AGE_SECONDS = 900
_REQUEST_SLOT = threading.BoundedSemaphore(1)
_LIVE_VERIFICATION_LOCK = threading.Lock()
_LIVE_VERIFICATION: dict[str, Any] = {}


class AIProviderError(RuntimeError):
    """Safe provider configuration, transport or response error."""


@dataclass(frozen=True)
class ProviderConfig:
    provider: str
    protocol: str
    model: str
    base_url: str
    api_key: str | None
    timeout_seconds: float
    endpoint: str
    remote: bool
    auth_header: str | None = None
    api_version: str | None = None


def _is_loopback(host: str | None) -> bool:
    if not host:
        return False
    name = host.casefold().rstrip(".")
    if name == "localhost":
        return True
    try:
        return ipaddress.ip_address(name).is_loopback
    except ValueError:
        return False


def _bounded_timeout(env: Mapping[str, str]) -> float:
    raw = env.get("NEXUS_AI_TIMEOUT_SECONDS", "60")
    try:
        value = float(raw)
    except (TypeError, ValueError):
        raise AIProviderError("invalid_timeout_configuration") from None
    if not 5.0 <= value <= 120.0:
        raise AIProviderError("timeout_out_of_range")
    return value


def _safe_config(env: Mapping[str, str]) -> ProviderConfig | None:
    raw_provider = str(env.get("NEXUS_AI_PROVIDER", "disabled")).strip().casefold()
    if raw_provider in {"", "disabled", "none", "off"}:
        return None

    aliases = {
        "openai-compatible": "openai_compatible",
        "lm_studio": "openai_compatible",
        "lm-studio": "openai_compatible",
        "vllm": "openai_compatible",
        "lfm3-local": "lfm3",
        "lfm3_local": "lfm3",
        "llamacpp-lfm3": "lfm3",
    }
    provider = aliases.get(raw_provider, raw_provider)
    protocols = {
        "ollama": "ollama",
        "lfm3": "openai_compatible",
        "openai": "openai_compatible",
        "openai_compatible": "openai_compatible",
        "anthropic": "anthropic",
        "gemini": "gemini",
        "groq": "openai_compatible",
        "openrouter": "openai_compatible",
        "mistral": "openai_compatible",
        "together": "openai_compatible",
        "deepseek": "openai_compatible",
        "fireworks": "openai_compatible",
        "cerebras": "openai_compatible",
    }
    protocol = protocols.get(provider)
    if protocol is None:
        raise AIProviderError("unsupported_provider")

    known_hosts = {
        "openai": "api.openai.com",
        "anthropic": "api.anthropic.com",
        "gemini": "generativelanguage.googleapis.com",
        "groq": "api.groq.com",
        "openrouter": "openrouter.ai",
        "mistral": "api.mistral.ai",
        "together": "api.together.xyz",
        "deepseek": "api.deepseek.com",
        "fireworks": "api.fireworks.ai",
        "cerebras": "api.cerebras.ai",
    }
    model_env_name = {
        "openai": "OPENAI_MODEL",
        "anthropic": "ANTHROPIC_MODEL",
        "gemini": "GEMINI_MODEL",
        "ollama": "OLLAMA_MODEL",
        "lfm3": "NEXUS_LFM3_MODEL",
    }.get(provider)
    default_models = {
        "ollama": "lfm3",
        "lfm3": "LiquidAI/LFM3-1.7B-GGUF:Q4_K_M",
    }
    model = str(
        env.get("NEXUS_AI_MODEL")
        or (env.get(model_env_name, "") if model_env_name else "")
        or default_models.get(provider, "")
    ).strip()
    if not model or len(model) > 160 or any(ord(c) < 32 for c in model):
        raise AIProviderError("model_not_configured")

    default_urls = {
        "ollama": "http://127.0.0.1:11434/api",
        "lfm3": "http://127.0.0.1:8080/v1",
        "openai": "https://api.openai.com/v1",
        "anthropic": "https://api.anthropic.com",
        "gemini": "https://generativelanguage.googleapis.com/v1beta",
    }
    provider_base_override = (
        env.get("NEXUS_LFM3_BASE_URL", "")
        if provider == "lfm3"
        else ""
    )
    raw_url = str(
        env.get("NEXUS_AI_BASE_URL")
        or provider_base_override
        or default_urls.get(provider, "")
    ).strip()
    if not raw_url or len(raw_url) > 500:
        raise AIProviderError("base_url_not_configured")

    try:
        parts = urlsplit(raw_url)
        host = parts.hostname
        port = parts.port
    except ValueError:
        raise AIProviderError("invalid_base_url") from None
    if (
        parts.scheme not in {"http", "https"}
        or not host
        or parts.username is not None
        or parts.password is not None
        or parts.query
        or parts.fragment
    ):
        raise AIProviderError("invalid_base_url")

    normalized_host = host.casefold().rstrip(".")
    remote = not _is_loopback(host)
    key_env_name = {
        "openai": "OPENAI_API_KEY",
        "anthropic": "ANTHROPIC_API_KEY",
        "gemini": "GEMINI_API_KEY",
        "ollama": "OLLAMA_API_KEY",
    }.get(provider)
    provider_key = str(env.get("NEXUS_LFM3_API_KEY", "")) if provider == "lfm3" else ""
    api_key = str(
        env.get("NEXUS_AI_API_KEY")
        or provider_key
        or (env.get(key_env_name, "") if key_env_name else "")
    ).strip() or None
    path = parts.path.rstrip("/")

    if remote:
        remote_allowed = env.get("NEXUS_AI_ALLOW_REMOTE", "").strip() == "1"
        if provider == "lfm3" and env.get("NEXUS_LFM3_ALLOW_REMOTE", "").strip() == "1":
            remote_allowed = True
        if not remote_allowed:
            raise AIProviderError("remote_provider_not_explicitly_enabled")
        if parts.scheme != "https" or port not in (None, 443):
            raise AIProviderError("remote_provider_requires_https_443")
        allowlist_text = str(env.get("NEXUS_AI_REMOTE_HOST_ALLOWLIST", ""))
        if provider == "lfm3":
            allowlist_text += "," + str(env.get("NEXUS_LFM3_REMOTE_HOST_ALLOWLIST", ""))
        allowed_hosts = {
            item.strip().casefold().rstrip(".")
            for item in allowlist_text.split(",")
            if item.strip()
        }
        if normalized_host not in allowed_hosts:
            raise AIProviderError("remote_host_not_allowlisted")
        expected_host = known_hosts.get(provider)
        if expected_host and normalized_host != expected_host:
            raise AIProviderError("provider_host_mismatch_use_openai_compatible")
        if not api_key:
            raise AIProviderError("remote_api_key_not_configured")

    if protocol == "ollama":
        if remote:
            raise AIProviderError("ollama_native_provider_must_be_local")
        if path not in {"", "/", "/api"}:
            raise AIProviderError("ollama_base_url_must_target_api_root")
        base_path, endpoint = "/api", "chat"
        auth_header = "Authorization" if api_key else None
        api_version = None
    elif protocol == "anthropic":
        if path not in {"", "/", "/v1"}:
            raise AIProviderError("anthropic_base_url_must_target_api_root_or_v1")
        base_path = "/v1"
        endpoint = "messages"
        auth_header = "Authorization" if api_key else None
        api_version = str(env.get("NEXUS_AI_ANTHROPIC_VERSION", "2026-10-21")).strip()
        if not api_version or len(api_version) > 40 or any(ord(c) < 32 for c in api_version):
            raise AIProviderError("invalid_anthropic_api_version")
    elif protocol == "gemini":
        if path not in {"/v1beta", "/v1"}:
            raise AIProviderError("gemini_base_url_must_target_v1beta_or_v1")
        base_path = path
        endpoint = f"models/{quote(model, safe='')}:generateContent"
        auth_header = "x-goog-api-key" if api_key else None
        api_version = None
    else:
        if path not in {"", "/v1", "/api/v1", "/"}:
            raise AIProviderError("openai_compatible_base_url_must_target_v1")
        base_path = path or "/v1"
        endpoint = "chat/completions"
        auth_header = "Authorization" if api_key else None
        api_version = None

    base = urlunsplit((parts.scheme, parts.netloc, base_path, "", "")).rstrip("/")
    return ProviderConfig(
        provider=provider,
        protocol=protocol,
        model=model,
        base_url=base,
        api_key=api_key,
        timeout_seconds=_bounded_timeout(env),
        endpoint=endpoint,
        remote=remote,
        auth_header=auth_header,
        api_version=api_version,
    )


def _provider_fingerprint(config: ProviderConfig) -> str:
    """Hash provider identity and credentials without exposing the credential."""
    value = "|".join((config.provider, config.model, config.base_url, config.api_key or ""))
    return sha256(value.encode("utf-8")).hexdigest()


def provider_status(env: Mapping[str, str] | None = None) -> dict[str, Any]:
    """Return safe config status; never echo keys or raw credentials."""
    source = os.environ if env is None else env
    try:
        config = _safe_config(source)
    except AIProviderError as exc:
        return {
            "provider_status": "misconfigured",
            "provider": str(source.get("NEXUS_AI_PROVIDER", "disabled")).strip().casefold(),
            "supported_providers": ["lfm3", "ollama", "openai", "anthropic", "gemini", "openai_compatible", "groq", "openrouter", "mistral", "together", "deepseek", "fireworks", "cerebras"],
            "model": None,
            "endpoint": None,
            "remote": False,
            "api_key_configured": bool(str(source.get("NEXUS_AI_API_KEY", "")).strip()),
            "configured_model_providers": 0,
            "active_ai_agents": 0,
            "model_invocation_enabled": False,
            "configuration_error": str(exc),
        }

    if config is None:
        return {
            "provider_status": "unconfigured",
            "provider": "disabled",
            "supported_providers": ["lfm3", "ollama", "openai", "anthropic", "gemini", "openai_compatible", "groq", "openrouter", "mistral", "together", "deepseek", "fireworks", "cerebras"],
            "model": None,
            "endpoint": None,
            "remote": False,
            "api_key_configured": False,
            "configured_model_providers": 0,
            "active_ai_agents": 0,
            "model_invocation_enabled": False,
            "configuration_error": None,
        }

    live_verified = False
    last_verified_at = None
    if env is None:
        with _LIVE_VERIFICATION_LOCK:
            verification = dict(_LIVE_VERIFICATION)
        if verification.get("fingerprint") == _provider_fingerprint(config):
            try:
                verified_at = datetime.fromisoformat(verification.get("observed_at", ""))
                age = (datetime.now(timezone.utc) - verified_at).total_seconds()
                live_verified = 0 <= age <= LIVE_VERIFICATION_MAX_AGE_SECONDS
                if live_verified:
                    last_verified_at = verification.get("observed_at")
            except (TypeError, ValueError):
                live_verified = False

    return {
        "provider_status": "live_verified" if live_verified else "configured_not_live_verified",
        "provider": config.provider,
        "live_connection_verified": live_verified,
        "operational_verified": live_verified,
        "last_verified_at": last_verified_at,
        "protocol": config.protocol,
        "model_family": "LFM3" if config.provider == "lfm3" else None,
        "weights_run_locally": bool(not config.remote and config.provider in {"lfm3", "ollama"}),
        "supported_providers": ["lfm3", "ollama", "openai", "anthropic", "gemini", "openai_compatible", "groq", "openrouter", "mistral", "together", "deepseek", "fireworks", "cerebras"],
        "model": config.model,
        "endpoint": f"{urlsplit(config.base_url).scheme}://{urlsplit(config.base_url).netloc}{urlsplit(config.base_url).path}",
        "remote": config.remote,
        "api_key_configured": bool(config.api_key),
        "configured_model_providers": 1,
        "active_ai_agents": 0,
        "model_invocation_enabled": True,
        "configuration_error": None,
    }


def probe_ai_provider(env: Mapping[str, str] | None = None) -> dict[str, Any]:
    """Perform a bounded real model round-trip; never expose the probe text."""
    source = os.environ if env is None else env
    config = _safe_config(source)
    if config is None:
        raise AIProviderError("ai_provider_not_configured")
    if env is None:
        # A failed new probe must not leave an older success looking current.
        with _LIVE_VERIFICATION_LOCK:
            _LIVE_VERIFICATION.clear()
    marker = "NEXUS_PROVIDER_HEALTH_OK"
    result = chat_completion(
        [
            {
                "role": "system",
                "content": "You are checking a NEXUS text-only provider connection. Reply with the exact token requested and nothing else.",
            },
            {
                "role": "user",
                "content": f"Return exactly {marker}. Do not add punctuation or other text.",
            },
        ],
        model=config.model,
        env=source,
    )
    if result["content"].strip() != marker:
        raise AIProviderError("provider_probe_response_mismatch")
    observed_at = datetime.now(timezone.utc).isoformat()
    if env is None:
        with _LIVE_VERIFICATION_LOCK:
            _LIVE_VERIFICATION.clear()
            _LIVE_VERIFICATION.update({
                "fingerprint": _provider_fingerprint(config),
                "observed_at": observed_at,
                "provider": config.provider,
                "model": config.model,
                "remote": config.remote,
            })
    return {
        "provider": config.provider,
        "protocol": config.protocol,
        "model": config.model,
        "remote": config.remote,
        "status": "live_verified",
        "operational_verified": True,
        "observed_at": observed_at,
        "tools_available": False,
        "tool_calls_executed": 0,
        "side_effects_performed": False,
        "prompt_tokens": result.get("prompt_tokens"),
        "completion_tokens": result.get("completion_tokens"),
    }


def model_for_worker(worker_id: str, default_model: str | None = None,
                     env: Mapping[str, str] | None = None) -> str:
    """Optional per-domain model override; no secret or endpoint is involved."""
    source = os.environ if env is None else env
    suffix = "".join(ch if ch.isalnum() else "_" for ch in worker_id.upper())
    override = str(source.get(f"NEXUS_AI_MODEL_{suffix}", "")).strip()
    return override or default_model or str(source.get("NEXUS_AI_MODEL", "")).strip()



class _NoRedirectHandler(HTTPRedirectHandler):
    """Prevent credential-bearing model requests from following redirects."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _transport_open(request: Request, timeout: float):
    """Use a direct connection, ignore proxy environment variables and reject redirects."""
    opener = build_opener(ProxyHandler({}), _NoRedirectHandler())
    return opener.open(request, timeout=timeout)


def chat_completion(
    messages: list[dict[str, str]],
    *,
    model: str | None = None,
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Send one bounded text-only request. No tool definitions are supported."""
    source = os.environ if env is None else env
    config = _safe_config(source)
    if config is None:
        raise AIProviderError("ai_provider_not_configured")
    if not isinstance(messages, list) or not 1 <= len(messages) <= MAX_MESSAGES:
        raise AIProviderError("invalid_message_count")

    total = 0
    normalized: list[dict[str, str]] = []
    for message in messages:
        if not isinstance(message, dict) or message.get("role") not in {"system", "user", "assistant"}:
            raise AIProviderError("invalid_message")
        content = message.get("content")
        if not isinstance(content, str) or not content.strip():
            raise AIProviderError("empty_message")
        total += len(content)
        normalized.append({"role": message["role"], "content": content})
    if total > MAX_TOTAL_MESSAGE_CHARS:
        raise AIProviderError("input_too_large")

    effective_model = (model or config.model).strip()
    if not effective_model or len(effective_model) > 160:
        raise AIProviderError("invalid_model")

    payload: dict[str, Any]
    if config.protocol == "ollama":
        payload = {
            "model": effective_model,
            "messages": normalized,
            "stream": False,
            "options": {"temperature": 0.2},
        }
    elif config.protocol == "anthropic":
        system_text = "\n\n".join(m["content"] for m in normalized if m["role"] == "system")
        payload = {
            "model": effective_model,
            "max_tokens": 2500,
            "stream": False,
            "messages": [
                {"role": m["role"], "content": m["content"]}
                for m in normalized if m["role"] != "system"
            ],
        }
        if system_text:
            payload["system"] = system_text
    elif config.protocol == "gemini":
        contents = []
        system_parts = []
        for message in normalized:
            if message["role"] == "system":
                system_parts.append({"text": message["content"]})
            else:
                contents.append({
                    "role": "model" if message["role"] == "assistant" else "user",
                    "parts": [{"text": message["content"]}],
                })
        payload = {
            "contents": contents,
            "generationConfig": {"temperature": 0.2, "maxOutputTokens": 2500},
        }
        if system_parts:
            payload["systemInstruction"] = {"parts": system_parts}
    else:
        payload = {
            "model": effective_model,
            "messages": normalized,
            "stream": False,
            "temperature": 0.2,
            "max_tokens": 2500,
        }

    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    if config.api_key and config.auth_header == "Authorization":
        headers["Authorization"] = f"Bearer {config.api_key}"
    elif config.api_key and config.auth_header:
        headers[config.auth_header] = config.api_key
    if config.protocol == "anthropic":
        headers["anthropic-version"] = config.api_version or "2026-10-21"
    request = Request(
        f"{config.base_url}/{config.endpoint}",
        data=body,
        headers=headers,
        method="POST",
    )

    if not _REQUEST_SLOT.acquire(timeout=5.0):
        raise AIProviderError("provider_busy_try_again")
    try:
        try:
            with _transport_open(request, timeout=config.timeout_seconds) as response:
                raw = response.read(2_000_000)
        except HTTPError as exc:
            # Do not surface provider response bodies: they may contain echoed
            # prompts, request headers, or other sensitive data.
            raise AIProviderError(f"provider_http_{exc.code}") from None
        except URLError as exc:
            reason = type(getattr(exc, "reason", None)).__name__
            raise AIProviderError(f"provider_connection_failed_{reason}") from None
        except TimeoutError:
            raise AIProviderError("provider_timeout") from None
        except OSError as exc:
            raise AIProviderError(f"provider_transport_failed_{type(exc).__name__}") from None
    finally:
        _REQUEST_SLOT.release()

    try:
        response_data = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise AIProviderError("provider_invalid_json") from None

    if config.protocol == "ollama":
        content = (
            response_data.get("message", {}).get("content")
            if isinstance(response_data, dict)
            and isinstance(response_data.get("message"), dict)
            else None
        )
        prompt_tokens = response_data.get("prompt_eval_count") if isinstance(response_data, dict) else None
        completion_tokens = response_data.get("eval_count") if isinstance(response_data, dict) else None
    elif config.protocol == "anthropic":
        blocks = response_data.get("content") if isinstance(response_data, dict) else None
        content = "\n".join(
            item.get("text", "") for item in blocks
            if isinstance(item, dict) and item.get("type") == "text"
        ) if isinstance(blocks, list) else None
        usage = response_data.get("usage") if isinstance(response_data, dict) else {}
        usage = usage if isinstance(usage, dict) else {}
        prompt_tokens = usage.get("input_tokens")
        completion_tokens = usage.get("output_tokens")
    elif config.protocol == "gemini":
        candidates = response_data.get("candidates") if isinstance(response_data, dict) else None
        first = candidates[0] if isinstance(candidates, list) and candidates and isinstance(candidates[0], dict) else {}
        candidate_content = first.get("content") if isinstance(first.get("content"), dict) else {}
        parts = candidate_content.get("parts") if isinstance(candidate_content.get("parts"), list) else []
        content = "".join(item.get("text", "") for item in parts
                             if isinstance(item, dict) and isinstance(item.get("text"), str))
        usage = response_data.get("usageMetadata") if isinstance(response_data, dict) else {}
        usage = usage if isinstance(usage, dict) else {}
        prompt_tokens = usage.get("promptTokenCount")
        completion_tokens = usage.get("candidatesTokenCount")
    else:
        choices = response_data.get("choices") if isinstance(response_data, dict) else None
        first = choices[0] if isinstance(choices, list) and choices and isinstance(choices[0], dict) else {}
        message = first.get("message") if isinstance(first.get("message"), dict) else {}
        content = message.get("content")
        usage = response_data.get("usage") if isinstance(response_data, dict) else {}
        usage = usage if isinstance(usage, dict) else {}
        prompt_tokens = usage.get("prompt_tokens")
        completion_tokens = usage.get("completion_tokens")

    if not isinstance(content, str) or not content.strip():
        raise AIProviderError("provider_returned_no_text")
    if len(content) > MAX_RESPONSE_CHARS:
        content = content[:MAX_RESPONSE_CHARS]
    return {
        "content": content,
        "provider": config.provider,
        "model": effective_model,
        "remote": config.remote,
        "prompt_tokens": prompt_tokens if isinstance(prompt_tokens, int) else None,
        "completion_tokens": completion_tokens if isinstance(completion_tokens, int) else None,
        "tools_available": False,
        "tool_calls_executed": 0,
        "side_effects_performed": False,
    }
