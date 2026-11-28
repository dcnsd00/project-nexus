"""NEXUS read-only connector registry and guarded REST adapter runtime.

Provider metadata is not treated as evidence of connectivity. A connector is
operationally verified only after a configured HTTPS/loopback JSON endpoint
returns a bounded, valid response through the adapter.
"""
from __future__ import annotations

from datetime import datetime, timezone
import base64
import hmac
import secrets
import ipaddress
import json
import os
import re
import threading
from typing import Any, Mapping
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit, urlunsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

from fastapi import APIRouter, HTTPException, Request as FastAPIRequest


router = APIRouter(prefix="/api/integrations", tags=["NEXUS Integrations"])

MAX_RESPONSE_BYTES = 1_000_000
CONNECTOR_TIMEOUT_SECONDS = 12.0
_VERIFICATION_LOCK = threading.Lock()
_LIVE_VERIFICATION: dict[str, dict[str, Any]] = {}
_FINGERPRINT_KEY = secrets.token_bytes(32)


PROVIDERS: tuple[dict[str, Any], ...] = (
    {"id": "acurast", "name": "Acurast", "category": "depin",
     "env": ("NEXUS_ACURAST_API_URL", "NEXUS_ACURAST_API_TOKEN"),
     "contract_state": "official_websocket_rpc_only_http_adapter_pending",
     "contract_source": "https://docs.acurast.com/networks/",
     "capabilities": ["account_read", "rewards_read", "device_status_read"],
     "resources": ("account", "rewards", "device_status")},
    {"id": "grass", "name": "Grass", "category": "depin",
     "env": ("NEXUS_GRASS_API_URL", "NEXUS_GRASS_API_TOKEN"),
     "contract_state": "provider_account_api_contract_pending",
     "capabilities": ["account_read", "points_read", "rewards_read"],
     "resources": ("account", "points", "rewards")},
    {"id": "aioz", "name": "AIOZ", "category": "depin",
     "env": ("NEXUS_AIOZ_API_URL",),
     "default_base_url": "https://rpc-dataseed.aioz.network",
     "health_path": "status",
     "resource_paths": {"public_chain": "status", "node_status": "status"},
     "contract_source": "https://docs.aioz.network/aioz-blockchain/network-information",
     "contract_state": "official_rpc_documented",
     "response_contract": "tendermint_status",
     "resource_response_contracts": {"public_chain": "tendermint_status", "node_status": "tendermint_status"},
     "protocol": "rest_get",
     "capabilities": ["public_chain_read", "node_status_read"],
     "resources": ("public_chain", "node_status")},
    {"id": "theta", "name": "Theta", "category": "depin",
     "env": ("NEXUS_THETA_API_URL",),
     "default_base_url": "https://eth-rpc-api.thetatoken.org",
     "health_path": "rpc",
     "health_rpc_method": "eth_chainId",
     "resource_paths": {"public_chain": "rpc"},
     "resource_rpc_methods": {"public_chain": "eth_blockNumber"},
     "contract_source": "https://docs.thetatoken.org/docs/theta-blockchain-tnt20-token-integration-guide",
     "contract_state": "official_json_rpc_documented",
     "response_contract": "json_rpc",
     "resource_response_contracts": {"public_chain": "json_rpc"},
     "protocol": "json_rpc_post",
     "capabilities": ["public_chain_read"],
     "resources": ("public_chain",)},
    {"id": "nodle", "name": "Nodle", "category": "depin",
     "env": ("NEXUS_NODLE_API_URL",),
     "default_base_url": "https://api.nodle.com",
     "health_path": "v1/total-issuance",
     "resource_paths": {
         "total_issuance": "v1/total-issuance",
         "circulating_supply": "v1/circulating-supply",
     },
     "contract_source": "https://docs.nodle.com/nodle-apis",
     "contract_state": "official_public_chain_supply_api_documented",
     "response_contract": "numeric_value",
     "resource_response_contracts": {
         "total_issuance": "numeric_value",
         "circulating_supply": "numeric_value",
     },
     "protocol": "rest_get",
     "capabilities": ["total_issuance_read", "circulating_supply_read"],
     "resources": ("total_issuance", "circulating_supply")},
    {"id": "helium_iot", "name": "Helium IoT", "category": "depin",
     "env": ("NEXUS_HELIUM_API_URL",),
     "default_base_url": "https://entities.nft.helium.io",
     "health_path": "v2/hotspots",
     "health_query": {"subnetwork": "iot"},
     "resource_paths": {"hotspots": "v2/hotspots"},
     "contract_source": "https://docs.helium.com/network-data/entity-api/",
     "contract_state": "official_entity_api_documented",
     "response_contract": "helium_hotspot_list",
     "resource_response_contracts": {"hotspots": "helium_hotspot_list"},
     "protocol": "rest_get",
     "capabilities": ["hotspot_read"],
     "resources": ("hotspots",)},
    {"id": "geodnet", "name": "GEODNET", "category": "depin",
     "env": ("NEXUS_GEODNET_API_URL", "NEXUS_GEODNET_USERNAME", "NEXUS_GEODNET_PASSWORD"),
     "default_base_url": "https://rawdata.geodnet.com",
     "auth_mode": "basic",
     "health_path": "api/rawdata/v1/stations",
     "resource_paths": {"station": "api/rawdata/v1/stations"},
     "contract_source": "https://github.com/geodnet/GEODNET_API/blob/main/GEODNET_STATION_API.md",
     "contract_state": "official_basic_auth_station_api_documented",
     "response_contract": "geodnet_stations",
     "resource_response_contracts": {"station": "geodnet_stations"},
     "protocol": "rest_get",
     "capabilities": ["station_read", "coverage_read"],
     "resources": ("station",)},
    {"id": "anyone", "name": "Anyone", "category": "depin",
     "env": ("NEXUS_ANYONE_API_URL",),
     "default_base_url": "https://api.ec.anyone.tech",
     "health_path": "total-relays-latest",
     "resource_paths": {"relay_status": "total-relays-latest"},
     "contract_source": "https://docs.anyone.io/sdk/api/rest",
     "contract_state": "official_public_rest_documented",
     "response_contract": "anyone_relay_summary",
     "resource_response_contracts": {"relay_status": "anyone_relay_summary"},
     "protocol": "rest_get",
     "capabilities": ["relay_network_status_read"],
     "resources": ("relay_status",)},
    {"id": "weatherxm", "name": "WeatherXM", "category": "depin",
     "env": ("NEXUS_WEATHERXM_API_URL",),
     "default_base_url": "https://api.weatherxm.com",
     "health_path": "api/v1/network/stats",
     "resource_paths": {
         "station": "api/v1/me/devices",
         "rewards": "api/v1/me/devices/rewards",
     },
     "optional_token_env": "NEXUS_WEATHERXM_API_TOKEN",
     "contract_source": "https://api.weatherxm.com/api/v1/docs/",
     "contract_state": "official_openapi_documented",
     "response_contract": "json_object",
     "protocol": "rest_get",
     "capabilities": ["network_stats_read", "station_read", "rewards_read"],
     "resources": ("station", "rewards")},
    {"id": "wingbits", "name": "Wingbits", "category": "depin",
     "env": ("NEXUS_WINGBITS_API_URL",),
     "contract_state": "official_api_contract_pending",
     "capabilities": ["receiver_read", "coverage_read", "rewards_read"],
     "resources": ("receiver", "coverage", "rewards")},
    {"id": "akash", "name": "Akash", "category": "compute",
     "env": ("NEXUS_AKASH_API_URL",),
     "default_base_url": "https://console-api.akash.network",
     "health_path": "v1/providers",
     "resource_paths": {"provider": "v1/providers"},
     "contract_source": "https://akash.network/docs/api-documentation/rest-api/",
     "contract_state": "official_public_read_only_network_data_api_documented",
     "response_contract": "akash_provider_list",
     "resource_response_contracts": {"provider": "akash_provider_list"},
     "protocol": "rest_get",
     "capabilities": ["provider_read", "gpu_availability_read"],
     "resources": ("provider",)},
    {"id": "nosana", "name": "Nosana", "category": "compute",
     "env": ("NEXUS_NOSANA_API_URL", "NEXUS_NOSANA_API_TOKEN"),
     "default_base_url": "https://api.nosana.com",
     "health_path": "jobs/count",
     "resource_paths": {"job": "jobs/count"},
     "contract_source": "https://learn.nosana.com/api/intro.html",
     "contract_state": "official_api_documented",
     "response_contract": "nosana_job_count",
     "resource_response_contracts": {"job": "nosana_job_count"},
     "protocol": "rest_get",
     "capabilities": ["job_read", "network_stats_read"],
     "resources": ("job",)},
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


def _required_env(item: dict[str, Any]) -> tuple[str, ...]:
    required = list(item.get("env", ()))
    if item.get("default_base_url") and required:
        required = [key for key in required if key != required[0]]
    if item.get("auth_mode") == "basic":
        return tuple(required)
    return tuple(required)


def _config(item: dict[str, Any], source: Mapping[str, str]) -> dict[str, Any]:
    missing = [key for key in _required_env(item) if not str(source.get(key, "")).strip()]
    if missing:
        raise ConnectorError("connector_not_configured")

    url_env = item["env"][0] if item.get("env") and item["env"][0].endswith("_API_URL") else None
    raw_url = str(source.get(url_env, "") if url_env else "").strip() or str(item.get("default_base_url", "")).strip()
    if not raw_url:
        raise ConnectorError("connector_not_configured")
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
    allowed_hosts = _host_allowlist(item, source)
    using_documented_default = bool(
        item.get("default_base_url")
        and raw_url.rstrip("/") == str(item["default_base_url"]).rstrip("/")
        and not str(source.get(url_env, "")).strip()
    )
    if using_documented_default:
        allowed_hosts.add(normalized_host)
    if not local:
        if parts.scheme != "https" or port not in (None, 443):
            raise ConnectorError("remote_connector_requires_https_443")
        if normalized_host not in allowed_hosts:
            raise ConnectorError("connector_host_not_allowlisted")

    suffix = item["id"].upper()
    token_env = item.get("token_env") or next(
        (key for key in item.get("env", ()) if key.endswith("_API_TOKEN")), None
    )
    if token_env is None:
        token_env = item.get("optional_token_env")
    token = str(source.get(token_env, "")).strip() if token_env else ""
    auth_mode = item.get("auth_mode", "token")
    auth_value = None
    if auth_mode == "basic":
        username_env = item["env"][1]
        password_env = item["env"][2]
        username = str(source.get(username_env, "")).strip()
        password = str(source.get(password_env, "")).strip()
        if not username or not password:
            raise ConnectorError("connector_not_configured")
        auth_value = "Basic " + base64.b64encode(
            f"{username}:{password}".encode("utf-8")
        ).decode("ascii")
    elif token:
        header_name = str(source.get(f"NEXUS_{suffix}_API_TOKEN_HEADER", "Authorization")).strip()
        if header_name.casefold() not in {"authorization", "x-api-key", "api-key"}:
            raise ConnectorError("unsupported_connector_auth_header")
        auth_scheme = str(source.get(f"NEXUS_{suffix}_API_AUTH_SCHEME", "Bearer")).strip()
        if not auth_scheme or len(auth_scheme) > 24 or any(ord(c) < 33 for c in auth_scheme):
            raise ConnectorError("invalid_connector_auth_scheme")
        auth_value = f"{auth_scheme} {token}"
        if header_name.casefold() != "authorization":
            auth_value = token

    base_path = parts.path.rstrip("/")
    base_url = urlunsplit((parts.scheme, parts.netloc, base_path, "", "")).rstrip("/")
    auth_fingerprint = auth_value or ""
    if auth_mode == "basic":
        auth_fingerprint = "|".join(
            str(source.get(key, "")) for key in item["env"][1:3]
        )
    # This is a keyed, process-local configuration fingerprint, not password
    # storage. HMAC prevents a leaked verification record from enabling offline
    # guessing of API tokens or Basic-auth credentials.
    fingerprint_payload = (
        raw_url + "|" + auth_fingerprint + "|" + ",".join(sorted(allowed_hosts))
    ).encode("utf-8")
    fingerprint = hmac.new(
        _FINGERPRINT_KEY, fingerprint_payload, digestmod="sha256"
    ).hexdigest()
    return {
        "base_url": base_url,
        "host": normalized_host,
        "local": local,
        "token": token or None,
        "auth_mode": auth_mode,
        "auth_value": auth_value,
        "auth_header": (
            "Authorization" if auth_mode == "basic"
            else str(source.get(f"NEXUS_{suffix}_API_TOKEN_HEADER", "Authorization")).strip()
        ),
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
        if resource == "health":
            raw = str(item.get("health_path", "")).strip()
        else:
            raw = str(item.get("resource_paths", {}).get(resource, "")).strip()
    if not raw:
        raise ConnectorError("connector_resource_path_not_configured")
    return _normalize_path(raw)


def _transport_open(request: Request, timeout: float):
    opener = build_opener(ProxyHandler({}), _NoRedirectHandler())
    return opener.open(request, timeout=timeout)


def _validate_provider_payload(item: dict[str, Any], resource: str, payload: Any) -> bool:
    """Validate documented provider/resource shape; generic JSON is reachability only."""
    contract = (
        item.get("response_contract") if resource == "health"
        else item.get("resource_response_contracts", {}).get(resource)
    )
    if not contract:
        return False
    valid = True
    if contract == "tendermint_status":
        valid = (
            isinstance(payload, dict)
            and isinstance(payload.get("result"), dict)
            and isinstance(payload["result"].get("node_info"), dict)
            and isinstance(payload["result"].get("sync_info"), dict)
        )
    elif contract == "json_rpc":
        valid = (
            isinstance(payload, dict)
            and payload.get("jsonrpc") == "2.0"
            and payload.get("id") == 1
            and "result" in payload
            and "error" not in payload
        )
    elif contract == "helium_hotspot_list":
        valid = (
            isinstance(payload, dict)
            and isinstance(payload.get("items"), list)
            and ("cursor" in payload)
        )
    elif contract == "geodnet_stations":
        valid = (
            isinstance(payload, dict)
            and payload.get("code") == 1000
            and isinstance(payload.get("data"), list)
        )
    elif contract == "anyone_relay_summary":
        valid = (
            isinstance(payload, dict)
            and all(isinstance(payload.get(key), (int, float)) for key in ("all", "offline", "online"))
        )
    elif contract == "numeric_value":
        # Nodle supply endpoints document a bare JSON number, not an object.
        valid = type(payload) in (int, float)
    elif contract == "json_object":
        valid = isinstance(payload, dict)
    elif contract == "akash_provider_list":
        valid = isinstance(payload, list) and all(isinstance(row, dict) for row in payload)
    elif contract == "nosana_job_count":
        valid = (
            isinstance(payload, dict)
            and isinstance(payload.get("total"), int)
            and isinstance(payload.get("byState"), dict)
        )
    if not valid:
        raise ConnectorError("connector_response_contract_mismatch")
    return True


def _request_json(
    item: dict[str, Any],
    resource: str,
    source: Mapping[str, str],
) -> tuple[Any, int, str, str, str, bool]:
    config = _config(item, source)
    relative_path = _resource_path(item, resource, source)
    url = f"{config['base_url']}/{relative_path}"
    query = item.get("health_query", {}) if resource == "health" else item.get("resource_queries", {}).get(resource, {})
    if query:
        url += "?" + urlencode(query)
    headers = {"Accept": "application/json", "User-Agent": "NEXUS-MASTER-readonly/1"}
    if config.get("auth_value"):
        headers[config["auth_header"]] = config["auth_value"]
    protocol = item.get("protocol", "rest_get")
    if protocol == "json_rpc_post":
        method = (
            item.get("health_rpc_method") if resource == "health"
            else item.get("resource_rpc_methods", {}).get(resource)
        )
        allowed_methods = {
            value for value in [item.get("health_rpc_method"), *item.get("resource_rpc_methods", {}).values()]
            if isinstance(value, str)
        }
        if not method or method not in allowed_methods:
            raise ConnectorError("unsupported_read_only_rpc_method")
        payload = json.dumps({"jsonrpc": "2.0", "method": method, "params": [], "id": 1}).encode("utf-8")
        headers["Content-Type"] = "application/json"
        request = Request(url, data=payload, headers=headers, method="POST")
    elif protocol == "rest_get":
        request = Request(url, headers=headers, method="GET")
    else:
        raise ConnectorError("unsupported_connector_protocol")
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
    contract_verified = _validate_provider_payload(item, resource, payload)

    observed_at = datetime.now(timezone.utc).isoformat()
    with _VERIFICATION_LOCK:
        if source is os.environ and resource == "health":
            _LIVE_VERIFICATION[item["id"]] = {
                "ok": contract_verified,
                "reachable": True,
                "contract_verified": contract_verified,
                "fingerprint": config["fingerprint"],
                "observed_at": observed_at,
                "http_status": status_code,
                "resource": resource,
            }
    return payload, status_code, content_type, observed_at, relative_path, contract_verified


def connector_status(env: dict[str, str] | None = None) -> list[dict[str, Any]]:
    source = os.environ if env is None else env
    rows = []
    for item in PROVIDERS:
        configured = [key for key in item.get("env", ()) if str(source.get(key, "")).strip()]
        required = _required_env(item)
        ready = all(str(source.get(key, "")).strip() for key in required)
        default_url_used = bool(item.get("default_base_url") and (
            not item.get("env") or not str(source.get(item["env"][0], "")).strip()
        ))
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
                else "reachable_contract_pending" if live and live.get("reachable")
                else "configured_pending_adapter_validation" if ready
                else "not_configured"
            ),
            "configured_fields": len(configured),
            "required_fields": len(required),
            "default_url_used": default_url_used,
            "protocol": item.get("protocol", "rest_get"),
            "contract_state": item.get("contract_state", "operator_configured_contract_pending"),
            "contract_source": item.get("contract_source"),
            "capabilities": list(item["capabilities"]),
            "resources": list(item["resources"]),
            "adapter_registered": True,
            "mode": "read_only",
            "reachability_verified": bool(live and live.get("reachable")),
            "contract_verified": operational_verified,
            "live_connection_verified": operational_verified,
            "operational_verified": operational_verified,
            "last_verified_at": live.get("observed_at") if live else None,
            "last_http_status": live.get("http_status") if live else None,
            "verified_resource": live.get("resource") if live else None,
            "writes_enabled": False,
            "missing_configuration": [key for key in required if not str(source.get(key, "")).strip()],
        })
    return rows


def probe_connector(provider_id: str, env: Mapping[str, str] | None = None) -> dict[str, Any]:
    source = os.environ if env is None else env
    item = _provider(provider_id)
    if env is None:
        with _VERIFICATION_LOCK:
            _LIVE_VERIFICATION.pop(item["id"], None)
    payload, status_code, content_type, observed_at, path, contract_verified = _request_json(item, "health", source)
    if isinstance(payload, dict):
        data_summary = {"type": "object", "keys": sorted(str(k) for k in payload.keys())[:40]}
    elif isinstance(payload, list):
        data_summary = {"type": "array", "items": len(payload)}
    else:
        data_summary = {"type": type(payload).__name__}
    return {
        "provider_id": item["id"],
        "name": item["name"],
        "status": "live_verified" if contract_verified else "reachable_contract_pending",
        "operational_verified": contract_verified,
        "contract_verified": contract_verified,
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
    payload, status_code, content_type, observed_at, path, contract_verified = _request_json(item, resource, source)
    return {
        "provider_id": item["id"],
        "name": item["name"],
        "resource": resource,
        "status": "live_verified" if contract_verified else "read_succeeded_contract_pending",
        "operational_verified": contract_verified,
        "contract_verified": contract_verified,
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
                "status": "passed" if probe["operational_verified"] else "contract_pending",
                "operational_verified": probe["operational_verified"],
                "reachability_verified": True,
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
    reachable = sum(bool(row.get("reachability_verified")) for row in results)
    contract_pending = sum(row["status"] == "contract_pending" for row in results)
    return {
        "status": "live_verified" if passed == len(PROVIDERS) else "partial",
        "operational_verified": passed == len(PROVIDERS),
        "connectors_tested": len(results),
        "connectors_passed": passed,
        "connectors_reachable": reachable,
        "connectors_contract_pending": contract_pending,
        "connectors_failed_or_unconfigured": len(results) - reachable,
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
