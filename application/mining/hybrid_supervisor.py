"""Exclusive-mode supervisor for isolated CPU and GPU mining workers."""
from __future__ import annotations

import json
import subprocess
import sys
import signal
import os
import threading
import time
import uuid
from pathlib import Path
from typing import Any

from modules.data_paths import data_path
from mining.process_arbiter import MINING_PROCESS_ARBITER, process_is_alive


_VALID_MODES = {'standard', 'development'}
_VALID_ENGINES = {'cpu', 'gpu'}


def _write_private_request(path: Path, request: dict) -> None:
    """Persist worker startup data with owner-only POSIX permissions."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        if os.name != "nt" and hasattr(os, "fchmod"):
            os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(request, handle, ensure_ascii=False)
            handle.flush()
    except Exception:
        try:
            os.close(fd)
        except OSError:
            pass
        try:
            path.unlink()
        except FileNotFoundError:
            pass
        raise


class HybridSupervisor:
    def __init__(self, runtime_root: str | Path | None = None, heartbeat_timeout: float = 5.0):
        self.runtime_root = Path(runtime_root).expanduser().resolve() if runtime_root else data_path('mining', 'hybrid').resolve()
        self.heartbeat_timeout = max(1.0, float(heartbeat_timeout))
        self._lock = threading.RLock()
        self._mode: str | None = None
        self._mode_state = 'stopped'
        self._workers: dict[str, dict[str, Any]] = {}
        self._restart_policy = {'enabled': False, 'max_restarts': 0}
        self._arbiter_owner = f'hybrid-supervisor:{os.getpid()}:{id(self)}'
        self._arbiter_acquired = False
        self._switching: set[str] = set()

    def _sync_arbiter(self, release_when_idle: bool = True) -> None:
        if not self._arbiter_acquired:
            return
        pids: set[int] = set()
        for item in self._workers.values():
            process = item.get('process')
            if process is not None and process.poll() is None:
                pids.add(int(process.pid))
            try:
                status_data = json.loads(item['status_path'].read_text(encoding='utf-8'))
            except (OSError, ValueError, TypeError):
                status_data = {}
            worker_pid = status_data.get('pid')
            if isinstance(worker_pid, int) and not isinstance(worker_pid, bool) and process_is_alive(worker_pid):
                pids.add(worker_pid)
            child_pid = status_data.get('miner_pid')
            if isinstance(child_pid, int) and not isinstance(child_pid, bool) and process_is_alive(child_pid):
                pids.add(child_pid)
        MINING_PROCESS_ARBITER.update_processes(self._arbiter_owner, pids)
        if release_when_idle and not pids and not self._switching:
            MINING_PROCESS_ARBITER.release(self._arbiter_owner)
            self._arbiter_acquired = False

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
            requested_engines = [engine for engine in ('cpu', 'gpu') if plan.get(engine) is not None]
            if requested_engines and not self._arbiter_acquired:
                if not MINING_PROCESS_ARBITER.acquire(self._arbiter_owner):
                    return {'started': False, 'error': 'mining_runtime_busy',
                            'message': 'O altă cale de minare NEXUS deține deja sesiunea acestui calculator.'}
                self._arbiter_acquired = True
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
            self._sync_arbiter(release_when_idle=not bool(started))
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
        worker_instance_id = uuid.uuid4().hex
        req['worker_instance_id'] = worker_instance_id
        if mode == 'development' and (req.get('executor') != 'development_pow' or 'command' in req):
            raise ValueError('development mode accepts only the isolated development_pow executor')
        request_path = runtime / 'request.json'
        _write_private_request(request_path, req)
        worker_log = (runtime / 'worker-process.log').open('ab')
        project_root = Path(__file__).resolve().parents[1]
        try:
            process = subprocess.Popen([sys.executable, '-m', 'mining.hybrid_worker', '--engine', engine,
                                        '--request', str(request_path), '--status', str(status_path),
                                        '--stop', str(stop_path)], cwd=str(project_root), stdin=subprocess.DEVNULL,
                                       stdout=worker_log, stderr=subprocess.STDOUT, shell=False,
                                       start_new_session=(os.name != 'nt'),
                                       creationflags=(subprocess.CREATE_NEW_PROCESS_GROUP if os.name == 'nt' else 0))
        except Exception:
            worker_log.close()
            try:
                request_path.unlink()
            except FileNotFoundError:
                pass
            raise
        worker_log.close()
        self._workers[engine] = {'process': process, 'status_path': status_path, 'stop_path': stop_path,
                                 'request': req, 'request_path': request_path, 'runtime': runtime,
                                 'started_at': time.time(), 'restart_count': restart_count,
                                 'worker_instance_id': worker_instance_id}
        self._sync_arbiter(release_when_idle=False)

    def stop(self, engine: str | None = None, *, release_lease: bool = True) -> dict:
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
                        worker_pid = worker_status.get('pid')
                        child_pid = worker_status.get('miner_pid')
                        if os.name == 'nt':
                            for target_pid in (worker_pid, child_pid):
                                if (isinstance(target_pid, int) and not isinstance(target_pid, bool)
                                        and target_pid > 0 and target_pid != proc.pid
                                        and process_is_alive(target_pid)):
                                    subprocess.run(['taskkill', '/PID', str(target_pid), '/T', '/F'],
                                                   capture_output=True, timeout=3)
                        else:
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
                if proc.poll() is not None:
                    try:
                        item.get('request_path', Path('')).unlink(missing_ok=True)
                    except OSError:
                        pass
            if engine is None and all(v == 'stopped' for v in results.values()):
                self._mode = None
                self._mode_state = 'stopped'
                self._workers = {}
            self._sync_arbiter(release_when_idle=release_lease)
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
            self._switching.add(engine)
            self.stop(engine, release_lease=False)
            try:
                self._launch(engine, request)
                deadline = time.time() + max(2.0, min(float(startup_timeout), 30.0))
                while time.time() < deadline:
                    state = self.status(read_only=True)['engines'][engine]['state']
                    if state == 'running':
                        self._switching.discard(engine)
                        self._sync_arbiter(release_when_idle=False)
                        return {'switched': True, 'engine': engine,
                                'coin': request.get('coin'), 'algorithm': request.get('algorithm'),
                                'rolled_back': False}
                    if state == 'failed':
                        break
                    time.sleep(.1)
                self.stop(engine, release_lease=False)
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
                self._switching.discard(engine)
                self._sync_arbiter(release_when_idle=True)
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
            self._switching.add('gpu')
            self.stop('gpu', release_lease=False)
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
                            self._switching.discard('gpu')
                            self._sync_arbiter(release_when_idle=False)
                            return {'switched': True, 'mode': self._mode, 'cpu_pid_unchanged': current_cpu == cpu_pid,
                                    'gpu_state': 'running'}
                    else:
                        running_since = None
                    if state == 'failed':
                        break
                    time.sleep(.05)
                self.stop('gpu', release_lease=False)
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
                self._switching.discard('gpu')
                self._sync_arbiter(release_when_idle=True)
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
                worker_pid = data.get('pid')
                worker_pid_valid = (
                    isinstance(worker_pid, int) and not isinstance(worker_pid, bool) and worker_pid > 0
                )
                worker_instance_matches = (
                    data.get('worker_instance_id') == item.get('worker_instance_id')
                )
                if os.name == 'nt' and worker_pid_valid and worker_instance_matches:
                    worker_process_alive = process_is_alive(worker_pid)
                    worker_pid_matches = worker_process_alive
                else:
                    worker_process_alive = proc.poll() is None
                    worker_pid_matches = worker_pid_valid and worker_pid == proc.pid and worker_instance_matches
                stale = bool(
                    worker_pid_matches
                    and (not isinstance(heartbeat, (int, float))
                         or time.time() - heartbeat > self.heartbeat_timeout)
                )
                state = data.get('state', 'starting')
                if proc.poll() is not None and state in ('starting', 'running'):
                    state = 'failed'
                elif worker_instance_matches and worker_pid_valid and not worker_process_alive and state in ('starting', 'running'):
                    state = 'failed'
                    data['last_error'] = data.get('last_error') or 'worker_process_exited'
                elif data.get('worker_instance_id') and not worker_instance_matches and state in ('starting', 'running'):
                    state = 'failed'
                    data['last_error'] = 'worker_identity_mismatch'
                elif stale:
                    if not read_only:
                        self.stop(engine)
                        item = self._workers.get(engine, item)
                        proc = item['process']
                        if os.name == 'nt' and worker_pid_valid and worker_instance_matches:
                            worker_process_alive = process_is_alive(worker_pid)
                        else:
                            worker_process_alive = proc.poll() is None
                    state = 'failed'
                    data['last_error'] = 'stale_heartbeat'
                display_pid = worker_pid if worker_pid_valid and worker_instance_matches else proc.pid
                engines[engine] = {
                    **data,
                    'state': state,
                    'pid': display_pid,
                    'supervisor_pid': proc.pid,
                    'process_alive': worker_process_alive,
                    'launcher_alive': proc.poll() is None,
                    'exit_code': proc.poll(),
                    'runtime_dir': str(item['runtime']),
                    'restart_count': item.get('restart_count', 0),
                }
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
            self._sync_arbiter(release_when_idle=True)
            return {'mode': self._mode, 'mode_state': mode_state, 'engines': engines,
                    'restart_policy': dict(self._restart_policy)}
