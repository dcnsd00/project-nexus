from fastapi import FastAPI
from fastapi.testclient import TestClient

from nexus_edge.gateway_runtime import EdgeGatewayRuntime
from nexus_edge.manager import EdgeManager
from nexus_edge.replay_guard import MemoryReplayGuard


def _gateway_factory(**kwargs):
    from nexus_edge.gateway import create_edge_app
    return create_edge_app(**kwargs)


def test_gateway_runtime_is_disabled_by_default():
    host = FastAPI()
    runtime = EdgeGatewayRuntime(env={})
    runtime.start(host)
    assert runtime.status()["gateway"] == "disabled_by_default"
    assert not any(getattr(route, "name", None) == "nexus-edge-gateway"
                   for route in host.router.routes)


def test_gateway_runtime_mounts_inside_master_only_with_opt_in():
    env = {
        "NEXUS_EDGE_GATEWAY_ENABLED": "true",
        "NEXUS_EDGE_PROVISIONING_TOKEN": "p" * 40,
    }
    host = FastAPI()
    runtime = EdgeGatewayRuntime(
        env=env,
        manager_factory=lambda: EdgeManager(replay_guard=MemoryReplayGuard()),
        app_factory=_gateway_factory,
    )
    runtime.start(host)
    assert runtime.status()["gateway"] == "active"
    assert runtime.status()["mounted_at"] == "/edge"
    with TestClient(host) as client:
        health = client.get("/edge/v1/edge/health")
        assert health.status_code == 200
        assert health.json()["wallet_access_enabled"] is False
        assert health.json()["miner_autostart_enabled"] is False
    runtime.stop(host)
    assert runtime.status()["gateway"] == "enabled_not_started"
    assert not any(getattr(route, "name", None) == "nexus-edge-gateway"
                   for route in host.router.routes)


def test_gateway_runtime_fails_closed_without_operator_token():
    host = FastAPI()
    runtime = EdgeGatewayRuntime(
        env={"NEXUS_EDGE_GATEWAY_ENABLED": "true"},
        manager_factory=lambda: EdgeManager(),
        app_factory=_gateway_factory,
    )
    try:
        runtime.start(host)
    except RuntimeError as exc:
        assert "NEXUS_EDGE_PROVISIONING_TOKEN" in str(exc)
    else:
        raise AssertionError("gateway must fail closed without operator token")
    assert runtime.status()["gateway"] == "enabled_not_started"
