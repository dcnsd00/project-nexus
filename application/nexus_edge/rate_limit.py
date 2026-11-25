"""Bounded in-process rate limiting for the NEXUS EDGE ASGI gateway.

This is defense in depth for the documented single-process gateway pilot.
Multi-worker or distributed deployments must also enforce limits at the
reverse proxy/WAF boundary or use a shared rate-limit backend.
"""
from __future__ import annotations

import hashlib
import ipaddress
import math
import re
import threading
import time
from collections import OrderedDict
from typing import Any

from starlette.responses import JSONResponse


_NODE_PATH = re.compile(r"(?:^|/)nodes/([A-Za-z0-9][A-Za-z0-9._:-]{2,63})(?:/|$)")


def _truthy(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _bounded_int(values: dict[str, str], name: str, default: int, minimum: int, maximum: int) -> int:
    raw = values.get(name, str(default)).strip()
    try:
        result = int(raw)
    except (TypeError, ValueError) as exc:
        raise RuntimeError(f"{name} must be an integer") from exc
    if not minimum <= result <= maximum:
        raise RuntimeError(f"{name} must be between {minimum} and {maximum}")
    return result


def rate_limit_settings(env: dict[str, str]) -> dict[str, Any]:
    """Read validated gateway rate-limit settings; enabled by default."""
    enabled = _truthy(env.get("NEXUS_EDGE_RATE_LIMIT_ENABLED"), default=True)
    settings: dict[str, Any] = {
        "enabled": enabled,
        "max_requests": _bounded_int(env, "NEXUS_EDGE_RATE_LIMIT_REQUESTS", 120, 1, 100000),
        "window_seconds": _bounded_int(env, "NEXUS_EDGE_RATE_LIMIT_WINDOW_S", 60, 1, 3600),
        "max_keys": _bounded_int(env, "NEXUS_EDGE_RATE_LIMIT_MAX_KEYS", 10000, 100, 100000),
        "trusted_proxy_cidrs": tuple(
            item.strip() for item in env.get("NEXUS_EDGE_TRUSTED_PROXY_CIDRS", "").split(",")
            if item.strip()
        ),
    }
    return settings


class EdgeRateLimitMiddleware:
    """Apply fixed-window limits to source IP and authenticated EDGE identity."""

    def __init__(
        self,
        app: Any,
        *,
        max_requests: int = 120,
        window_seconds: int = 60,
        max_keys: int = 10000,
        trusted_proxy_cidrs: tuple[str, ...] | list[str] = (),
    ) -> None:
        if max_requests < 1 or window_seconds < 1 or max_keys < 100:
            raise ValueError("invalid rate-limit bounds")
        self.app = app
        self.max_requests = int(max_requests)
        self.window_seconds = int(window_seconds)
        self.max_keys = int(max_keys)
        try:
            self.trusted_proxies = tuple(ipaddress.ip_network(item, strict=False) for item in trusted_proxy_cidrs)
        except ValueError as exc:
            raise ValueError("NEXUS_EDGE_TRUSTED_PROXY_CIDRS contains an invalid network") from exc
        self._buckets: OrderedDict[str, tuple[float, int]] = OrderedDict()
        self._lock = threading.Lock()
        self._requests_seen = 0

    def _source_ip(self, scope: dict[str, Any], headers: dict[bytes, bytes]) -> str:
        client = scope.get("client")
        peer = str(client[0]) if client else "unknown"
        try:
            peer_ip = ipaddress.ip_address(peer.split("%", 1)[0])
        except ValueError:
            return peer.lower()

        if self.trusted_proxies and any(peer_ip in network for network in self.trusted_proxies):
            forwarded = headers.get(b"x-forwarded-for", b"").decode("latin-1")
            # Only trust X-Forwarded-For when the immediate peer is allowlisted.
            # Use the left-most address supplied by the trusted proxy chain.
            candidate = forwarded.split(",", 1)[0].strip()
            try:
                return str(ipaddress.ip_address(candidate.split("%", 1)[0]))
            except ValueError:
                pass
        return str(peer_ip)

    def _keys(self, scope: dict[str, Any], headers: dict[bytes, bytes]) -> list[str]:
        keys = [f"ip:{self._source_ip(scope, headers)}"]
        path = str(scope.get("path", ""))
        node_match = _NODE_PATH.search(path)
        if node_match:
            keys.append(f"node:{node_match.group(1)}")
        authorization = headers.get(b"authorization", b"")
        if authorization.lower().startswith(b"bearer "):
            token = authorization[7:].strip()
            if token:
                digest = hashlib.sha256(token).hexdigest()
                keys.append(f"operator:{digest}")
        return list(dict.fromkeys(keys))

    def _consume(self, keys: list[str], now: float) -> int | None:
        with self._lock:
            self._requests_seen += 1
            if self._requests_seen % 128 == 0:
                expired = [
                    key for key, (started, _) in self._buckets.items()
                    if now - started >= self.window_seconds
                ]
                for key in expired:
                    self._buckets.pop(key, None)

            retry_after = 0
            for key in keys:
                bucket = self._buckets.get(key)
                if bucket is None or now - bucket[0] >= self.window_seconds:
                    continue
                if bucket[1] >= self.max_requests:
                    retry_after = max(
                        retry_after,
                        max(1, math.ceil(self.window_seconds - (now - bucket[0]))),
                    )
            if retry_after:
                return retry_after

            for key in keys:
                bucket = self._buckets.get(key)
                if bucket is None or now - bucket[0] >= self.window_seconds:
                    self._buckets[key] = (now, 1)
                else:
                    self._buckets[key] = (bucket[0], bucket[1] + 1)
                self._buckets.move_to_end(key)

            while len(self._buckets) > self.max_keys:
                self._buckets.popitem(last=False)
            return None

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return
        headers = {key.lower(): value for key, value in scope.get("headers", [])}
        retry_after = self._consume(self._keys(scope, headers), time.monotonic())
        if retry_after is not None:
            response = JSONResponse(
                {"detail": "rate limit exceeded", "retry_after_seconds": retry_after},
                status_code=429,
                headers={
                    "Retry-After": str(retry_after),
                    "X-RateLimit-Limit": str(self.max_requests),
                },
            )
            await response(scope, receive, send)
            return
        await self.app(scope, receive, send)
