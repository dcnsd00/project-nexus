import ipaddress

from fastapi import FastAPI
from fastapi.testclient import TestClient

from nexus_edge.rate_limit import EdgeRateLimitMiddleware, rate_limit_settings


def _app(**settings):
    app = FastAPI()
    app.add_middleware(EdgeRateLimitMiddleware, **settings)

    @app.get("/health")
    def health():
        return {"ok": True}

    @app.get("/v1/edge/nodes/{node_id}/heartbeat")
    def heartbeat(node_id: str):
        return {"node_id": node_id}

    return app


def test_rate_limiter_returns_429_after_configured_limit():
    client = TestClient(_app(max_requests=2, window_seconds=60, max_keys=100))
    assert client.get("/health").status_code == 200
    assert client.get("/health").status_code == 200
    limited = client.get("/health")
    assert limited.status_code == 429
    assert limited.json()["detail"] == "rate limit exceeded"
    assert int(limited.headers["Retry-After"]) >= 1


def test_rate_limiter_applies_node_identity_bucket():
    client = TestClient(_app(max_requests=2, window_seconds=60, max_keys=100))
    assert client.get("/v1/edge/nodes/esp32-node-01/heartbeat").status_code == 200
    assert client.get("/v1/edge/nodes/esp32-node-01/heartbeat").status_code == 200
    assert client.get("/v1/edge/nodes/esp32-node-01/heartbeat").status_code == 429


def test_rate_limiter_does_not_trust_forwarded_ip_from_untrusted_peer():
    middleware = EdgeRateLimitMiddleware(
        lambda *_: None,
        max_requests=10,
        window_seconds=60,
        max_keys=100,
        trusted_proxy_cidrs=("10.0.0.0/8",),
    )
    scope = {"client": ("203.0.113.8", 12345), "path": "/health"}
    headers = {b"x-forwarded-for": b"198.51.100.22"}
    assert middleware._source_ip(scope, headers) == "203.0.113.8"


def test_rate_limiter_uses_forwarded_ip_only_from_trusted_proxy():
    middleware = EdgeRateLimitMiddleware(
        lambda *_: None,
        max_requests=10,
        window_seconds=60,
        max_keys=100,
        trusted_proxy_cidrs=("10.0.0.0/8",),
    )
    scope = {"client": ("10.0.0.5", 12345), "path": "/health"}
    headers = {b"x-forwarded-for": b"198.51.100.22, 10.0.0.1"}
    assert middleware._source_ip(scope, headers) == "198.51.100.22"


def test_rate_limit_settings_validate_and_default_to_enabled():
    settings = rate_limit_settings({})
    assert settings["enabled"] is True
    assert settings["max_requests"] == 120
    assert settings["window_seconds"] == 60
    assert settings["trusted_proxy_cidrs"] == ()

    try:
        rate_limit_settings({"NEXUS_EDGE_RATE_LIMIT_REQUESTS": "0"})
    except RuntimeError as exc:
        assert "NEXUS_EDGE_RATE_LIMIT_REQUESTS" in str(exc)
    else:
        raise AssertionError("invalid rate-limit values must fail closed")



def test_rate_limiter_ignores_spoofed_leftmost_forwarded_address():
    middleware = EdgeRateLimitMiddleware(
        lambda *_: None,
        max_requests=10,
        window_seconds=60,
        max_keys=100,
        trusted_proxy_cidrs=("10.0.0.0/8",),
    )
    scope = {"client": ("10.0.0.5", 12345), "path": "/health"}
    # The trusted proxy appends the actual client address to a header that
    # already contained a spoofed value supplied by the connecting client.
    headers = {b"x-forwarded-for": b"203.0.113.200, 198.51.100.22"}
    assert middleware._source_ip(scope, headers) == "198.51.100.22"
