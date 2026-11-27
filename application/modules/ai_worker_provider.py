"""Opt-in, text-only AI provider adapter for NEXUS workers.

Supported providers:
- Ollama's native local /api/chat endpoint.
- OpenAI-compatible /v1/chat/completions endpoints, local by default.
Remote providers require HTTPS, an explicit remote-enable flag, a hostname
allowlist, and an API key. No tools/function calls are sent to the model.
"""
from __future__ import annotations

from dataclasses import dataclass
import ipaddress
import json
import os
import threading
from typing import Any, Mapping
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit, urlunsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener


MAX_MESSAGES = 12
MAX_TOTAL_MESSAGE_CHARS = 40_000
MAX_RESPONSE_CHARS = 30_000
_REQUEST_SLOT = threading.BoundedSemaphore(1)


class AIProviderError(RuntimeError):
    """Safe provider configuration, transport or response error."""


@dataclass(frozen=True)
class ProviderConfig:
    provider: str
    model: str
    base_url: str
    api_key: str | None
    timeout_seconds: float
    endpoint: str
    remote: bool


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
    provider = str(env.get("NEXUS_AI_PROVIDER", "disabled")).strip().casefold()
    if provider in {"", "disabled", "none", "off"}:
        return None
    if provider not in {"ollama", "openai_compatible"}:
        raise AIProviderError("unsupported_provider")

    model = str(env.get("NEXUS_AI_MODEL", "")).strip()
    if not model or len(model) > 160 or any(ord(c) < 32 for c in model):
        raise AIProviderError("model_not_configured")

    default_url = "http://127.0.0.1:11434/api" if provider == "ollama" else ""
    raw_url = str(env.get("NEXUS_AI_BASE_URL", default_url)).strip()
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

    remote = not _is_loopback(host)
    api_key = str(env.get("NEXUS_AI_API_KEY", "")).strip() or None
    path = parts.path.rstrip("/")

    if remote:
        if env.get("NEXUS_AI_ALLOW_REMOTE", "").strip() != "1":
            raise AIProviderError("remote_provider_not_explicitly_enabled")
        if parts.scheme != "https" or port not in (None, 443):
            raise AIProviderError("remote_provider_requires_https_443")
        allowed_hosts = {
            item.strip().casefold().rstrip(".")
            for item in str(env.get("NEXUS_AI_REMOTE_HOST_ALLOWLIST", "")).split(",")
            if item.strip()
        }
        if host.casefold().rstrip(".") not in allowed_hosts:
            raise AIProviderError("remote_host_not_allowlisted")
        if not api_key:
            raise AIProviderError("remote_api_key_not_configured")

    if provider == "ollama":
        if remote:
            raise AIProviderError("ollama_native_provider_must_be_local")
        if path not in {"", "/", "/api"}:
            raise AIProviderError("ollama_base_url_must_target_api_root")
        base_path = "/api"
        endpoint = "chat"
    else:
        if path not in {"/v1", "/"}:
            raise AIProviderError("openai_compatible_base_url_must_target_v1")
        base_path = "/v1"
        endpoint = "chat/completions"

    base = urlunsplit((
        parts.scheme,
        parts.netloc,
        base_path,
        "",
        "",
    )).rstrip("/")
    return ProviderConfig(
        provider=provider,
        model=model,
        base_url=base,
        api_key=api_key,
        timeout_seconds=_bounded_timeout(env),
        endpoint=endpoint,
        remote=remote,
    )


def provider_status(env: Mapping[str, str] | None = None) -> dict[str, Any]:
    """Return safe config status; never echo keys or raw credentials."""
    source = os.environ if env is None else env
    try:
        config = _safe_config(source)
    except AIProviderError as exc:
        return {
            "provider_status": "misconfigured",
            "provider": str(source.get("NEXUS_AI_PROVIDER", "disabled")).strip().casefold(),
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
            "model": None,
            "endpoint": None,
            "remote": False,
            "api_key_configured": False,
            "configured_model_providers": 0,
            "active_ai_agents": 0,
            "model_invocation_enabled": False,
            "configuration_error": None,
        }

    return {
        "provider_status": "configured_not_live_verified",
        "provider": config.provider,
        "model": config.model,
        "endpoint": f"{urlsplit(config.base_url).scheme}://{urlsplit(config.base_url).netloc}{urlsplit(config.base_url).path}",
        "remote": config.remote,
        "api_key_configured": bool(config.api_key),
        "configured_model_providers": 1,
        "active_ai_agents": 0,
        "model_invocation_enabled": True,
        "configuration_error": None,
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
    if config.provider == "ollama":
        payload = {
            "model": effective_model,
            "messages": normalized,
            "stream": False,
            "options": {"temperature": 0.2},
        }
    else:
        payload = {
            "model": effective_model,
            "messages": normalized,
            "stream": False,
            "temperature": 0.2,
            "max_tokens": 2500,
        }

    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = Request(
        f"{config.base_url}/{config.endpoint}",
        data=body,
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            **({"Authorization": f"Bearer {config.api_key}"} if config.api_key else {}),
        },
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

    if config.provider == "ollama":
        content = (
            response_data.get("message", {}).get("content")
            if isinstance(response_data, dict)
            and isinstance(response_data.get("message"), dict)
            else None
        )
        prompt_tokens = response_data.get("prompt_eval_count") if isinstance(response_data, dict) else None
        completion_tokens = response_data.get("eval_count") if isinstance(response_data, dict) else None
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
