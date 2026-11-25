"""Fail-closed loopback boundary for the local NEXUS CORE ASGI application.

This is an exposure guard, not user authentication. Keep the normal CORE
listener on 127.0.0.1 and place private-network access behind the NEXUS
reverse proxy, which rewrites Host to the local upstream authority.
"""
from __future__ import annotations

import ipaddress
from urllib.parse import urlsplit
from typing import Any

from starlette.responses import JSONResponse


def _peer_is_loopback(peer: Any) -> bool:
    if not isinstance(peer, str) or not peer:
        return False
    try:
        address = ipaddress.ip_address(peer.split("%", 1)[0])
    except ValueError:
        return False
    return address.is_loopback


def _host_is_loopback(raw_host: bytes | str | None) -> bool:
    if raw_host is None:
        return False
    try:
        value = raw_host.decode("latin-1") if isinstance(raw_host, bytes) else str(raw_host)
        value = value.strip()
        if not value or "," in value or any(ch.isspace() for ch in value):
            return False
        parsed = urlsplit("//" + value)
        if parsed.username is not None or parsed.password is not None:
            return False
        if parsed.path or parsed.query or parsed.fragment:
            return False
        _ = parsed.port
        hostname = (parsed.hostname or "").rstrip(".").lower()
    except (UnicodeError, ValueError):
        return False
    if hostname == "localhost":
        return True
    try:
        return ipaddress.ip_address(hostname.split("%", 1)[0]).is_loopback
    except ValueError:
        return False


def request_is_loopback(scope: dict[str, Any]) -> bool:
    """Require both a loopback socket peer and loopback Host authority.

    X-Forwarded-For is intentionally ignored. The standard Starlette
    TestClient scope pair is recognized as a test harness, not a TCP peer.
    """
    if scope.get("type") not in {"http", "websocket"}:
        return True
    client = scope.get("client")
    if not isinstance(client, (tuple, list)) or not client:
        return False
    peer = str(client[0])
    hosts = [
        value for key, value in scope.get("headers", [])
        if key.lower() == b"host"
    ]
    if len(hosts) != 1:
        return False
    host_raw = hosts[0]
    if peer.lower() == "testclient":
        try:
            test_host = host_raw.decode("latin-1").strip().lower()
        except UnicodeError:
            return False
        return scope.get("type") == "http" and test_host == "testserver"
    return _peer_is_loopback(peer) and _host_is_loopback(host_raw)


class LoopbackOnlyMiddleware:
    """Reject non-loopback clients before they reach CORE API routes."""

    def __init__(self, app: Any) -> None:
        self.app = app

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        if scope.get("type") not in {"http", "websocket"}:
            await self.app(scope, receive, send)
            return
        if request_is_loopback(scope):
            await self.app(scope, receive, send)
            return
        if scope.get("type") == "websocket":
            await send({"type": "websocket.close", "code": 1008})
            return
        response = JSONResponse(
            {"detail": "NEXUS CORE accepts local loopback requests only"},
            status_code=403,
            headers={"Cache-Control": "no-store"},
        )
        await response(scope, receive, send)
