import json
import os
import subprocess
import sys
import time

import pytest

from mining.process_arbiter import MiningProcessArbiter, process_is_alive
import mining.process_arbiter as process_arbiter_module


_CHILD_ACQUIRE_SCRIPT = r"""
import sys
from mining.process_arbiter import MiningProcessArbiter
arbiter = MiningProcessArbiter(sys.argv[1])
acquired = arbiter.acquire("child-process")
print("ACQUIRED" if acquired else "BUSY", flush=True)
if acquired:
    arbiter.release("child-process")
"""


def _fake_controller_request():
    return {
        "miner_id": "srbminer",
        "pool_id": "2miners-rvn-eu",
        "wallet": "RWalletExample123",
        "worker": "arbiter-test",
        "algorithm": "KawPoW",
        "device": "GPU",
        "use_ssl": False,
        "custom_host": None,
        "custom_port": None,
        "binary_path": None,
    }


class _FakeMinerProcess:
    def __init__(self, *args, **kwargs):
        self.args = args[0]
        self.kwargs = kwargs
        self.returncode = None
        self.pid = 987654

    def poll(self):
        return self.returncode

    def terminate(self):
        self.returncode = 0

    def wait(self, timeout=None):
        return self.returncode

    def kill(self):
        self.returncode = -9


def test_arbiter_excludes_a_second_owner_and_releases_cleanly(tmp_path):
    arbiter = MiningProcessArbiter(tmp_path / "mining.lock")
    assert arbiter.acquire("direct-controller") is True
    assert arbiter.acquire("hybrid-supervisor") is False
    assert arbiter.owner == "direct-controller"
    assert arbiter.release("direct-controller") is True
    assert arbiter.acquire("hybrid-supervisor") is True
    assert arbiter.release("hybrid-supervisor") is True


def test_os_lock_is_exclusive_across_processes(tmp_path):
    path = str(tmp_path / "mining.lock")
    arbiter = MiningProcessArbiter(path)
    assert arbiter.acquire("parent-process") is True
    try:
        child = subprocess.run(
            [sys.executable, "-c", _CHILD_ACQUIRE_SCRIPT, path],
            capture_output=True, text=True, timeout=10,
            creationflags=(subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0),
        )
        assert child.returncode == 0, child.stderr
        assert child.stdout.strip() == "BUSY"
    finally:
        arbiter.release("parent-process")

    # Once the parent releases the lease, a different process can own it.
    child = subprocess.run(
        [sys.executable, "-c", _CHILD_ACQUIRE_SCRIPT, path],
        capture_output=True, text=True, timeout=10,
            creationflags=(subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0),
    )
    assert child.returncode == 0, child.stderr
    assert child.stdout.strip() == "ACQUIRED"


def test_arbiter_can_be_released_from_a_different_thread(tmp_path):
    import threading

    arbiter = MiningProcessArbiter(tmp_path / "thread-release.lock")
    assert arbiter.acquire("api-start-thread") is True
    results = []
    thread = threading.Thread(target=lambda: results.append(arbiter.release("api-start-thread")), daemon=True)
    thread.start()
    thread.join(timeout=5)
    assert not thread.is_alive()
    assert results == [True]
    assert arbiter.held is False


def test_stale_lock_metadata_blocks_while_orphan_pid_is_alive(tmp_path):
    path = tmp_path / "mining.lock"
    arbiter = MiningProcessArbiter(path)
    assert arbiter.acquire("simulated-crashed-owner") is True
    assert arbiter.update_processes("simulated-crashed-owner", [os.getpid()]) is True

    # Simulate the API process losing its lock handle without clearing the
    # persisted lease record. The current process PID stands in for an
    # orphaned miner child that is still running.
    handle = arbiter._file
    arbiter._unlock_os_file(handle)
    handle.close()
    arbiter._file = None
    arbiter._owner = None

    restarted = MiningProcessArbiter(path)
    assert restarted.acquire("new-runtime") is False


class _FakeHybridWorkerProcess:
    def __init__(self, pid=987655):
        self.pid = pid
        self.returncode = None

    def poll(self):
        return self.returncode

    def wait(self, timeout=None):
        self.returncode = 0
        return 0

    def kill(self):
        self.returncode = -9


def test_direct_controller_and_hybrid_supervisor_are_mutually_exclusive(tmp_path, monkeypatch):
    from mining import controller as direct
    from mining import hybrid_supervisor as hybrid_module

    arbiter = MiningProcessArbiter(tmp_path / "shared-mining.lock")
    monkeypatch.setattr(direct, "MINING_PROCESS_ARBITER", arbiter)
    monkeypatch.setattr(hybrid_module, "MINING_PROCESS_ARBITER", arbiter)
    monkeypatch.setattr(direct, "_proc", None)
    monkeypatch.setattr(direct, "_resolve_binary", lambda miner_id, explicit_path=None: "C:/fake/SRBMiner-MULTI.exe")
    monkeypatch.setattr(direct, "_metrics", lambda: {
        "api_connected": False, "hashrate_hs": None, "hashrate_display": None,
        "accepted_shares": None, "rejected_shares": None, "gpu": {}, "system": {}, "raw_api": None,
    })

    supervisor = hybrid_module.HybridSupervisor(runtime_root=tmp_path / "hybrid-first")
    fake_worker_pid = 987655
    fake_worker_instance_id = "fake-hybrid-worker-instance"
    fake_processes = {}

    def fake_process_is_alive(pid):
        if pid == fake_worker_pid:
            process = fake_processes.get("cpu")
            return process is not None and process.returncode is None
        return False

    monkeypatch.setattr(hybrid_module, "process_is_alive", fake_process_is_alive)

    def fake_hybrid_launch(engine, request, restart_count=0):
        runtime = tmp_path / "hybrid-first" / "standard" / engine
        runtime.mkdir(parents=True, exist_ok=True)
        status_path = runtime / "status.json"
        stop_path = runtime / "stop"
        status_path.write_text(json.dumps({
            "state": "running",
            "pid": fake_worker_pid,
            "worker_instance_id": fake_worker_instance_id,
            "heartbeat_unix": time.time(),
        }), encoding="utf-8")
        process = _FakeHybridWorkerProcess(pid=fake_worker_pid)
        fake_processes[engine] = process
        supervisor._workers[engine] = {
            "process": process, "status_path": status_path, "stop_path": stop_path,
            "request": dict(request), "runtime": runtime, "started_at": 1.0,
            "restart_count": restart_count, "worker_instance_id": fake_worker_instance_id,
        }
        supervisor._sync_arbiter(release_when_idle=False)

    monkeypatch.setattr(supervisor, "_launch", fake_hybrid_launch)
    started = supervisor.start({"cpu": {"command": ["fake-worker"]}}, mode="standard")
    assert started["started"] is True
    assert started["started_engines"] == ["cpu"]

    with monkeypatch.context() as patch:
        patch.setattr(direct.subprocess, "Popen", _FakeMinerProcess)
        with pytest.raises(ValueError, match="altă sesiune de minare NEXUS"):
            direct.start(_fake_controller_request())

    assert supervisor.status()["engines"]["cpu"]["state"] == "running"
    supervisor.stop_mode()
    assert arbiter.held is False

    # Reverse direction: the direct controller owns the host first, and
    # HybridSupervisor must refuse to launch a second independent worker.
    monkeypatch.setattr(direct, "_proc", None)
    direct_supervisor = hybrid_module.HybridSupervisor(runtime_root=tmp_path / "direct-first")
    launch_attempts = []
    monkeypatch.setattr(
        direct_supervisor, "_launch",
        lambda *args, **kwargs: launch_attempts.append(args) or (_ for _ in ()).throw(AssertionError("worker must not launch")),
    )
    with monkeypatch.context() as patch:
        patch.setattr(direct.subprocess, "Popen", _FakeMinerProcess)
        result = direct.start(_fake_controller_request())
    assert result["status"] == "running"

    blocked = direct_supervisor.start(
        {"cpu": {"command": ["fake-worker"]}},
        mode="standard",
    )
    assert blocked["started"] is False
    assert blocked["error"] == "mining_runtime_busy"
    assert direct_supervisor.status()["engines"]["cpu"]["state"] == "stopped"
    assert launch_attempts == []

    direct.stop()
    direct_supervisor.stop_mode()
    assert arbiter.held is False



def test_windows_process_liveness_uses_non_destructive_api(monkeypatch):
    calls = []

    def windows_probe(pid):
        calls.append(pid)
        return True

    def forbidden_kill(*args, **kwargs):
        raise AssertionError("os.kill must not be used for Windows liveness checks")

    with monkeypatch.context() as patch:
        patch.setattr(process_arbiter_module.os, "name", "nt")
        patch.setattr(process_arbiter_module, "_windows_process_is_alive", windows_probe)
        patch.setattr(process_arbiter_module.os, "kill", forbidden_kill)
        assert process_is_alive(43210) is True
        assert process_is_alive(0) is False
    assert calls == [43210]

class _FakeWinApiFunction:
    def __init__(self, result):
        self.result = result

    def __call__(self, *args):
        return self.result


def _fake_win_kernel32(open_result, exit_result=True):
    return type("FakeKernel32", (), {
        "OpenProcess": _FakeWinApiFunction(open_result),
        "GetExitCodeProcess": _FakeWinApiFunction(exit_result),
        "CloseHandle": _FakeWinApiFunction(True),
    })()


def test_windows_process_liveness_fails_closed_on_unknown_open_process_error(monkeypatch):
    import ctypes
    kernel32 = _fake_win_kernel32(None)
    monkeypatch.setattr(ctypes, "WinDLL", lambda *args, **kwargs: kernel32, raising=False)
    monkeypatch.setattr(ctypes, "get_last_error", lambda: 1234, raising=False)
    assert process_arbiter_module._windows_process_is_alive(1234) is True


def test_windows_process_liveness_treats_invalid_pid_as_not_alive(monkeypatch):
    import ctypes
    kernel32 = _fake_win_kernel32(None)
    monkeypatch.setattr(ctypes, "WinDLL", lambda *args, **kwargs: kernel32, raising=False)
    monkeypatch.setattr(ctypes, "get_last_error", lambda: 87, raising=False)
    assert process_arbiter_module._windows_process_is_alive(1234) is False


def test_windows_process_liveness_fails_closed_when_exit_code_query_fails(monkeypatch):
    import ctypes
    kernel32 = _fake_win_kernel32(1234, exit_result=False)
    monkeypatch.setattr(ctypes, "WinDLL", lambda *args, **kwargs: kernel32, raising=False)
    monkeypatch.setattr(ctypes, "get_last_error", lambda: 1234, raising=False)
    assert process_arbiter_module._windows_process_is_alive(1234) is True


def test_windows_process_liveness_fails_closed_on_winapi_exception(monkeypatch):
    import ctypes
    def unavailable(*args, **kwargs):
        raise OSError("simulated Windows API failure")
    monkeypatch.setattr(ctypes, "WinDLL", unavailable, raising=False)
    assert process_arbiter_module._windows_process_is_alive(1234) is True

