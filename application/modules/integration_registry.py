"""NEXUS read-only connector registry and guarded REST adapter runtime.

Provider metadata is not treated as evidence of connectivity. A connector is
operationally verified only after a configured HTTPS/loopback JSON endpoint
returns a bounded, valid response through the adapter.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import ipaddress
import json
import os
import re
import threading
from typing import Any, Mapping
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit, urlunsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

from fastapi import APIRouter, HTTPException, Request as FastAPIRequest


router = APIRouter(prefix="/api/integrations", tags=["NEXUS Integrations"])

MAX_RESPONSE_BYTES = 1_000_000
CONNECTOR_TIMEOUT_SECONDS = 12.0
_VERIFICATION_LOCK = threading.Lock()
_LIVE_VERIFICATION: dict[str, dict[str, Any]] = {}


PROVIDERS: tuple[dict[str, Any], ...] = (
    {"id": "acurast", "name": "Acurast", "category": "depin",
     "env": ("NEXUS_ACURAST_API_URL", "NEXUS_ACURAST_API_TOKEN"),
     "capabilities": ["account_read", "rewards_read", "device_status_read"],
     "resources": ("account", "rewards", "device_status")},
    {"id": "grass", "name": "Grass", "category": "depin",
     "env": ("NEXUS_GRASS_API_URL", "NEXUS_GRASS_API_TOKEN"),
     "capabilities": ["account_read", "points_read", "rewards_read"],
     "resources": ("account", "points", "rewards")},
    {"id": "aioz", "name": "AIOZ", "category": "depin",
     "env": ("NEXUS_AIOZ_API_URL",),
     "capabilities": ["public_chain_read", "node_status_read", "rewards_read"],
     "resources": ("public_chain", "node_status", "rewards")},
    {"id": "theta", "name": "Theta", "category": "depin",
     "env": ("NEXUS_THETA_API_URL",),
     "capabilities": ["public_chain_read", "edge_status_read"],
     "resources": ("public_chain", "edge_status")},
    {"id": "nodle", "name": "Nodle", "category": "depin",
     "env": ("NEXUS_NODLE_API_URL",),
     "capabilities": ["public_chain_read", "rewards_read"],
     "resources": ("public_chain", "rewards")},
    {"id": "helium_iot", "name": "Helium IoT", "category": "depin",
     "env": ("NEXUS_HELIUM_API_URL",),
     "capabilities": ["coverage_read", "hotspot_read", "rewards_read"],
     "resources": ("coverage", "hotspot", "rewards")},
    {"id": "geodnet", "name": "GEODNET", "category": "depin",
     "env": ("NEXUS_GEODNET_API_URL",),
     "capabilities": ["station_read", "coverage_read", "rewards_read"],
     "resources": ("station", "coverage", "rewards")},
    {"id": "anyone", "name": "Anyone", "category": "depin",
     "env": ("NEXUS_ANYONE_API_URL",),
     "capabilities": ["relay_status_read", "rewards_read"],
     "resources": ("relay_status", "rewards")},
    {"id": "weatherxm", "name": "WeatherXM", "category": "depin",
     "env": ("NEXUS_WEATHERXM_API_URL",),
     "capabilities": ["station_read", "rewards_read"],
     "resources": ("station", "rewards")},
    {"id": "wingbits", "name": "Wingbits", "category": "depin",
     "env": ("NEXUS_WINGBITS_API_URL",),
     "capabilities": ["receiver_read", "coverage_read", "rewards_read"],
     "resources": ("receiver", "coverage", "rewards")},
    {"id": "akash", "name": "Akash", "category": "compute",
     "env": ("NEXUS_AKASH_API_URL",),
     "capabilities": ["provider_read", "deployment_read", "billing_read"],
     "resources": ("provider", "deployment", "billing")},
    {"id": "nosana", "name": "Nosana", "category": "compute",
     "env": ("NEXUS_NOSANA_API_URL",),
     "capabilities": ["node_read", "job_read", "rewards_read"],
     "resources": ("node", "job", "rewards")},
)
_PROVIDER_BY_ID = {item["id"]: item for item in PROVIDERS}


class ConnectorError(RuntimeError):
    """Safe connector configuration, transport or contract error."""


class _NoRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _is_loopback(host: str | None) -> bool:
    if not host:
        return False
    value = host.casefold().rstrip(".")
    if value == "localhost":
        return True
    try:
        return ipaddress.ip_address(value).is_loopback
    except ValueError:
        return False


def _provider(provider_id: str) -> dict[str, Any]:
    item = _PROVIDER_BY_ID.get(str(provider_id).strip().casefold())
    if item is None:
        raise ConnectorError("unknown_connector")
    return item


def _host_allowlist(item: dict[str, Any], source: Mapping[str, str]) -> set[str]:
    suffix = item["id"].upper()
    values = [
        source.get("NEXUS_CONNECTOR_ALLOWED_HOSTS", ""),
        source.get(f"NEXUS_CONNECTOR_ALLOWED_HOSTS_{suffix}", ""),
    ]
    return {
        host.strip().casefold().rstrip(".")
        for value in values
        for host in str(value).split(",")
        if host.strip()
    }


def _config(item: dict[str, Any], source: Mapping[str, str]) -> dict[str, Any]:
    missing = [key for key in item["env"] if not str(source.get(key, "")).strip()]
    if missing:
        raise ConnectorError("connector_not_configured")

    raw_url = str(source[item["env"][0]]).strip()
    if len(raw_url) > 500:
        raise ConnectorError("connector_url_too_long")
    try:
        parts = urlsplit(raw_url)
        host = parts.hostname
        port = parts.port
    except ValueError:
        raise ConnectorError("invalid_connector_url") from None
    if (
        parts.scheme not in {"http", "https"}
        or not host
        or parts.username is not None
        or parts.password is not None
        or parts.query
        or parts.fragment
    ):
        raise ConnectorError("invalid_connector_url")

    normalized_host = host.casefold().rstrip(".")
    local = _is_loopback(host)
    if not local:
        if parts.scheme != "https" or port not in (None, 443):
            raise ConnectorError("remote_connector_requires_https_443")
        if normalized_host not in _host_allowlist(item, source):
            raise ConnectorError("connector_host_not_allowlisted")

    suffix = item["id"].upper()
    token_env = next((key for key in item["env"] if key.endswith("_API_TOKEN")), None)
    token = str(source.get(token_env, "")).strip() if token_env else ""
    header_name = str(source.get(f"NEXUS_{suffix}_API_TOKEN_HEADER", "Authorization")).strip()
    if header_name.casefold() not in {"authorization", "x-api-key", "api-key"}:
        raise ConnectorError("unsupported_connector_auth_header")
    auth_scheme = str(source.get(f"NEXUS_{suffix}_API_AUTH_SCHEME", "Bearer")).strip()
    if token and (not auth_scheme or len(auth_scheme) > 24 or any(ord(c) < 33 for c in auth_scheme)):
        raise ConnectorError("invalid_connector_auth_scheme")

    base_path = parts.path.rstrip("/")
    base_url = urlunsplit((parts.scheme, parts.netloc, base_path, "", "")).rstrip("/")
    fingerprint = sha256(
        (raw_url + "|" + token + "|" + ",".join(sorted(_host_allowlist(item, source)))).encode("utf-8")
    ).hexdigest()
    return {
        "base_url": base_url,
        "host": normalized_host,
        "local": local,
        "token": token or None,
        "auth_header": header_name,
        "auth_scheme": auth_scheme,
        "fingerprint": fingerprint,
    }


def _normalize_path(path: str) -> str:
    value = str(path).strip()
    if not value or len(value) > 300 or "://" in value:
        raise ConnectorError("invalid_connector_resource_path")
    parts = urlsplit(value)
    if parts.scheme or parts.netloc or parts.query or parts.fragment:
        raise ConnectorError("invalid_connector_resource_path")
    clean = parts.path.lstrip("/")
    segments = clean.split("/")
    if not clean or any(segment in {"", ".", ".."} for segment in segments):
        raise ConnectorError("invalid_connector_resource_path")
    if any(ord(ch) < 32 for ch in clean):
        raise ConnectorError("invalid_connector_resource_path")
    return clean


def _resource_path(item: dict[str, Any], resource: str, source: Mapping[str, str]) -> str:
    suffix = item["id"].upper()
    resource_key = resource.upper()
    if resource != "health" and resource not in item["resources"]:
        raise ConnectorError("unsupported_connector_resource")
    env_name = f"NEXUS_{suffix}_{resource_key}_PATH"
    raw = str(source.get(env_name, "")).strip()
    if not raw:
        raise ConnectorError("connector_resource_path_not_configured")
    return _normalize_path(raw)


def _transport_open(request: Request, timeout: float):
    opener = build_opener(ProxyHandler({}), _NoRedirectHandler())
    return opener.open(request, timeout=timeout)


def _request_json(
    item: dict[str, Any],
    resource: str,
    source: Mapping[str, str],
) -> tuple[Any, int, str, str, str]:
    config = _config(item, source)
    relative_path = _resource_path(item, resource, source)
    url = f"{config['base_url']}/{relative_path}"
    headers = {"Accept": "application/json", "User-Agent": "NEXUS-MASTER-readonly/1"}
    if config["token"]:
        headers[config["auth_header"]] = f"{config['auth_scheme']} {config['token']}"
    request = Request(url, headers=headers, method="GET")
    try:
        with _transport_open(request, CONNECTOR_TIMEOUT_SECONDS) as response:
            raw = response.read(MAX_RESPONSE_BYTES + 1)
            status_code = int(getattr(response, "status", response.getcode()))
            content_type = str(response.headers.get("Content-Type", ""))
    except HTTPError as exc:
        raise ConnectorError(f"connector_http_{exc.code}") from None
    except URLError as exc:
        reason = type(getattr(exc, "reason", None)).__name__
        raise ConnectorError(f"connector_transport_failed_{reason}") from None
    except TimeoutError:
        raise ConnectorError("connector_timeout") from None
    except OSError as exc:
        raise ConnectorError(f"connector_transport_failed_{type(exc).__name__}") from None

    if status_code < 200 or status_code >= 300:
        raise ConnectorError(f"connector_http_{status_code}")
    if len(raw) > MAX_RESPONSE_BYTES:
        raise ConnectorError("connector_response_too_large")
    if "json" not in content_type.casefold():
        raise ConnectorError("connector_expected_json_content_type")
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise ConnectorError("connector_invalid_json") from None

    observed_at = datetime.now(timezone.utc).isoformat()
    with _VERIFICATION_LOCK:
        if source is os.environ:
            _LIVE_VERIFICATION[item["id"]] = {
                "ok": True,
                "fingerprint": config["fingerprint"],
                "observed_at": observed_at,
                "http_status": status_code,
                "resource": resource,
            }
    return payload, status_code, content_type, observed_at, relative_path


def connector_status(env: dict[str, str] | None = None) -> list[dict[str, Any]]:
    source = os.environ if env is None else env
    rows = []
    for item in PROVIDERS:
        configured = [key for key in item["env"] if str(source.get(key, "")).strip()]
        ready = len(configured) == len(item["env"])
        live: dict[str, Any] | None = None
        if env is None and ready:
            try:
                current_config = _config(item, source)
                with _VERIFICATION_LOCK:
                    candidate = _LIVE_VERIFICATION.get(item["id"])
                if candidate and candidate.get("fingerprint") == current_config["fingerprint"]:
                    try:
                        verified_at = datetime.fromisoformat(candidate.get("observed_at", ""))
                        age = (datetime.now(timezone.utc) - verified_at).total_seconds()
                        if 0 <= age <= 900:
                            live = candidate
                    except (TypeError, ValueError):
                        live = None
            except ConnectorError:
                live = None
        operational_verified = bool(live and live.get("ok"))
        rows.append({
            "id": item["id"],
            "name": item["name"],
            "category": item["category"],
            "status": (
                "live_verified" if operational_verified
                else "configured_pending_adapter_validation" if ready
                else "not_configured"
            ),
            "configured_fields": len(configured),
            "required_fields": len(item["env"]),
            "capabilities": list(item["capabilities"]),
            "resources": list(item["resources"]),
            "adapter_registered": True,
            "mode": "read_only",
            "live_connection_verified": operational_verified,
            "operational_verified": operational_verified,
            "last_verified_at": live.get("observed_at") if live else None,
            "last_http_status": live.get("http_status") if live else None,
            "verified_resource": live.get("resource") if live else None,
            "writes_enabled": False,
            "missing_configuration": [key for key in item["env"] if key not in configured],
        })
    return rows


def probe_connector(provider_id: str, env: Mapping[str, str] | None = None) -> dict[str, Any]:
    source = os.environ if env is None else env
    item = _provider(provider_id)
    if env is None:
        with _VERIFICATION_LOCK:
            _LIVE_VERIFICATION.pop(item["id"], None)
    payload, status_code, content_type, observed_at, path = _request_json(item, "health", source)
    if isinstance(payload, dict):
        data_summary = {"type": "object", "keys": sorted(str(k) for k in payload.keys())[:40]}
    elif isinstance(payload, list):
        data_summary = {"type": "array", "items": len(payload)}
    else:
        data_summary = {"type": type(payload).__name__}
    return {
        "provider_id": item["id"],
        "name": item["name"],
        "status": "reachable",
        "operational_verified": True,
        "read_only": True,
        "http_status": status_code,
        "content_type": content_type,
        "resource_path": path,
        "observed_at": observed_at,
        "response_summary": data_summary,
    }


def read_connector_resource(
    provider_id: str,
    resource: str,
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    source = os.environ if env is None else env
    item = _provider(provider_id)
    payload, status_code, content_type, observed_at, path = _request_json(item, resource, source)
    return {
        "provider_id": item["id"],
        "name": item["name"],
        "resource": resource,
        "status": "live_verified",
        "operational_verified": True,
        "read_only": True,
        "http_status": status_code,
        "content_type": content_type,
        "resource_path": path,
        "observed_at": observed_at,
        "data": payload,
    }


def run_connector_self_test() -> dict[str, Any]:
    """Probe every registered connector that has a real local configuration."""
    results: list[dict[str, Any]] = []
    for item in PROVIDERS:
        try:
            probe = probe_connector(item["id"])
            results.append({
                "provider_id": item["id"],
                "status": "passed",
                "operational_verified": True,
                "http_status": probe["http_status"],
                "resource_path": probe["resource_path"],
            })
        except ConnectorError as exc:
            reason = str(exc)
            results.append({
                "provider_id": item["id"],
                "status": "not_configured" if reason == "connector_not_configured" else "failed",
                "operational_verified": False,
                "reason": reason,
            })

    passed = sum(row["status"] == "passed" for row in results)
    return {
        "status": "live_verified" if passed == len(PROVIDERS) else "partial",
        "operational_verified": passed == len(PROVIDERS),
        "connectors_tested": len(results),
        "connectors_passed": passed,
        "connectors_failed_or_unconfigured": len(results) - passed,
        "read_only": True,
        "writes_enabled": False,
        "results": results,
    }


def _require_loopback_client(request: FastAPIRequest) -> None:
    client = request.client
    host = client.host if client else ""
    try:
        allowed = ipaddress.ip_address(host).is_loopback
    except ValueError:
        allowed = host.casefold().rstrip(".") == "localhost"
    if not allowed:
        raise HTTPException(status_code=403, detail="integration_api_loopback_only")


@router.get("/catalog")
def integrations_catalog():
    rows = connector_status()
    return {
        "providers": rows,
        "count": len(rows),
        "live_verified": sum(row["operational_verified"] for row in rows),
        "adapter_registered": sum(row["adapter_registered"] for row in rows),
        "policy": (
            "Connectors are read-only. Configuration is not live verification; "
            "each provider must pass an allowlisted JSON health/resource request."
        ),
    }


@router.get("/status")
def integrations_status():
    rows = connector_status()
    return {
        "total": len(rows),
        "not_configured": sum(x["status"] == "not_configured" for x in rows),
        "configured_pending_adapter_validation": sum(
            x["status"] == "configured_pending_adapter_validation" for x in rows
        ),
        "live_verified": sum(x["operational_verified"] for x in rows),
        "operational_verified": sum(x["operational_verified"] for x in rows),
        "providers": rows,
    }


@router.post("/self-test")
def integrations_self_test(request: FastAPIRequest):
    """Explicitly test each configured connector's health endpoint."""
    _require_loopback_client(request)
    return run_connector_self_test()


@router.post("/{provider_id}/probe")
def integrations_probe(provider_id: str, request: FastAPIRequest):
    _require_loopback_client(request)
    try:
        return probe_connector(provider_id)
    except ConnectorError as exc:
        status_code = 404 if str(exc) == "unknown_connector" else 503
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc


@router.get("/{provider_id}/read/{resource}")
def integrations_read(provider_id: str, resource: str, request: FastAPIRequest):
    _require_loopback_client(request)
    try:
        return read_connector_resource(provider_id, resource)
    except ConnectorError as exc:
        status_code = 404 if str(exc) == "unknown_connector" else 503
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc
