"""Local open-weight model catalogue and loopback runtime discovery for NEXUS.

This module does not download weights or start inference servers. It discovers
already-running local runtimes only when the local status endpoint is called.
"""
from __future__ import annotations

from datetime import datetime, timezone
import ipaddress
import json
import os
import threading
from typing import Any, Mapping
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit, urlunsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener


MAX_STATUS_BYTES = 512_000
DEFAULT_OLLAMA_BASE_URL = "http://127.0.0.1:11434"
DEFAULT_LLAMACPP_BASE_URL = "http://127.0.0.1:8080"


MODEL_PROFILES: tuple[dict[str, Any], ...] = (
    {
        "id": "lfm3-text",
        "name": "Liquid AI LFM3-1.7B",
        "family": "LFM3",
        "role": "local_fast_agent",
        "parameters": "1.7B",
        "modalities": ["text"],
        "capabilities": ["instruction_following", "agentic_tasks", "tool_calling", "structured_output"],
        "ollama_model": "lfm3",
        "llamacpp_model": "LiquidAI/LFM3-1.7B-GGUF:Q4_K_M",
        "huggingface_model": "LiquidAI/LFM3-1.7B",
        "quantization": "Q4_K_M",
        "approx_quantized_weights_gb": 1.1,
        "context_window_tokens": 256000,
        "license": "LFM Open License v1.0",
        "license_family": "Apache-2.0-based-with-commercial-revenue-condition",
        "license_notice": (
            "Not standard Apache-2.0. Free commercial use under the LFM Open License "
            "is subject to a USD 10 million annual company-revenue threshold."
        ),
        "recommended_use": "Fast local coordination, routing, specialist tasks and tool-call planning.",
        "limits": "Small model; not the primary choice for difficult coding or deep multi-step reasoning.",
        "download_required": True,
    },
    {
        "id": "gpt-oss-20b",
        "name": "OpenAI gpt-oss-20b",
        "family": "gpt-oss",
        "role": "local_deep_reasoning",
        "parameters": "21B total / 3.6B active",
        "modalities": ["text"],
        "capabilities": ["reasoning", "agentic_tasks", "tool_use", "structured_output"],
        "ollama_model": "gpt-oss:20b",
        "llamacpp_model": "unspecified",
        "huggingface_model": "openai/gpt-oss-20b",
        "quantization": "runtime-selected",
        "approx_quantized_weights_gb": None,
        "minimum_system_memory_gb": 16,
        "license": "Apache License 2.0",
        "license_family": "Apache-2.0",
        "license_notice": "Also subject to the gpt-oss usage policy.",
        "recommended_use": "Higher-capacity local reasoning and long-form analysis when sufficient memory is available.",
        "limits": "Not a realistic target for the current 4 GB GTX 1650; benchmark on a larger-memory host.",
        "download_required": True,
    },
    {
        "id": "qwen3-4b",
        "name": "Qwen3-4B",
        "family": "Qwen3",
        "role": "local_balanced_agent_and_coding",
        "parameters": "4B",
        "modalities": ["text"],
        "capabilities": ["reasoning", "coding", "mathematics", "multilingual", "agentic_tasks", "tool_calling"],
        "ollama_model": "qwen3:4b",
        "llamacpp_model": "Qwen/Qwen3-4B-GGUF (select and validate a quantized build)",
        "huggingface_model": "Qwen/Qwen3-4B",
        "quantization": "Ollama quantized package / GGUF variant",
        "approx_quantized_weights_gb": 2.5,
        "context_window_tokens": 256000,
        "license": "Apache License 2.0",
        "license_family": "Apache-2.0",
        "license_notice": "Verify the exact quantized repository and model derivative before redistribution.",
        "recommended_use": "Balanced local specialist for coding, maths, multilingual tasks and general reasoning.",
        "limits": "2.5 GB package size is not the total runtime memory; use a modest context and CPU/GPU offload on 4 GB VRAM.",
        "download_required": True,
    },
    {
        "id": "deepseek-r1-1-5b",
        "name": "DeepSeek-R1-Distill-Qwen-1.5B",
        "family": "DeepSeek-R1-Distill",
        "role": "local_light_reasoning",
        "parameters": "1.5B",
        "modalities": ["text"],
        "capabilities": ["stepwise_reasoning", "mathematics", "logic", "reflection"],
        "ollama_model": "deepseek-r1:1.5b",
        "llamacpp_model": "deepseek-ai/DeepSeek-R1-Distill-Qwen-1.5B-GGUF (select and validate a quantized build)",
        "huggingface_model": "deepseek-ai/DeepSeek-R1-Distill-Qwen-1.5B",
        "quantization": "Ollama quantized package / GGUF variant",
        "approx_quantized_weights_gb": 1.1,
        "context_window_tokens": 128000,
        "license": "MIT License",
        "license_family": "MIT-with-Qwen2.5-derived-base-notice",
        "license_notice": "DeepSeek states MIT for R1 weights; this distilled Qwen model derives from Qwen2.5, whose base license is Apache 2.0. Preserve both applicable notices.",
        "recommended_use": "Light local reasoning and mathematical cross-checks on constrained hardware.",
        "limits": "Small distilled model; not a substitute for larger coding/reasoning models on difficult tasks.",
        "download_required": True,
    },
    {
        "id": "deepseek-r1-7b",
        "name": "DeepSeek-R1-Distill-Qwen-7B",
        "family": "DeepSeek-R1-Distill",
        "role": "local_reasoning",
        "parameters": "7B",
        "modalities": ["text"],
        "capabilities": ["stepwise_reasoning", "coding", "mathematics", "logic", "reflection"],
        "ollama_model": "deepseek-r1:7b",
        "llamacpp_model": "deepseek-ai/DeepSeek-R1-Distill-Qwen-7B-GGUF (select and validate a quantized build)",
        "huggingface_model": "deepseek-ai/DeepSeek-R1-Distill-Qwen-7B",
        "quantization": "Ollama quantized package / GGUF variant",
        "approx_quantized_weights_gb": 4.7,
        "context_window_tokens": 128000,
        "license": "MIT License",
        "license_family": "MIT-with-Qwen2.5-derived-base-notice",
        "license_notice": "DeepSeek states MIT for R1 weights; this distilled Qwen model derives from Qwen2.5, whose base license is Apache 2.0. Preserve both applicable notices.",
        "recommended_use": "Stronger local reasoning and code review when system RAM/CPU offload is available.",
        "limits": "The 4.7 GB package exceeds 4 GB VRAM before runtime/KV cache; do not expect full GPU residency on GTX 1650 4 GB.",
        "download_required": True,
    },
    {
        "id": "lfm3-vision",
        "name": "Liquid AI LFM3-VL-2B",
        "family": "LFM3",
        "role": "local_vision",
        "parameters": "2B",
        "modalities": ["text", "image", "video"],
        "capabilities": ["visual_question_answering", "video_understanding", "object_grounding"],
        "ollama_model": None,
        "llamacpp_model": "LiquidAI/LFM3-VL-2B-GGUF (verify supported quantization/runtime before deployment)",
        "huggingface_model": "LiquidAI/LFM3-VL-2B",
        "quantization": "runtime-specific",
        "approx_quantized_weights_gb": None,
        "license": "LFM Open License v1.0",
        "license_family": "Apache-2.0-based-with-commercial-revenue-condition",
        "license_notice": "Not standard Apache-2.0; observe the LFM Open License revenue condition.",
        "recommended_use": "Image and video analysis; separate multimodal adapter and tested runtime required.",
        "limits": "Catalogued, not yet wired to the text-only worker contract.",
        "download_required": True,
    },
    {
        "id": "lfm3-audio",
        "name": "Liquid AI LFM3-Audio-2B",
        "family": "LFM3",
        "role": "local_audio",
        "parameters": "2B",
        "modalities": ["text", "audio"],
        "capabilities": ["speech_recognition", "speech_synthesis", "translation", "audio_reasoning"],
        "ollama_model": "lfm3-audio",
        "llamacpp_model": "GGUF/runtime support requires separate validation",
        "huggingface_model": "LiquidAI/LFM3-Audio-2B",
        "quantization": "runtime-specific",
        "approx_quantized_weights_gb": None,
        "license": "LFM Open License v1.0",
        "license_family": "Apache-2.0-based-with-commercial-revenue-condition",
        "license_notice": "Not standard Apache-2.0; observe the LFM Open License revenue condition.",
        "recommended_use": "Speech and audio input/output.",
        "limits": "Separate audio pipeline; not enabled by the text-only worker API.",
        "download_required": True,
    },
    {
        "id": "lfm3-omni",
        "name": "Liquid AI LFM3-Omni-2B",
        "family": "LFM3",
        "role": "local_multimodal",
        "parameters": "2B",
        "modalities": ["text", "image", "audio", "video"],
        "capabilities": ["multimodal_reasoning", "speech", "visual_question_answering", "tool_calling"],
        "ollama_model": "lfm3-omni",
        "llamacpp_model": "GGUF/runtime support requires separate validation",
        "huggingface_model": "LiquidAI/LFM3-Omni-2B",
        "quantization": "runtime-specific",
        "approx_quantized_weights_gb": None,
        "license": "LFM Open License v1.0",
        "license_family": "Apache-2.0-based-with-commercial-revenue-condition",
        "license_notice": "Not standard Apache-2.0; observe the LFM Open License revenue condition.",
        "recommended_use": "Unified vision, audio and text workflows.",
        "limits": "Separate multimodal pipeline; not enabled by the text-only worker API.",
        "download_required": True,
    },
)
_PROFILE_BY_ID = {item["id"]: item for item in MODEL_PROFILES}
_OLLAMA_PULL_ALLOWLIST = frozenset({
    "lfm3-text", "gpt-oss-20b", "qwen3-4b",
    "deepseek-r1-1-5b", "deepseek-r1-7b",
})
_PULL_LOCK = threading.Lock()
_PULLS: dict[str, dict[str, Any]] = {}


class LocalModelRuntimeError(RuntimeError):
    """A local model runtime is absent or returned an invalid response."""


class _NoRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _loopback_base_url(raw: str, label: str) -> str:
    if not isinstance(raw, str) or not raw.strip() or len(raw) > 500:
        raise LocalModelRuntimeError(f"{label}_base_url_invalid")
    try:
        parsed = urlsplit(raw.strip())
        host = parsed.hostname
        port = parsed.port
    except ValueError:
        raise LocalModelRuntimeError(f"{label}_base_url_invalid") from None
    if (
        parsed.scheme not in {"http", "https"}
        or not host
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
        or (port is not None and not 1 <= port <= 65535)
    ):
        raise LocalModelRuntimeError(f"{label}_base_url_invalid")
    normalized = host.casefold().rstrip(".")
    is_loopback = normalized == "localhost"
    if not is_loopback:
        try:
            is_loopback = ipaddress.ip_address(normalized).is_loopback
        except ValueError:
            is_loopback = False
    if not is_loopback:
        raise LocalModelRuntimeError(f"{label}_endpoint_must_be_loopback")
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path.rstrip("/"), "", "")).rstrip("/")


def _get_json(url: str, timeout: float = 2.0) -> dict[str, Any]:
    opener = build_opener(ProxyHandler({}), _NoRedirectHandler())
    request = Request(
        url,
        headers={"Accept": "application/json", "User-Agent": "NEXUS-MASTER-local-ai/1"},
        method="GET",
    )
    try:
        with opener.open(request, timeout=timeout) as response:
            raw = response.read(MAX_STATUS_BYTES + 1)
    except HTTPError as exc:
        raise LocalModelRuntimeError(f"local_runtime_http_{exc.code}") from None
    except URLError as exc:
        reason = type(getattr(exc, "reason", None)).__name__
        raise LocalModelRuntimeError(f"local_runtime_connection_failed_{reason}") from None
    except TimeoutError:
        raise LocalModelRuntimeError("local_runtime_timeout") from None
    except OSError as exc:
        raise LocalModelRuntimeError(f"local_runtime_transport_failed_{type(exc).__name__}") from None
    if len(raw) > MAX_STATUS_BYTES:
        raise LocalModelRuntimeError("local_runtime_response_too_large")
    try:
        result = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise LocalModelRuntimeError("local_runtime_invalid_json") from None
    if not isinstance(result, dict):
        raise LocalModelRuntimeError("local_runtime_invalid_response_shape")
    return result


def model_catalog() -> dict[str, Any]:
    """Return model choices without downloading weights or contacting runtimes."""
    return {
        "models": [dict(item, modalities=list(item["modalities"]),
                        capabilities=list(item["capabilities"])) for item in MODEL_PROFILES],
        "count": len(MODEL_PROFILES),
        "default_local_agent": "lfm3-text",
        "recommended_topology": {
            "fast_coordinator_and_workers": "lfm3-text",
            "deep_reasoning_on_sufficient_hardware": "gpt-oss-20b",
            "vision": "lfm3-vision",
            "audio": "lfm3-audio",
            "multimodal": "lfm3-omni",
        },
        "policy": (
            "Catalogue only. NEXUS does not download model weights or start runtimes automatically. "
            "Model license metadata describes the model weights, not the MIT-licensed Ollama runtime."
        ),
    }


def _installed_ollama_models(models: Any) -> list[dict[str, Any]]:
    if not isinstance(models, list):
        raise LocalModelRuntimeError("ollama_tags_response_invalid")
    results = []
    for item in models:
        if not isinstance(item, dict):
            continue
        name = item.get("name")
        if isinstance(name, str) and name.strip():
            results.append({
                "name": name,
                "size_bytes": item.get("size") if isinstance(item.get("size"), int) else None,
                "modified_at": item.get("modified_at") if isinstance(item.get("modified_at"), str) else None,
            })
    return results


def local_runtime_status(env: Mapping[str, str] | None = None) -> dict[str, Any]:
    """Probe Ollama and llama.cpp only on loopback; does not load models or start processes."""
    source = os.environ if env is None else env
    results: dict[str, Any] = {}

    ollama_raw = str(source.get("NEXUS_OLLAMA_BASE_URL", DEFAULT_OLLAMA_BASE_URL))
    try:
        base = _loopback_base_url(ollama_raw, "ollama")
        version = _get_json(f"{base}/api/version")
        tags = _get_json(f"{base}/api/tags")
        installed = _installed_ollama_models(tags.get("models"))
        results["ollama"] = {
            "status": "reachable",
            "operational_verified": False,
            "version": version.get("version"),
            "installed_models": installed,
            "model_count": len(installed),
            "models_loaded": "not_checked",
            "model_downloads_started": False,
            "server_started_by_nexus": False,
        }
    except LocalModelRuntimeError as exc:
        results["ollama"] = {
            "status": "unavailable_or_invalid",
            "operational_verified": False,
            "reason": str(exc),
            "installed_models": [],
            "model_count": 0,
            "model_downloads_started": False,
            "server_started_by_nexus": False,
        }

    llama_raw = str(source.get("NEXUS_LLAMACPP_BASE_URL", DEFAULT_LLAMACPP_BASE_URL))
    try:
        base = _loopback_base_url(llama_raw, "llamacpp")
        model_data = _get_json(f"{base}/v1/models")
        rows = model_data.get("data")
        if not isinstance(rows, list):
            raise LocalModelRuntimeError("llamacpp_models_response_invalid")
        installed = [
            {"id": item.get("id")}
            for item in rows
            if isinstance(item, dict) and isinstance(item.get("id"), str)
        ]
        results["llamacpp"] = {
            "status": "reachable",
            "operational_verified": False,
            "installed_models": installed,
            "model_count": len(installed),
            "model_downloads_started": False,
            "server_started_by_nexus": False,
        }
    except LocalModelRuntimeError as exc:
        results["llamacpp"] = {
            "status": "unavailable_or_invalid",
            "operational_verified": False,
            "reason": str(exc),
            "installed_models": [],
            "model_count": 0,
            "model_downloads_started": False,
            "server_started_by_nexus": False,
        }

    return {
        "runtimes": results,
        "any_runtime_reachable": any(row["status"] == "reachable" for row in results.values()),
        "local_model_operational_verified": False,
        "policy": "Loopback discovery only. A reachable API is not proof that a model can infer correctly.",
    }




def _ollama_pull_open(request: Request, timeout: float):
    opener = build_opener(ProxyHandler({}), _NoRedirectHandler())
    return opener.open(request, timeout=timeout)


def _pull_snapshot(profile_id: str, state: Mapping[str, Any] | None) -> dict[str, Any]:
    if state is None:
        return {
            "profile_id": profile_id,
            "status": "not_started",
            "operational_verified": False,
            "model_downloaded": False,
        }
    total = state.get("total")
    completed = state.get("completed")
    progress = (
        round((completed / total) * 100, 2)
        if isinstance(total, int) and total > 0 and isinstance(completed, int)
        else None
    )
    return {
        "profile_id": profile_id,
        "model": state.get("model"),
        "status": state.get("status"),
        "operational_verified": False,
        "model_downloaded": state.get("status") == "completed",
        "total_bytes": total,
        "completed_bytes": completed,
        "progress_percent": progress,
        "last_message": state.get("last_message"),
        "started_at": state.get("started_at"),
        "finished_at": state.get("finished_at"),
        "failure_type": state.get("failure_type"),
    }


def _ollama_pull_worker(profile_id: str, model_name: str, base_url: str) -> None:
    request = Request(
        f"{base_url}/api/pull",
        data=json.dumps({"name": model_name, "stream": True}).encode("utf-8"),
        headers={"Content-Type": "application/json", "Accept": "application/x-ndjson"},
        method="POST",
    )
    try:
        with _ollama_pull_open(request, timeout=30.0) as response:
            while True:
                raw = response.readline(256_001)
                if not raw:
                    break
                if len(raw) > 256_000:
                    raise LocalModelRuntimeError("ollama_pull_progress_line_too_large")
                try:
                    item = json.loads(raw.decode("utf-8"))
                except (UnicodeDecodeError, json.JSONDecodeError):
                    raise LocalModelRuntimeError("ollama_pull_invalid_progress_json") from None
                if not isinstance(item, dict):
                    raise LocalModelRuntimeError("ollama_pull_invalid_progress_shape")
                with _PULL_LOCK:
                    state = _PULLS.get(profile_id)
                    if state is None:
                        return
                    message = item.get("status")
                    state["last_message"] = (
                        str(message)[:160] if isinstance(message, str) else None
                    )
                    total = item.get("total")
                    completed = item.get("completed")
                    if isinstance(total, int) and total >= 0:
                        state["total"] = total
                    if isinstance(completed, int) and completed >= 0:
                        state["completed"] = completed
                    if item.get("error"):
                        state["status"] = "failed"
                        state["failure_type"] = "ollama_pull_error"
                        state["finished_at"] = datetime.now(timezone.utc).isoformat()
                        return
        with _PULL_LOCK:
            state = _PULLS.get(profile_id)
            if state is not None:
                state["status"] = "completed"
                state["finished_at"] = datetime.now(timezone.utc).isoformat()
                state["last_message"] = "success"
    except Exception as exc:
        with _PULL_LOCK:
            state = _PULLS.get(profile_id)
            if state is not None:
                state["status"] = "failed"
                state["failure_type"] = type(exc).__name__
                state["last_message"] = "pull_failed"
                state["finished_at"] = datetime.now(timezone.utc).isoformat()


def start_ollama_model_pull(
    profile_id: str,
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Explicitly request one allowlisted model pull from an already-running loopback Ollama."""
    normalized_id = str(profile_id).strip().casefold()
    profile = _PROFILE_BY_ID.get(normalized_id)
    if profile is None or normalized_id not in _OLLAMA_PULL_ALLOWLIST:
        raise LocalModelRuntimeError("model_profile_not_allowlisted_for_ollama_pull")
    profile_id = normalized_id
    model_name = profile.get("ollama_model")
    if not isinstance(model_name, str) or not model_name.strip():
        raise LocalModelRuntimeError("ollama_model_not_available_for_profile")

    source = os.environ if env is None else env
    raw_url = str(source.get("NEXUS_OLLAMA_BASE_URL", DEFAULT_OLLAMA_BASE_URL))
    base_url = _loopback_base_url(raw_url, "ollama")
    # Require an already-running service. This endpoint never starts Ollama itself.
    _get_json(f"{base_url}/api/version", timeout=2.0)

    with _PULL_LOCK:
        for current_id, current in _PULLS.items():
            thread = current.get("thread")
            if thread is not None and thread.is_alive():
                if current_id == profile_id:
                    return _pull_snapshot(profile_id, current)
                raise LocalModelRuntimeError("another_ollama_model_pull_is_running")
        state: dict[str, Any] = {
            "model": model_name,
            "status": "running",
            "total": None,
            "completed": 0,
            "last_message": "starting",
            "started_at": datetime.now(timezone.utc).isoformat(),
            "finished_at": None,
            "failure_type": None,
            "thread": None,
        }
        _PULLS[profile_id] = state
        thread = threading.Thread(
            target=_ollama_pull_worker,
            args=(profile_id, model_name, base_url),
            name=f"nexus-ollama-pull-{profile_id}",
            daemon=True,
        )
        state["thread"] = thread
        try:
            thread.start()
        except RuntimeError as exc:
            state["status"] = "failed"
            state["failure_type"] = type(exc).__name__
            state["finished_at"] = datetime.now(timezone.utc).isoformat()
            raise LocalModelRuntimeError("ollama_pull_thread_start_failed") from exc
        return _pull_snapshot(profile_id, state)


def ollama_model_pull_status(profile_id: str) -> dict[str, Any]:
    normalized_id = str(profile_id).strip().casefold()
    if normalized_id not in _OLLAMA_PULL_ALLOWLIST:
        raise LocalModelRuntimeError("model_profile_not_allowlisted_for_ollama_pull")
    with _PULL_LOCK:
        state = _PULLS.get(normalized_id)
        return _pull_snapshot(normalized_id, state)


def model_profile(profile_id: str) -> dict[str, Any]:
    item = _PROFILE_BY_ID.get(str(profile_id).strip().casefold())
    if item is None:
        raise LocalModelRuntimeError("unknown_model_profile")
    return dict(item)
