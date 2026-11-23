import multiprocessing
import os
import sys
import time

import pytest

from mining.process_arbiter import MiningProcessArbiter


def _try_acquire_in_child(path, result_queue):
    arbiter = MiningProcessArbiter(path)
    acquired = arbiter.acquire("child-process")
    result_queue.put(acquired)
    if acquired:
        arbiter.release("child-process")


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
    context = multiprocessing.get_context("spawn")
    result_queue = context.Queue()
    child = context.Process(target=_try_acquire_in_child, args=(path, result_queue))
    child.start()
    try:
        assert result_queue.get(timeout=10) is False
    finally:
        child.join(timeout=10)
        if child.is_alive():
            child.terminate()
            child.join(timeout=5)
        arbiter.release("parent-process")
    assert child.exitcode == 0


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
    started = supervisor.start(
        {"cpu": {"command": [sys.executable, "-c", "import time; time.sleep(30)"]}},
        mode="standard",
    )
    assert started["started"] is True

    with monkeypatch.context() as patch:
        patch.setattr(direct.subprocess, "Popen", _FakeMinerProcess)
        with pytest.raises(ValueError, match="altă sesiune de minare NEXUS"):
            direct.start(_fake_controller_request())

    deadline = time.time() + 5
    while time.time() < deadline and supervisor.status()["engines"]["cpu"]["state"] != "running":
        time.sleep(0.05)
    assert supervisor.status()["engines"]["cpu"]["state"] == "running"
    supervisor.stop_mode()
    assert arbiter.held is False

    # Reverse direction: the direct controller owns the host first, and
    # HybridSupervisor must refuse to launch a second independent worker.
    monkeypatch.setattr(direct, "_proc", None)
    direct_supervisor = hybrid_module.HybridSupervisor(runtime_root=tmp_path / "direct-first")
    with monkeypatch.context() as patch:
        patch.setattr(direct.subprocess, "Popen", _FakeMinerProcess)
        result = direct.start(_fake_controller_request())
    assert result["status"] == "running"

    blocked = direct_supervisor.start(
        {"cpu": {"command": [sys.executable, "-c", "import time; time.sleep(30)"]}},
        mode="standard",
    )
    assert blocked["started"] is False
    assert blocked["error"] == "mining_runtime_busy"
    assert direct_supervisor.status()["engines"]["cpu"]["state"] == "stopped"

    direct.stop()
    direct_supervisor.stop_mode()
    assert arbiter.held is False
