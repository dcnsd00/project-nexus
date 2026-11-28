"""Evidence-based, read-only Bitcoin Core node telemetry.

Only loopback RPC endpoints are permitted. Credentials are read from process
environment or the standard Bitcoin Core cookie file and are never returned.
No wallet, mining, transaction, or chain-write RPC methods are invoked.
"""
from __future__ import annotations

import os
import platform
import shutil
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from mining.solo_bitcoin_rpc import BitcoinRPC, SoloRPCError


def _default_cookie() -> Path:
    if os.name == "nt":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
        return base / "Bitcoin" / ".cookie"
    return Path.home() / ".bitcoin" / ".cookie"


def _rpc_configuration() -> dict[str, Any]:
    url = os.environ.get("NEXUS_BITCOIN_RPC_URL", "http://127.0.0.1:18443").strip()
    cookie_value = os.environ.get("NEXUS_BITCOIN_RPC_COOKIE")
    cookie_path_value = os.environ.get("NEXUS_BITCOIN_RPC_COOKIE_FILE")
    cookie_path = Path(cookie_path_value).expanduser() if cookie_path_value else _default_cookie()
    username = os.environ.get("NEXUS_BITCOIN_RPC_USER")
    password = os.environ.get("NEXUS_BITCOIN_RPC_PASSWORD")
    cookie_file = None
    if cookie_value:
        # Use an ephemeral in-memory adapter for explicitly supplied cookie text.
        cookie_file = None
    elif cookie_path.is_file():
        cookie_file = str(cookie_path)
    parsed = urlparse(url)
    safe_loopback = parsed.scheme == "http" and parsed.hostname in {"127.0.0.1", "localhost", "::1"}
    credentials_available = bool(cookie_value or cookie_file or (username and password))
    return {
        "url": url,
        "parsed": parsed,
        "safe_loopback": safe_loopback,
        "credentials_available": credentials_available,
        "username": username,
        "password": password,
        "cookie_file": cookie_file,
        "cookie_value": cookie_value,
    }


def bitcoin_node_snapshot(rpc_factory=None, include_privacy: bool = False) -> dict[str, Any]:
    """Return observed node state; never infer connectivity from installed tools."""
    sampled_at = time.time()
    bitcoind = shutil.which("bitcoind") or shutil.which("bitcoind.exe")
    bitcoin_cli = shutil.which("bitcoin-cli") or shutil.which("bitcoin-cli.exe")
    cfg = _rpc_configuration()
    base = {
        "schema_version": 1,
        "sampled_at": sampled_at,
        "node": "bitcoin_core",
        "binary_detection": {
            "bitcoind": {"available": bool(bitcoind), "path": bitcoind},
            "bitcoin_cli": {"available": bool(bitcoin_cli), "path": bitcoin_cli},
        },
        "rpc": {
            "endpoint": cfg["url"],
            "transport_policy": "loopback_http_only",
            "credentials_configured": cfg["credentials_available"],
            "reachable": False,
            "status": "not_configured",
            "latency_ms": None,
        },
        "network": None,
        "sync": None,
        "peers": None,
        "mempool": None,
        "data_quality": "node_rpc_unavailable",
        "error": None,
    }
    if not cfg["safe_loopback"]:
        base["rpc"]["status"] = "blocked_non_loopback_endpoint"
        base["error"] = "Only loopback Bitcoin Core RPC endpoints are allowed."
        return base
    if not cfg["credentials_available"]:
        base["error"] = "Configure NEXUS_BITCOIN_RPC_COOKIE_FILE or NEXUS_BITCOIN_RPC_USER and NEXUS_BITCOIN_RPC_PASSWORD."
        return base
    try:
        if rpc_factory:
            rpc = rpc_factory(cfg)
        elif cfg["cookie_value"]:
            # Avoid writing credentials to disk; construct a small adapter with the same call contract.
            class _CookieRPC:
                def __init__(self, url: str, cookie: str):
                    self.url = url
                    self.cookie = cookie
                def call(self, method: str, params=None):
                    import base64
                    import json
                    import urllib.request
                    token = base64.b64encode(self.cookie.encode()).decode()
                    body = json.dumps({"jsonrpc": "1.0", "id": "nexus-telemetry",
                                       "method": method, "params": params or []}).encode()
                    req = urllib.request.Request(self.url, body, {
                        "Authorization": "Basic " + token,
                        "Content-Type": "application/json",
                    })
                    with urllib.request.urlopen(req, timeout=2.0) as response:
                        payload = json.loads(response.read())
                    if payload.get("error"):
                        raise SoloRPCError(f"RPC {method}: {payload['error']}")
                    return payload.get("result")
            rpc = _CookieRPC(cfg["url"], cfg["cookie_value"])
        else:
            rpc = BitcoinRPC(
                cfg["url"], cfg["username"], cfg["password"],
                cfg["cookie_file"], timeout=2.0,
            )
        started = time.perf_counter()
        chain = rpc.call("getblockchaininfo")
        latency_ms = round((time.perf_counter() - started) * 1000, 3)
        if not isinstance(chain, dict):
            raise SoloRPCError("getblockchaininfo returned a non-object response")
        network_info = rpc.call("getnetworkinfo")
        peer_rows = rpc.call("getpeerinfo")
        mempool_info = rpc.call("getmempoolinfo")
        blocks = chain.get("blocks")
        headers = chain.get("headers")
        ibd = chain.get("initialblockdownload")
        base.update({
            "rpc": {
                **base["rpc"],
                "reachable": True,
                "status": "connected",
                "latency_ms": latency_ms,
            },
            "network": {
                "chain": chain.get("chain"),
                "chainwork": chain.get("chainwork"),
                "version": network_info.get("version") if isinstance(network_info, dict) else None,
                "subversion": network_info.get("subversion") if isinstance(network_info, dict) else None,
                "protocol_version": network_info.get("protocolversion") if isinstance(network_info, dict) else None,
            },
            "sync": {
                "blocks": blocks,
                "headers": headers,
                "blocks_behind_headers": max(0, headers - blocks) if isinstance(headers, int) and isinstance(blocks, int) else None,
                "initial_block_download": ibd,
                "verification_progress": chain.get("verificationprogress"),
                "pruned": chain.get("pruned"),
            },
            "peers": {
                "count": len(peer_rows) if isinstance(peer_rows, list) else None,
                "inbound": sum(1 for p in peer_rows if p.get("inbound")) if isinstance(peer_rows, list) else None,
                "outbound": sum(1 for p in peer_rows if not p.get("inbound")) if isinstance(peer_rows, list) else None,
            },
            "mempool": {
                "transactions": mempool_info.get("size") if isinstance(mempool_info, dict) else None,
                "bytes": mempool_info.get("bytes") if isinstance(mempool_info, dict) else None,
                "usage_bytes": mempool_info.get("usage") if isinstance(mempool_info, dict) else None,
                "total_fee_btc": mempool_info.get("total_fee") if isinstance(mempool_info, dict) else None,
            },
            "data_quality": "measured_from_successful_bitcoin_core_rpc",
            "error": None,
        })
        if include_privacy:
            try:
                from modules.bitcoin_privacy_guard import assess_bitcoin_peer_privacy
                base["privacy"] = assess_bitcoin_peer_privacy(peer_rows)
            except Exception:
                # The optional analyzer must never break existing node telemetry.
                base["privacy"] = {
                    "status": "assessment_unavailable",
                    "severity": "unknown",
                    "wallet_state": "not_inspected",
                    "wallet_broadcast_setting": "not_inspected",
                    "peer_address_fields_inspected": False,
                    "transaction_data_inspected": False,
                    "peer_addresses_returned": False,
                    "actions_taken": [],
                }
        return base
    except Exception as exc:
        base["rpc"]["status"] = "connection_failed"
        base["error"] = f"{type(exc).__name__}: {str(exc)[:300]}"
        return base
