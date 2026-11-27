import sys
import time
import os

from mining.hybrid_supervisor import HybridSupervisor
from mining.process_arbiter import process_is_alive


def _cmd():
    return [sys.executable, '-c', 'import time; time.sleep(30)']


def test_cpu_gpu_are_separate_and_independently_stoppable(tmp_path):
    sup = HybridSupervisor(runtime_root=tmp_path)
    result = sup.start({'cpu': {'command': _cmd()}, 'gpu': {'command': _cmd()}}, mode='standard')
    assert result['started'] is True
    deadline = time.time() + 5
    while time.time() < deadline and any(x['state'] != 'running' for x in sup.status()['engines'].values()):
        time.sleep(.05)
    status = sup.status()['engines']
    diagnostics = {
        engine: {
            "status": data,
            "worker_process_log": (
                (tmp_path / "standard" / engine / "worker-process.log").read_text(
                    encoding="utf-8", errors="replace"
                )[-4000:]
                if (tmp_path / "standard" / engine / "worker-process.log").exists()
                else None
            ),
            "miner_log": (
                (tmp_path / "standard" / engine / "worker.log").read_text(
                    encoding="utf-8", errors="replace"
                )[-4000:]
                if (tmp_path / "standard" / engine / "worker.log").exists()
                else None
            ),
        }
        for engine, data in status.items()
    }
    assert status['cpu']['state'] == status['gpu']['state'] == 'running', diagnostics
    cpu_pid = status['cpu']['pid']
    assert cpu_pid != status['gpu']['pid']
    sup.stop('gpu')
    status = sup.status()['engines']
    assert status['cpu']['state'] == 'running'
    assert status['cpu']['pid'] == cpu_pid
    assert status['gpu']['state'] == 'stopped'
    sup.stop()


def test_modes_are_exclusive_and_empty_backend_fails_truthfully(tmp_path):
    sup = HybridSupervisor(runtime_root=tmp_path)
    sup.start_mode('standard')
    assert sup.active_mode() == 'standard'
    result = sup.start({'cpu': {}}, mode='development')
    assert result['started'] is False
    assert sup.active_mode() == 'standard'
    sup.stop_mode()


def test_development_mode_does_not_reuse_standard_runtime(tmp_path):
    sup = HybridSupervisor(runtime_root=tmp_path)
    sup.start({'cpu': {'command': _cmd()}}, mode='standard')
    sup.stop_mode()
    sup.start({'cpu': {'executor': 'development_pow', 'network': 'regtest', 'algorithm': 'sha256d', 'attempts': 10000}}, mode='development')
    assert sup.status()['mode'] == 'development'
    assert (tmp_path / 'development' / 'cpu').exists()
    sup.stop_mode()


def test_development_mode_rejects_external_miner_command(tmp_path):
    sup = HybridSupervisor(runtime_root=tmp_path)
    result = sup.start({'cpu': {'command': _cmd()}}, mode='development')
    assert result['started'] is False
    assert 'development_pow' in result['errors']['cpu']
    sup.stop_mode()


def test_starting_same_mode_is_idempotent_and_does_not_orphan_workers(tmp_path):
    sup = HybridSupervisor(runtime_root=tmp_path)
    sup.start({'cpu': {'command': _cmd()}}, mode='standard')
    pid = sup.status()['engines']['cpu']['pid']
    sup.start_mode('standard')
    assert sup.status()['engines']['cpu']['pid'] == pid
    sup.stop_mode()


def test_gpu_switch_keeps_cpu_pid_and_rolls_back_failed_candidate(tmp_path):
    sup = HybridSupervisor(runtime_root=tmp_path)
    sup.start({'cpu': {'command': _cmd()}, 'gpu': {'command': _cmd()}}, mode='standard')
    deadline = time.time() + 5
    while time.time() < deadline and sup.status()['engines']['cpu']['state'] != 'running':
        time.sleep(.05)
    cpu_pid = sup.status()['engines']['cpu']['pid']
    result = sup.switch_gpu({'command': [sys.executable, '-c', 'raise SystemExit(7)'], 'miner_id': 'bad'})
    assert result['switched'] is False
    assert result['rolled_back'] is True
    assert result['cpu_pid_unchanged'] is True
    assert sup.status()['engines']['cpu']['pid'] == cpu_pid
    sup.stop_mode()


def test_stale_heartbeat_is_not_reported_as_running(tmp_path, monkeypatch):
    import mining.hybrid_supervisor as supervisor_module

    sup = HybridSupervisor(runtime_root=tmp_path, heartbeat_timeout=1)
    sup.start({'cpu': {'command': _cmd()}}, mode='standard')
    deadline = time.time() + 5
    while time.time() < deadline and sup.status()['engines']['cpu']['state'] != 'running':
        time.sleep(.05)

    # Advance only the supervisor's clock. The worker runs in a separate
    # process, so this deterministically simulates an expired heartbeat
    # without racing its periodic status-file writes.
    import json
    item = sup._workers['cpu']
    worker_status = json.loads(item['status_path'].read_text(encoding='utf-8'))
    assert worker_status.get('worker_instance_id') == item['worker_instance_id']
    assert process_is_alive(worker_status.get('pid'))
    if os.name != 'nt':
        assert worker_status.get('pid') == item['process'].pid
    observed_now = time.time()
    with monkeypatch.context() as patch:
        patch.setattr(supervisor_module.time, 'time', lambda: observed_now + 30)
        stale = sup.status()['engines']['cpu']
    assert stale['state'] == 'failed'
    assert stale['last_error'] == 'stale_heartbeat'
    assert stale['process_alive'] is False
    sup.stop_mode()


def test_restart_policy_is_disabled_by_default_and_bounded_when_opted_in(tmp_path):
    sup = HybridSupervisor(runtime_root=tmp_path)
    result = sup.start({'cpu': {'command': [sys.executable, '-c', 'raise SystemExit(3)']}}, mode='standard')
    assert result['restart_policy']['enabled'] is False
    sup.stop_mode()

    sup = HybridSupervisor(runtime_root=tmp_path / 'bounded')
    sup.start({'cpu': {'command': [sys.executable, '-c', 'raise SystemExit(3)']}}, mode='standard',
              restart_policy={'enabled': True, 'max_restarts': 2})
    deadline = time.time() + 12
    last = None
    while time.time() < deadline:
        last = sup.status()['engines']['cpu']
        if last.get('restart_count') == 2 and last['state'] == 'failed':
            break
        time.sleep(.1)
    assert last['restart_count'] == 2
    assert last['state'] == 'failed'
    sup.stop_mode()


def test_stop_reaps_miner_child_if_worker_process_crashes(tmp_path):
    import os
    import pytest
    if os.name == 'nt':
        pytest.skip('POSIX process-group assertion')
    sup = HybridSupervisor(runtime_root=tmp_path)
    sup.start({'cpu': {'command': _cmd()}}, mode='standard')
    deadline = time.time() + 5
    while time.time() < deadline and sup.status()['engines']['cpu']['state'] != 'running':
        time.sleep(.05)
    item = sup._workers['cpu']
    data = __import__('json').loads(item['status_path'].read_text())
    child_pid = data['miner_pid']
    item['process'].kill()
    item['process'].wait(timeout=2)
    result = sup.stop('cpu')
    assert result['engines']['cpu'] == 'stopped'
    deadline = time.time() + 3
    while time.time() < deadline:
        try:
            os.kill(child_pid, 0)
        except ProcessLookupError:
            break
        time.sleep(.05)
    else:
        pytest.fail('miner child survived worker crash')
    sup.stop_mode()


def test_mode_reports_degraded_when_one_lane_fails_and_other_runs(tmp_path):
    sup = HybridSupervisor(runtime_root=tmp_path)
    sup.start({'cpu': {'command': _cmd()}, 'gpu': {}}, mode='standard')
    deadline = time.time() + 5
    while time.time() < deadline:
        status = sup.status()
        if status['engines']['cpu']['state'] == 'running' and status['engines']['gpu']['state'] == 'failed':
            break
        time.sleep(.05)
    assert status['mode_state'] == 'degraded'
    sup.stop_mode()


def test_read_only_status_reports_stale_without_stopping_worker(tmp_path, monkeypatch):
    import mining.hybrid_supervisor as supervisor_module

    sup = HybridSupervisor(runtime_root=tmp_path, heartbeat_timeout=1)
    sup.start({'cpu': {'command': _cmd()}}, mode='standard')
    deadline = time.time() + 5
    while time.time() < deadline and sup.status()['engines']['cpu']['state'] != 'running':
        time.sleep(.05)
    item = sup._workers['cpu']
    import json
    worker_status = json.loads(item['status_path'].read_text(encoding='utf-8'))
    assert worker_status.get('worker_instance_id') == item['worker_instance_id']
    assert process_is_alive(worker_status.get('pid'))
    if os.name != 'nt':
        assert worker_status.get('pid') == item['process'].pid

    observed_now = time.time()
    with monkeypatch.context() as patch:
        patch.setattr(supervisor_module.time, 'time', lambda: observed_now + 30)
        result = sup.status(read_only=True)['engines']['cpu']
    assert result['state'] == 'failed'
    assert result['last_error'] == 'stale_heartbeat'
    assert result['process_alive'] is True
    assert item['process'].poll() is None
    sup.stop_mode()


def test_switch_engine_replaces_configuration_and_preserves_worker_health(tmp_path):
    sup = HybridSupervisor(runtime_root=tmp_path)
    sup.start({'cpu': {'command': _cmd(), 'coin': 'COIN-A', 'algorithm': 'Algo-A'}}, mode='standard')
    deadline = time.time() + 5
    while time.time() < deadline and sup.status()['engines']['cpu']['state'] != 'running':
        time.sleep(.05)

    result = sup.switch_engine('cpu', {'command': _cmd(), 'coin': 'COIN-B', 'algorithm': 'Algo-B'})
    assert result['switched'] is True
    assert result['coin'] == 'COIN-B'
    assert sup._workers['cpu']['request']['coin'] == 'COIN-B'
    assert sup.status()['engines']['cpu']['state'] == 'running'
    sup.stop_mode()


def test_switch_engine_rejects_missing_candidate_backend_without_stopping_current(tmp_path):
    sup = HybridSupervisor(runtime_root=tmp_path)
    sup.start({'cpu': {'command': _cmd(), 'coin': 'COIN-A'}}, mode='standard')
    deadline = time.time() + 5
    while time.time() < deadline and sup.status()['engines']['cpu']['state'] != 'running':
        time.sleep(.05)

    result = sup.switch_engine('cpu', {'coin': 'COIN-B'})
    assert result['switched'] is False
    assert result['error'] == 'candidate_worker_command_missing'
    assert sup.status()['engines']['cpu']['state'] == 'running'
    assert sup._workers['cpu']['request']['coin'] == 'COIN-A'
    sup.stop_mode()


def test_worker_request_is_owner_private_and_removed_after_worker_start(tmp_path):
    import json
    import os
    import pytest
    from mining.hybrid_supervisor import _write_private_request

    request_path = tmp_path / "private" / "request.json"
    payload = {"command": _cmd(), "pool_password": "POOL_SECRET_SENTINEL"}
    _write_private_request(request_path, payload)
    assert json.loads(request_path.read_text(encoding="utf-8")) == payload
    if os.name != "nt":
        assert request_path.stat().st_mode & 0o777 == 0o600

    sup = HybridSupervisor(runtime_root=tmp_path / "runtime")
    result = sup.start({"cpu": payload}, mode="standard")
    assert result["started"] is True
    request = sup._workers["cpu"]["request_path"]
    deadline = time.time() + 5
    while time.time() < deadline and request.exists():
        time.sleep(0.05)
    assert not request.exists()
    sup.stop_mode()
