"""Cross-process exclusion for SQLite-backed NEXUS EDGE runtime."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest
from cryptography.fernet import Fernet
from fastapi import FastAPI
from fastapi.testclient import TestClient

from nexus_edge.gateway import create_edge_app, create_edge_manager_from_env
from nexus_edge.gateway_runtime import EdgeGatewayRuntime
from nexus_edge.runtime import EdgeTransportRuntime
from nexus_edge.runtime_lock import EdgeRuntimeLock
from nexus_edge.transports import MQTTConfig


class FakeBridge:
    def __init__(self, config, callback):
        self.callback = callback
        self.started = False

    def start(self):
        self.started = True

    def stop(self):
        self.started = False


def _env(tmp_path):
    return {
        "NEXUS_EDGE_DATABASE": str(tmp_path / "edge.sqlite3"),
        "NEXUS_EDGE_STORAGE_KEY": Fernet.generate_key().decode("ascii"),
        "NEXUS_EDGE_PROVISIONING_TOKEN": "p" * 40,
    }


def test_runtime_lock_excludes_other_process_and_releases(tmp_path):
    database = tmp_path / "edge.sqlite3"
    application_root = Path(__file__).resolve().parents[1]
    script = """
import sys
sys.path.insert(0, sys.argv[2])
from nexus_edge.runtime_lock import EdgeRuntimeLock
try:
    lock = EdgeRuntimeLock(sys.argv[1]).acquire()
except RuntimeError:
    print("LOCKED")
else:
    print("ACQUIRED")
    lock.release()
"""
    parent = EdgeRuntimeLock(database).acquire()
    try:
        blocked = subprocess.run(
            [sys.executable, "-c", script, str(database), str(application_root)],
            capture_output=True, text=True, timeout=10, check=False,
        )
        assert blocked.returncode == 0
        assert "LOCKED" in blocked.stdout
    finally:
        parent.release()

    available = subprocess.run(
        [sys.executable, "-c", script, str(database), str(application_root)],
        capture_output=True, text=True, timeout=10, check=False,
    )
    assert available.returncode == 0
    assert "ACQUIRED" in available.stdout


def test_standalone_gateway_manager_lock_is_released_on_app_shutdown(tmp_path):
    env = _env(tmp_path)
    app = create_edge_app(
        provisioning_token=env["NEXUS_EDGE_PROVISIONING_TOKEN"], env=env
    )
    manager = app.state.edge_manager
    with pytest.raises(RuntimeError, match="already in use by another process"):
        create_edge_manager_from_env(env)

    with TestClient(app) as client:
        response = client.get("/v1/edge/health")
        assert response.status_code == 200

    replacement = create_edge_manager_from_env(env)
    replacement._runtime_lock.release()


def test_injected_gateway_manager_lock_remains_owned_by_caller_on_app_shutdown(tmp_path):
    env = _env(tmp_path)
    manager = create_edge_manager_from_env(env)
    app = create_edge_app(
        manager, provisioning_token=env["NEXUS_EDGE_PROVISIONING_TOKEN"], env=env
    )

    with TestClient(app) as client:
        response = client.get("/v1/edge/health")
        assert response.status_code == 200

    # The app was given a lifecycle-owned manager and must not release its lock.
    with pytest.raises(RuntimeError, match="already in use by another process"):
        create_edge_manager_from_env(env)

    manager._runtime_lock.release()
    replacement = create_edge_manager_from_env(env)
    replacement._runtime_lock.release()


def test_master_edge_service_adapter_owns_and_releases_runtime_lock(tmp_path, monkeypatch):
    from modules.nexus_runtime import EdgeServiceAdapter

    env = _env(tmp_path)
    monkeypatch.setenv("NEXUS_EDGE_DATABASE", env["NEXUS_EDGE_DATABASE"])
    monkeypatch.setenv("NEXUS_EDGE_STORAGE_KEY", env["NEXUS_EDGE_STORAGE_KEY"])

    first = EdgeServiceAdapter()
    first.initialize()
    second = EdgeServiceAdapter()
    with pytest.raises(RuntimeError, match="already in use by another process"):
        second.initialize()

    first.shutdown()
    second.initialize()
    second.shutdown()


def test_mqtt_runtime_releases_its_owned_manager_lock_on_stop(tmp_path, monkeypatch):
    from nexus_edge import transports

    env = _env(tmp_path)
    env.update({
        "NEXUS_EDGE_MQTT_ENABLED": "true",
        "NEXUS_EDGE_MQTT_HOST": "broker.example",
        "NEXUS_EDGE_MQTT_CLIENT_ID": "edge-lock-test",
    })
    monkeypatch.setattr(
        transports, "mqtt_config_from_env",
        lambda values: MQTTConfig(
            host="broker.example", client_id="edge-lock-test",
            username="nexus", password="test-password",
        ),
    )
    runtime = EdgeTransportRuntime(
        env=env,
        manager_factory=lambda: create_edge_manager_from_env(env),
        bridge_factory=FakeBridge,
    )
    runtime.start()
    with pytest.raises(RuntimeError, match="already in use by another process"):
        create_edge_manager_from_env(env)
    runtime.stop()
    replacement = create_edge_manager_from_env(env)
    replacement._runtime_lock.release()


def test_gateway_runtime_releases_owned_lock_when_mount_fails(tmp_path):
    env = _env(tmp_path)
    env["NEXUS_EDGE_GATEWAY_ENABLED"] = "true"
    runtime = EdgeGatewayRuntime(
        env=env,
        manager_factory=lambda: create_edge_manager_from_env(env),
        app_factory=lambda **kwargs: (_ for _ in ()).throw(RuntimeError("simulated mount failure")),
    )
    with pytest.raises(RuntimeError, match="simulated mount failure"):
        runtime.start(FastAPI())

    replacement = create_edge_manager_from_env(env)
    replacement._runtime_lock.release()


def test_key_rotation_refuses_to_run_while_edge_runtime_is_active(tmp_path):
    from nexus_edge.rotate_storage_key import main as rotate_key_main
    from nexus_edge.sqlite_store import SQLiteEdgeStore

    database = tmp_path / "edge.sqlite3"
    key = Fernet.generate_key()
    SQLiteEdgeStore(database, encryption_key=key)
    lock = EdgeRuntimeLock(database).acquire()
    try:
        with pytest.raises(SystemExit) as raised:
            rotate_key_main(["--database", str(database)])
        assert raised.value.code == 2
    finally:
        lock.release()


def test_create_edge_app_preserves_injected_manager_lock_when_validation_fails(tmp_path):
    env = _env(tmp_path)
    manager = create_edge_manager_from_env(env)
    manager.snapshot = lambda: (_ for _ in ()).throw(RuntimeError("snapshot failure"))

    with pytest.raises(RuntimeError, match="snapshot failure"):
        create_edge_app(
            manager, provisioning_token=env["NEXUS_EDGE_PROVISIONING_TOKEN"], env=env
        )

    with pytest.raises(RuntimeError, match="already in use by another process"):
        create_edge_manager_from_env(env)
    manager._runtime_lock.release()
