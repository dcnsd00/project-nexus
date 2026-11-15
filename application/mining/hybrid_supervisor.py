"""Exclusive-mode supervisor for isolated CPU and GPU mining workers."""
from __future__ import annotations

import json
import subprocess
import sys
import signal
import os
import threading
import time
from pathlib import Path
from typing import Any

from modules.data_paths import data_path


_VALID_MODES = {'standard', 'development'}
_VALID_ENGINES = {'cpu', 'gpu'}


class HybridSupervisor:
    def __init__(self, runtime_root: str | Path | None = None, heartbeat_timeout: float = 5.0):
        self.runtime_root = Path(runtime_root).expanduser().resolve() if runtime_root else data_path('mining', 'hybrid').resolve()
        self.heartbeat_timeout = max(1.0, float(heartbeat_timeout))
        self._lock = threading.RLock()
        self._mode: str | None = None
        self._mode_state = 'stopped'
        self._workers: dict[str, dict[str, Any]] = {}
        self._restart_policy = {'enabled': False, 'max_restarts': 0}

    def active_mode(self) -> str | None:
        with self._lock:
            return self._mode

    def start_mode(self, mode: str) -> dict:
        mode = str(mode).lower()
        if mode not in _VALID_MODES:
            raise ValueError('mode must be standard or development')
        with self._lock:
            if self._mode and self._mode != mode:
                live = [k for k, v in self._workers.items() if v['process'].poll() is None]
                return {'started': False, 'error': 'mode_conflict', 'active_mode': self._mode, 'live_engines': live}
            if self._mode == mode:
                return {'started': True, 'mode': mode, 'already_active': True, 'status': self.status()}
            self._mode = mode
            self._mode_state = 'running'
            self._workers = {}
            self._restart_policy = {'enabled': False, 'max_restarts': 0}
            return {'started': True, 'mode': mode, 'engines': {e: {'state': 'stopped'} for e in _VALID_ENGINES}}

    def start(self, plan: dict, mode: str = 'standard', restart_policy: dict | None = None) -> dict:
        with self._lock:
            if self._mode is None:
                result = self.start_mode(mode)
                if not result.get('started'):
                    return result
            elif self._mode != mode:
                return {'started': False, 'error': 'mode_conflict', 'active_mode': self._mode}
            if restart_policy is None:
                self._restart_policy = {'enabled': False, 'max_restarts': 0}
            if restart_policy and restart_policy.get('enabled'):
                maximum = int(restart_policy.get('max_restarts', 0))
                if maximum < 1 or maximum > 5:
                    raise ValueError('max_restarts must be between 1 and 5')
                self._restart_policy = {'enabled': True, 'max_restarts': maximum}
            started, errors = [], {}
            for engine in ('cpu', 'gpu'):
                request = plan.get(engine)
                if request is None:
                    continue
                if engine in self._workers and self._workers[engine]['process'].poll() is None:
                    errors[engine] = 'already_running'
                    continue
                try:
                    self._launch(engine, request)
                    started.append(engine)
                except Exception as exc:
                    errors[engine] = f'{type(exc).__name__}: {exc}'
            return {'started': bool(started), 'mode': self._mode, 'started_engines': started, 'errors': errors,
                    'restart_policy': dict(self._restart_policy)}

    def _launch(self, engine: str, request: dict, restart_count: int = 0) -> None:
        if engine not in _VALID_ENGINES:
            raise ValueError('engine must be cpu or gpu')
        if not isinstance(request, dict):
            raise ValueError(f'{engine} request must be an object')
        mode = self._mode
        runtime = self.runtime_root / str(mode) / engine
        runtime.mkdir(parents=True, exist_ok=True)
        status_path, stop_path = runtime / 'status.json', runtime / 'stop'
        for stale_path in (stop_path, status_path):
            try:
                stale_path.unlink()
            except FileNotFoundError:
                pass
        req = dict(request)
        req.setdefault('log_path', str(runtime / 'worker.log'))
        if mode == 'development' and (req.get('executor') != 'development_pow' or 'command' in req):
            raise ValueError('development mode accepts only the isolated development_pow executor')
        request_path = runtime / 'request.json'
        request_path.write_text(json.dumps(req, ensure_ascii=False), encoding='utf-8')
        worker_log = (runtime / 'worker-process.log').open('ab')
        project_root = Path(__file__).resolve().parents[1]
        process = subprocess.Popen([sys.executable, '-m', 'mining.hybrid_worker', '--engine', engine,
                                    '--request', str(request_path), '--status', str(status_path),
                                    '--stop', str(stop_path)], cwd=str(project_root), stdin=subprocess.DEVNULL,
                                   stdout=worker_log, stderr=subprocess.STDOUT, shell=False,
                                   start_new_session=(os.name != 'nt'),
                                   creationflags=(subprocess.CREATE_NEW_PROCESS_GROUP if os.name == 'nt' else 0))
        worker_log.close()
        self._workers[engine] = {'process': process, 'status_path': status_path, 'stop_path': stop_path,
                                 'request': req, 'runtime': runtime, 'started_at': time.time(), 'restart_count': restart_count}

    def stop(self, engine: str | None = None) -> dict:
        with self._lock:
            targets = [engine] if engine else list(self._workers)
            if any(x not in _VALID_ENGINES for x in targets):
                raise ValueError('engine must be cpu or gpu')
            results = {}
            for name in targets:
                item = self._workers.get(name)
                if not item:
                    results[name] = 'stopped'
                    continue
                item['stop_path'].parent.mkdir(parents=True, exist_ok=True)
                item['stop_path'].write_text('stop', encoding='utf-8')
                proc = item['process']
                if proc.poll() is not None:
                    try:
                        worker_status = json.loads(item['status_path'].read_text(encoding='utf-8'))
                    except Exception:
                        worker_status = {}
                    if worker_status.get('state') in ('starting', 'running'):
                        child_pid = worker_status.get('miner_pid')
                        if os.name == 'nt' and child_pid:
                            subprocess.run(['taskkill', '/PID', str(child_pid), '/T', '/F'], capture_output=True, timeout=3)
                        elif os.name != 'nt':
                            try: os.killpg(proc.pid, signal.SIGTERM)
                            except ProcessLookupError: pass
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    if os.name == 'nt':
                        subprocess.run(['taskkill', '/PID', str(proc.pid), '/T', '/F'], capture_output=True, timeout=3)
                    else:
                        try: os.killpg(proc.pid, signal.SIGTERM)
                        except ProcessLookupError: pass
                    try: proc.wait(timeout=2)
                    except subprocess.TimeoutExpired:
                        if os.name == 'nt': proc.kill()
                        else:
                            try: os.killpg(proc.pid, signal.SIGKILL)
                            except ProcessLookupError: pass
                        try: proc.wait(timeout=2)
                        except subprocess.TimeoutExpired: pass
                results[name] = 'stopped' if proc.poll() is not None else 'unconfirmed_shutdown'
            if engine is None and all(v == 'stopped' for v in results.values()):
                self._mode = None
                self._mode_state = 'stopped'
                self._workers = {}
            return {'stopped': all(v == 'stopped' for v in results.values()), 'engines': results,
                    'active_mode': self._mode}

    def stop_mode(self, mode: str | None = None) -> dict:
        if mode is not None and mode not in _VALID_MODES:
            raise ValueError('mode must be standard or development')
        with self._lock:
            if mode is not None and self._mode not in (None, mode):
                return {'stopped': False, 'error': 'mode_mismatch', 'active_mode': self._mode}
            return self.stop()

    def switch_engine(self, engine: str, request: dict, startup_timeout: float = 8.0) -> dict:
        """Replace one worker configuration, restoring the previous worker on failure."""
        if engine not in _VALID_ENGINES:
            raise ValueError('engine must be cpu or gpu')
        if not isinstance(request, dict) or not isinstance(request.get('command'), list) or not request['command']:
            return {'switched': False, 'error': 'candidate_worker_command_missing'}
        with self._lock:
            if self._mode != 'standard':
                return {'switched': False, 'error': 'standard_mode_required'}
            previous = self._workers.get(engine, {}).get('request')
            if previous is None:
                return {'switched': False, 'error': 'no_active_worker_to_replace'}
            self.stop(engine)
            try:
                self._launch(engine, request)
                deadline = time.time() + max(2.0, min(float(startup_timeout), 30.0))
                while time.time() < deadline:
                    state = self.status(read_only=True)['engines'][engine]['state']
                    if state == 'running':
                        return {'switched': True, 'engine': engine,
                                'coin': request.get('coin'), 'algorithm': request.get('algorithm'),
                                'rolled_back': False}
                    if state == 'failed':
                        break
                    time.sleep(.1)
                self.stop(engine)
                raise RuntimeError('candidate_worker_failed_startup')
            except Exception as exc:
                rolled_back = False
                try:
                    self._launch(engine, previous)
                    rollback_deadline = time.time() + max(2.0, min(float(startup_timeout), 30.0))
                    while time.time() < rollback_deadline:
                        state = self.status(read_only=True)['engines'][engine]['state']
                        if state == 'running':
                            rolled_back = True
                            break
                        if state == 'failed':
                            break
                        time.sleep(.1)
                except Exception:
                    rolled_back = False
                return {'switched': False, 'engine': engine,
                        'error': f'{type(exc).__name__}: {exc}', 'rolled_back': rolled_back}

    def switch_gpu(self, request: dict) -> dict:
        with self._lock:
            if self._mode is None:
                return {'switched': False, 'error': 'no_active_mode'}
            if self._mode == 'development':
                return {'switched': False, 'error': 'development_gpu_backend_unavailable'}
            if not isinstance(request.get('command'), list) or not request['command']:
                return {'switched': False, 'error': 'backend_unavailable'}
            previous = self._workers.get('gpu', {}).get('request')
            cpu_pid = self._workers.get('cpu', {}).get('process').pid if self._workers.get('cpu') else None
            self.stop('gpu')
            try:
                self._launch('gpu', request)
                deadline = time.time() + 4
                running_since = None
                while time.time() < deadline:
                    state = self.status()['engines']['gpu']['state']
                    if state == 'running':
                        running_since = running_since or time.time()
                        if time.time() - running_since >= 1.5:
                            current_cpu = self._workers.get('cpu', {}).get('process').pid if self._workers.get('cpu') else None
                            return {'switched': True, 'mode': self._mode, 'cpu_pid_unchanged': current_cpu == cpu_pid,
                                    'gpu_state': 'running'}
                    else:
                        running_since = None
                    if state == 'failed':
                        break
                    time.sleep(.05)
                self.stop('gpu')
                raise RuntimeError('candidate_gpu_worker_failed_to_start')
            except Exception as exc:
                rolled_back = False
                if previous and isinstance(previous.get('command'), list) and previous['command']:
                    try:
                        self._launch('gpu', previous)
                        rollback_deadline = time.time() + 4
                        while time.time() < rollback_deadline:
                            rollback_state = self.status()['engines']['gpu']['state']
                            if rollback_state == 'running':
                                rolled_back = True
                                break
                            if rollback_state == 'failed':
                                break
                            time.sleep(.05)
                    except Exception:
                        pass
                return {'switched': False, 'error': f'{type(exc).__name__}: {exc}', 'rolled_back': rolled_back,
                        'cpu_pid_unchanged': (self._workers.get('cpu', {}).get('process').pid if self._workers.get('cpu') else None) == cpu_pid}

    def status(self, read_only: bool = False) -> dict:
        """Return supervisor state; read_only disables restart and stale-worker termination."""
        with self._lock:
            engines = {}
            for engine in ('cpu', 'gpu'):
                item = self._workers.get(engine)
                if not item:
                    engines[engine] = {'state': 'stopped', 'pid': None}
                    continue
                proc = item['process']
                try:
                    data = json.loads(item['status_path'].read_text(encoding='utf-8'))
                except Exception:
                    data = {}
                if (not read_only and proc.poll() is not None and data.get('state') in ('failed', 'running', 'starting') and self._restart_policy.get('enabled')
                        and item.get('restart_count', 0) < self._restart_policy.get('max_restarts', 0)):
                    next_count = item.get('restart_count', 0) + 1
                    self._launch(engine, item['request'], restart_count=next_count)
                    item = self._workers[engine]
                    proc = item['process']
                    data = {}
                heartbeat = data.get('heartbeat_unix')
                worker_pid_matches = data.get('pid') == proc.pid
                stale = bool(proc.poll() is None and worker_pid_matches and (not isinstance(heartbeat, (int, float)) or time.time() - heartbeat > self.heartbeat_timeout))
                state = data.get('state', 'starting')
                if proc.poll() is not None and state in ('starting', 'running'):
                    state = 'failed'
                elif stale:
                    if not read_only:
                        self.stop(engine)
                        item = self._workers.get(engine, item)
                        proc = item['process']
                    state = 'failed'
                    data['last_error'] = 'stale_heartbeat'
                engines[engine] = {**data, 'state': state, 'pid': proc.pid,
                                   'process_alive': proc.poll() is None, 'exit_code': proc.poll(),
                                   'runtime_dir': str(item['runtime']), 'restart_count': item.get('restart_count', 0)}
            states = [x['state'] for x in engines.values()]
            if not self._mode:
                mode_state = 'stopped'
            elif 'failed' in states and 'running' in states:
                mode_state = 'degraded'
            elif 'failed' in states:
                mode_state = 'failed'
            elif 'running' in states:
                mode_state = 'running'
            else:
                mode_state = 'degraded'
            return {'mode': self._mode, 'mode_state': mode_state, 'engines': engines,
                    'restart_policy': dict(self._restart_policy)}
