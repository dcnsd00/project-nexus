import sys
import time

from mining.hybrid_supervisor import HybridSupervisor


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
    assert status['cpu']['state'] == status['gpu']['state'] == 'running'
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


def test_stale_heartbeat_is_not_reported_as_running(tmp_path):
    import json
    sup = HybridSupervisor(runtime_root=tmp_path, heartbeat_timeout=1)
    sup.start({'cpu': {'command': _cmd()}}, mode='standard')
    deadline = time.time() + 5
    while time.time() < deadline and sup.status()['engines']['cpu']['state'] != 'running':
        time.sleep(.05)
    item = sup._workers['cpu']
    data = json.loads(item['status_path'].read_text())
    data['heartbeat_unix'] = time.time() - 30
    item['status_path'].write_text(json.dumps(data))
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


def test_read_only_status_reports_stale_without_stopping_worker(tmp_path):
    import json
    sup = HybridSupervisor(runtime_root=tmp_path, heartbeat_timeout=1)
    sup.start({'cpu': {'command': _cmd()}}, mode='standard')
    deadline = time.time() + 5
    while time.time() < deadline and sup.status()['engines']['cpu']['state'] != 'running':
        time.sleep(.05)
    item = sup._workers['cpu']
    data = json.loads(item['status_path'].read_text())
    data['heartbeat_unix'] = time.time() - 30
    item['status_path'].write_text(json.dumps(data))

    result = sup.status(read_only=True)['engines']['cpu']
    assert result['state'] == 'failed'
    assert result['last_error'] == 'stale_heartbeat'
    assert result['process_alive'] is True
    assert item['process'].poll() is None
    sup.stop_mode()
