"""Isolated OS-process worker for one NEXUS mining lane."""
from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path
from typing import Any


def _write_status(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(payload, ensure_ascii=False), encoding='utf-8')
    os.replace(tmp, path)


def run_worker(engine: str, request: dict, status_path: str, stop_event_path: str) -> int:
    """Launch and own exactly one child miner; return its exit code."""
    status_file, stop_file = Path(status_path), Path(stop_event_path)
    payload = {
        'engine': engine, 'pid': os.getpid(), 'state': 'starting',
        'heartbeat_unix': time.time(), 'miner_id': request.get('miner_id'),
        'algorithm': request.get('algorithm'), 'hashrate_hs': None,
        'accepted_shares': None, 'rejected_shares': None,
        'last_error': None, 'pool_connected': None, 'authorized': None,
    }
    _write_status(status_file, payload)
    command = request.get('command')
    if not isinstance(command, list) or not command or not all(isinstance(x, str) for x in command):
        payload.update(state='failed', last_error='backend_unavailable', heartbeat_unix=time.time())
        _write_status(status_file, payload)
        return 2
    child = None
    try:
        log_path = Path(request.get('log_path') or status_file.with_name('worker.log'))
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open('ab') as log:
            child = subprocess.Popen(command, cwd=request.get('cwd'), stdout=log, stderr=subprocess.STDOUT,
                                     shell=False, creationflags=(subprocess.CREATE_NEW_PROCESS_GROUP if os.name == 'nt' else 0),
                                     start_new_session=False)
            payload.update(state='running', miner_pid=child.pid, heartbeat_unix=time.time())
            _write_status(status_file, payload)
            while child.poll() is None:
                if stop_file.exists():
                    try:
                        child.terminate()
                        child.wait(timeout=float(request.get('stop_timeout', 3)))
                    except subprocess.TimeoutExpired:
                        child.kill()
                        child.wait(timeout=2)
                    break
                payload['heartbeat_unix'] = time.time()
                _write_status(status_file, payload)
                time.sleep(max(.1, min(float(request.get('heartbeat_interval', .5)), 2.0)))
            rc = child.wait()
        payload.update(state='stopped' if stop_file.exists() else ('failed' if rc else 'stopped'),
                       heartbeat_unix=time.time(), child_exit_code=rc)
        if rc and not stop_file.exists():
            payload['last_error'] = f'miner_exit_{rc}'
        _write_status(status_file, payload)
        return rc
    except Exception as exc:
        if child is not None and child.poll() is None:
            try:
                child.terminate()
                child.wait(timeout=2)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait(timeout=2)
        payload.update(state='failed', last_error=f'{type(exc).__name__}: {exc}', heartbeat_unix=time.time())
        _write_status(status_file, payload)
        return 1


def main(argv=None) -> int:
    import argparse
    parser = argparse.ArgumentParser(description='NEXUS isolated hybrid worker')
    parser.add_argument('--engine', required=True, choices=('cpu', 'gpu'))
    parser.add_argument('--request', required=True)
    parser.add_argument('--status', required=True)
    parser.add_argument('--stop', required=True)
    args = parser.parse_args(argv)
    request = json.loads(Path(args.request).read_text(encoding='utf-8'))
    if request.get('executor') == 'development_pow':
        from mining.development_pow import run_development_worker
        return run_development_worker(args.engine, request, args.status, args.stop)
    return run_worker(args.engine, request, args.status, args.stop)


if __name__ == '__main__':
    raise SystemExit(main())
