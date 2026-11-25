import json
import sys
import time
from pathlib import Path

from mining.hybrid_worker import run_worker
import mining.hybrid_worker as hybrid_worker


def test_worker_launches_owned_child_and_stops_it(tmp_path):
    import threading
    status = tmp_path / 'cpu' / 'status.json'
    stop = tmp_path / 'cpu' / 'stop'
    request = {'command': [sys.executable, '-c', 'import time; time.sleep(30)'],
               'miner_id': 'test-miner', 'algorithm': 'test'}
    result = []
    thread = threading.Thread(target=lambda: result.append(run_worker('cpu', request, str(status), str(stop))))
    thread.start()
    deadline = time.time() + 5
    while time.time() < deadline:
        if status.exists() and json.loads(status.read_text()).get('state') == 'running':
            break
        time.sleep(.05)
    assert json.loads(status.read_text())['state'] == 'running'
    running = json.loads(status.read_text())
    assert running['pool_connected'] is None
    assert running['authorized'] is None
    stop.parent.mkdir(parents=True, exist_ok=True)
    stop.write_text('stop')
    thread.join(5)
    assert not thread.is_alive()
    stopped = json.loads(status.read_text())
    assert stopped['state'] == 'stopped'
    # POSIX terminate() reports -SIGTERM; Windows TerminateProcess commonly
    # reports 1. The worker preserves that native child code for diagnostics.
    assert result == [stopped['child_exit_code']]
    assert stopped['last_error'] is None


def test_worker_reports_backend_unavailable_without_command(tmp_path):
    status = tmp_path / 'gpu' / 'status.json'
    rc = run_worker('gpu', {}, str(status), str(tmp_path / 'gpu' / 'stop'))
    result = json.loads(status.read_text())
    assert rc != 0
    assert result['state'] == 'failed'
    assert result['last_error'] == 'backend_unavailable'


def test_worker_propagates_child_exit_code_and_uses_isolated_log(tmp_path):
    status = tmp_path / 'gpu' / 'status.json'
    log = tmp_path / 'gpu' / 'miner.log'
    rc = run_worker('gpu', {'command': [sys.executable, '-c', 'raise SystemExit(9)'],
                            'log_path': str(log)}, str(status), str(tmp_path / 'gpu' / 'stop'))
    assert rc == 9
    data = json.loads(status.read_text())
    assert data['state'] == 'failed'
    assert data['child_exit_code'] == 9
    assert log.exists()



def test_worker_status_write_retries_transient_permission_error(tmp_path, monkeypatch):
    status = tmp_path / "gpu" / "status.json"
    real_replace = hybrid_worker.os.replace
    attempts = {"count": 0}

    def flaky_replace(source, destination):
        attempts["count"] += 1
        if attempts["count"] <= 2:
            raise PermissionError("simulated transient Windows sharing violation")
        return real_replace(source, destination)

    monkeypatch.setattr(hybrid_worker.os, "replace", flaky_replace)
    hybrid_worker._write_status(status, {"state": "running", "pid": 123})
    assert attempts["count"] == 3
    assert json.loads(status.read_text(encoding="utf-8")) == {
        "state": "running",
        "pid": 123,
    }
    assert not status.with_suffix(".json." + str(__import__("os").getpid()) + ".tmp").exists()


def test_write_status_retries_transient_replace_permission_error(tmp_path, monkeypatch):
    import mining.hybrid_worker as hybrid_worker

    status = tmp_path / "cpu" / "status.json"
    real_replace = hybrid_worker.os.replace
    attempts = 0

    def flaky_replace(source, destination):
        nonlocal attempts
        attempts += 1
        if attempts <= 2:
            raise PermissionError(5, "Access is denied")
        return real_replace(source, destination)

    monkeypatch.setattr(hybrid_worker.os, "replace", flaky_replace)
    payload = {"engine": "cpu", "state": "running", "heartbeat_unix": 123.0}
    hybrid_worker._write_status(status, payload)

    assert json.loads(status.read_text(encoding="utf-8")) == payload
    assert attempts == 3
    temp_path = status.with_suffix(status.suffix + f".{hybrid_worker.os.getpid()}.tmp")
    assert not temp_path.exists()
