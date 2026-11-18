"""Read-only EVM JSON-RPC node/provider telemetry.

Only HTTPS endpoints explicitly supplied through NEXUS_EVM_RPC_URL are used.
Redirects and obvious local/private targets are rejected. The adapter invokes
read-only JSON-RPC methods only and never signs or broadcasts transactions.
"""
from __future__ import annotations

import ipaddress
import json
import os
import time
import urllib.parse
import urllib.request
from typing import Any


_CHAIN_NAMES = {
    1: "ethereum", 10: "optimism", 137: "polygon", 8453: "base",
    42161: "arbitrum", 11155111: "ethereum-sepolia", 84532: "base-sepolia",
}


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _validate_endpoint(url: str) -> tuple[bool, str | None]:
    try:
        parsed = urllib.parse.urlsplit(url)
    except ValueError:
        return False, None
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        return False, None
    host = parsed.hostname.lower().rstrip(".")
    if host in {"localhost", "localhost.localdomain"} or host.endswith((".local", ".internal", ".lan")):
        return False, None
    try:
        ip = ipaddress.ip_address(host)
        if not ip.is_global:
            return False, None
    except ValueError:
        pass
    if len(url) > 2048:
        return False, None
    return True, host


def _rpc(url: str, method: str, params: list[Any] | None = None, timeout: float = 4.0) -> Any:
    payload = json.dumps({"jsonrpc": "2.0", "id": "nexus-readonly", "method": method,
                          "params": params or []}).encode("utf-8")
    request = urllib.request.Request(url, data=payload, headers={
        "Accept": "application/json", "Content-Type": "application/json",
        "User-Agent": "NEXUS-MASTER/readonly-EVM-telemetry",
    }, method="POST")
    opener = urllib.request.build_opener(_NoRedirect())
    with opener.open(request, timeout=max(1.0, min(float(timeout), 8.0))) as response:
        if response.status != 200:
            raise RuntimeError(f"JSON-RPC HTTP {response.status}")
        raw = response.read(1_000_000)
    data = json.loads(raw.decode("utf-8"))
    if not isinstance(data, dict) or data.get("error") or "result" not in data:
        raise RuntimeError("JSON-RPC returned an invalid or error response")
    return data["result"]


def _hex_int(value: Any) -> int | None:
    if not isinstance(value, str) or not value.startswith("0x"):
        return None
    try:
        return int(value, 16)
    except ValueError:
        return None


def evm_node_snapshot(rpc_factory=None) -> dict[str, Any]:
    sampled_at = time.time()
    url = os.environ.get("NEXUS_EVM_RPC_URL", "").strip()
    base = {
        "schema_version": 1, "sampled_at": sampled_at,
        "provider": "configured_evm_json_rpc",
        "rpc": {"configured": bool(url), "endpoint_host": None,
                "status": "not_configured" if not url else "invalid_endpoint",
                "reachable": False, "latency_ms": None},
        "network": None, "sync": None, "peers": None,
        "gas_price_wei": None, "latest_block": None,
        "data_quality": "rpc_unavailable",
        "read_only_methods": ["eth_chainId", "eth_blockNumber", "eth_syncing",
                              "net_peerCount", "eth_gasPrice", "eth_getBlockByNumber"],
        "writes_enabled": False, "error": None,
    }
    if not url:
        return base
    valid, host = _validate_endpoint(url)
    if not valid:
        base["error"] = "NEXUS_EVM_RPC_URL must be HTTPS without embedded credentials or obvious local/private targets."
        return base
    base["rpc"]["endpoint_host"] = host
    try:
        call = rpc_factory or (lambda method, params=None: _rpc(url, method, params))
        started = time.perf_counter()
        chain_hex, block_hex = call("eth_chainId"), call("eth_blockNumber")
        latency = round((time.perf_counter() - started) * 1000, 3)
        chain_id, block_number = _hex_int(chain_hex), _hex_int(block_hex)
        if chain_id is None or block_number is None:
            raise RuntimeError("Invalid eth_chainId or eth_blockNumber response")
        base["rpc"].update({"status": "connected", "reachable": True, "latency_ms": latency})
        base["network"] = {"chain_id": chain_id, "name": _CHAIN_NAMES.get(chain_id, "unknown_evm_chain")}
        base["latest_block"] = {"number": block_number}
        try:
            syncing = call("eth_syncing")
            if syncing is False:
                base["sync"] = {"status": "not_syncing", "current_block": block_number,
                                "highest_block": block_number, "blocks_behind": 0}
            elif isinstance(syncing, dict):
                current, highest = _hex_int(syncing.get("currentBlock")), _hex_int(syncing.get("highestBlock"))
                base["sync"] = {"status": "syncing", "current_block": current, "highest_block": highest,
                                "blocks_behind": max(0, highest-current) if current is not None and highest is not None else None}
            else:
                base["sync"] = {"status": "unknown", "current_block": None, "highest_block": None, "blocks_behind": None}
        except Exception:
            base["sync"] = {"status": "unavailable", "current_block": None, "highest_block": None, "blocks_behind": None}
        try:
            peers = _hex_int(call("net_peerCount"))
            base["peers"] = {"count": peers, "status": "reported" if peers is not None else "unavailable"}
        except Exception:
            base["peers"] = {"count": None, "status": "unavailable"}
        try:
            base["gas_price_wei"] = _hex_int(call("eth_gasPrice"))
        except Exception:
            pass
        try:
            block = call("eth_getBlockByNumber", ["latest", False])
            if isinstance(block, dict):
                base["latest_block"].update({
                    "hash": block.get("hash"),
                    "timestamp_unix": _hex_int(block.get("timestamp")),
                    "transactions": len(block.get("transactions", [])) if isinstance(block.get("transactions"), list) else None,
                })
        except Exception:
            pass
        base["data_quality"] = "measured_from_successful_evm_json_rpc"
        return base
    except Exception as exc:
        base["rpc"]["status"] = "connection_failed"
        # urllib/provider exceptions can embed the full request URL, including
        # API keys in path or query parameters. Expose only the exception class.
        base["error"] = f"{type(exc).__name__}: RPC request failed; endpoint details redacted."
        return base
