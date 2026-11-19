from fastapi import FastAPI
from fastapi.testclient import TestClient
from cryptography.fernet import Fernet

from nexus_edge.gateway_runtime import EdgeGatewayRuntime
from nexus_edge.manager import EdgeManager
from nexus_edge.replay_guard import MemoryReplayGuard, SQLiteReplayGuard
from nexus_edge.sqlite_store import SQLiteEdgeStore


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


def test_gateway_runtime_mounts_inside_master_only_with_opt_in(tmp_path):
    env = {
        "NEXUS_EDGE_GATEWAY_ENABLED": "true",
        "NEXUS_EDGE_PROVISIONING_TOKEN": "p" * 40,
    }
    database = tmp_path / "edge.sqlite3"
    manager = EdgeManager(
        store=SQLiteEdgeStore(database, encryption_key=Fernet.generate_key()),
        replay_guard=SQLiteReplayGuard(database),
    )
    host = FastAPI()
    runtime = EdgeGatewayRuntime(
        env=env,
        manager_factory=lambda: (_ for _ in ()).throw(
            AssertionError("must reuse the LifecycleManager-owned instance")
        ),
        app_factory=_gateway_factory,
    )
    runtime.start(host, manager)
    assert runtime.status()["gateway"] == "active"
    assert runtime.status()["mounted_at"] == "/edge"
    assert runtime._mounted_app.state.edge_manager is manager
    with TestClient(host) as client:
        health = client.get("/edge/v1/edge/health")
        assert health.status_code == 200
        assert health.json()["wallet_access_enabled"] is False
        assert health.json()["miner_autostart_enabled"] is False
    runtime.stop(host)
    assert runtime.status()["gateway"] == "enabled_not_started"
    assert not any(getattr(route, "name", None) == "nexus-edge-gateway"
                   for route in host.router.routes)


def test_gateway_runtime_rejects_ephemeral_manager(tmp_path):
    env = {
        "NEXUS_EDGE_GATEWAY_ENABLED": "true",
        "NEXUS_EDGE_PROVISIONING_TOKEN": "p" * 40,
    }
    host = FastAPI()
    runtime = EdgeGatewayRuntime(env=env, app_factory=_gateway_factory)
    ephemeral = EdgeManager(replay_guard=MemoryReplayGuard())

    try:
        runtime.start(host, ephemeral)
    except RuntimeError as exc:
        assert "sqlite_persistent" in str(exc)
    else:
        raise AssertionError("online gateway must reject in-memory EDGE state")
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



def test_gateway_runtime_does_not_release_injected_manager_lock_on_mount_failure(tmp_path):
    import pytest
    from nexus_edge.gateway import create_edge_manager_from_env

    env = {
        "NEXUS_EDGE_GATEWAY_ENABLED": "true",
        "NEXUS_EDGE_PROVISIONING_TOKEN": "p" * 40,
        "NEXUS_EDGE_STORAGE_KEY": Fernet.generate_key().decode("ascii"),
        "NEXUS_EDGE_DATABASE": str(tmp_path / "edge.sqlite3"),
    }
    manager = create_edge_manager_from_env(env)

    def fail_mount(**kwargs):
        raise RuntimeError("simulated mount failure")

    runtime = EdgeGatewayRuntime(env=env, app_factory=fail_mount)
    try:
        with pytest.raises(RuntimeError, match="simulated mount failure"):
            runtime.start(FastAPI(), manager)
        with pytest.raises(RuntimeError, match="already in use by another process"):
            create_edge_manager_from_env(env)
    finally:
        manager._runtime_lock.release()


def test_gateway_runtime_does_not_release_injected_manager_lock_on_mode_rejection(tmp_path):
    import pytest
    from nexus_edge.gateway import create_edge_manager_from_env

    env = {
        "NEXUS_EDGE_GATEWAY_ENABLED": "true",
        "NEXUS_EDGE_PROVISIONING_TOKEN": "p" * 40,
        "NEXUS_EDGE_STORAGE_KEY": Fernet.generate_key().decode("ascii"),
        "NEXUS_EDGE_DATABASE": str(tmp_path / "edge.sqlite3"),
    }
    manager = create_edge_manager_from_env(env)
    manager.snapshot = lambda: {"mode": "in_memory_pilot"}
    runtime = EdgeGatewayRuntime(env=env, app_factory=_gateway_factory)
    try:
        with pytest.raises(RuntimeError, match="sqlite_persistent"):
            runtime.start(FastAPI(), manager)
        with pytest.raises(RuntimeError, match="already in use by another process"):
            create_edge_manager_from_env(env)
    finally:
        manager._runtime_lock.release()
