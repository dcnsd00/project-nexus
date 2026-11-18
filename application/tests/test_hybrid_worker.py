import json
import sys
import time
from pathlib import Path

from mining.hybrid_worker import run_worker


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
