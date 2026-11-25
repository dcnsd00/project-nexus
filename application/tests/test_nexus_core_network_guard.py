import asyncio
import sys
from pathlib import Path

CORE_ROOT = Path(__file__).resolve().parents[1] / "core" / "PROJECT-NEXUS-LOCAL"
if str(CORE_ROOT) not in sys.path:
    sys.path.insert(0, str(CORE_ROOT))

from app.network_guard import LoopbackOnlyMiddleware, request_is_loopback


def _scope(peer, host, *, forwarded_for=None, kind="http"):
    headers = [(b"host", host.encode("ascii"))] if host is not None else []
    if forwarded_for is not None:
        headers.append((b"x-forwarded-for", forwarded_for.encode("ascii")))
    return {
        "type": kind,
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": "/api/health",
        "raw_path": b"/api/health",
        "query_string": b"",
        "headers": headers,
        "client": (peer, 12345),
        "server": ("127.0.0.1", 8765),
    }


def _run(scope):
    messages = []

    async def downstream(inner_scope, receive, send):
        await send({
            "type": "http.response.start",
            "status": 200,
            "headers": [(b"content-type", b"text/plain")],
        })
        await send({"type": "http.response.body", "body": b"ok"})

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message):
        messages.append(message)

    asyncio.run(LoopbackOnlyMiddleware(downstream)(scope, receive, send))
    return messages


def _status(messages):
    starts = [message for message in messages if message["type"] == "http.response.start"]
    return starts[0]["status"] if starts else None


def test_local_ipv4_peer_and_host_are_allowed():
    scope = _scope("127.0.0.1", "127.0.0.1:8765")
    assert request_is_loopback(scope)
    assert _status(_run(scope)) == 200


def test_local_ipv6_peer_and_host_are_allowed():
    scope = _scope("::1", "[::1]:8765")
    assert request_is_loopback(scope)
    assert _status(_run(scope)) == 200


def test_remote_peer_is_rejected_even_with_loopback_host_and_spoofed_forwarded_ip():
    scope = _scope(
        "203.0.113.25",
        "127.0.0.1:8765",
        forwarded_for="127.0.0.1",
    )
    assert not request_is_loopback(scope)
    assert _status(_run(scope)) == 403


def test_loopback_peer_with_remote_host_is_rejected():
    scope = _scope("127.0.0.1", "nexus.example.com")
    assert not request_is_loopback(scope)
    assert _status(_run(scope)) == 403


def test_duplicate_host_headers_fail_closed():
    scope = _scope("127.0.0.1", "127.0.0.1")
    scope["headers"].append((b"host", b"localhost"))
    assert not request_is_loopback(scope)
    assert _status(_run(scope)) == 403


def test_standard_starlette_testclient_scope_is_allowed():
    scope = _scope("testclient", "testserver")
    assert request_is_loopback(scope)
    assert _status(_run(scope)) == 200


def test_non_loopback_websocket_is_closed_with_policy_violation():
    scope = _scope("203.0.113.25", "localhost", kind="websocket")
    messages = []

    async def downstream(inner_scope, receive, send):
        raise AssertionError("non-loopback websocket must not reach the app")

    async def receive():
        return {"type": "websocket.connect"}

    async def send(message):
        messages.append(message)

    asyncio.run(LoopbackOnlyMiddleware(downstream)(scope, receive, send))
    assert messages == [{"type": "websocket.close", "code": 1008}]
