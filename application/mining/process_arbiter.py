"""Cross-process arbitration for NEXUS mining execution paths.

The direct miner controller and HybridSupervisor are separate execution
paths. This lock prevents both paths (or two NEXUS instances) from owning
the same host's mining runtime at the same time.

The OS lock is held for the full mining session. A small metadata record keeps
child miner PIDs so a crashed API process cannot silently release ownership
while an orphaned miner is still alive.
"""
from __future__ import annotations

import errno
import json
import os
import threading
from pathlib import Path
from typing import BinaryIO, Iterable

from modules.data_paths import data_path


def _windows_process_is_alive(pid: int) -> bool:
    """Fail closed when Windows process state cannot be queried safely."""
    try:
        import ctypes
        from ctypes import wintypes

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        kernel32.OpenProcess.restype = wintypes.HANDLE
        kernel32.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
        kernel32.GetExitCodeProcess.restype = wintypes.BOOL
        kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel32.CloseHandle.restype = wintypes.BOOL

        handle = kernel32.OpenProcess(0x1000, False, pid)
        if not handle:
            # Only definitive "PID does not exist" errors are considered dead.
            return ctypes.get_last_error() not in (87, 1168)

        try:
            exit_code = wintypes.DWORD()
            if not kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)):
                return True
            return exit_code.value == 259  # STILL_ACTIVE
        finally:
            kernel32.CloseHandle(handle)
    except Exception:
        return True

def process_is_alive(pid: int | None) -> bool:
    """Return a conservative process-liveness result for a positive PID."""
    if isinstance(pid, bool) or not isinstance(pid, int) or pid <= 0:
        return False
    if os.name == "nt":
        return _windows_process_is_alive(pid)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError as exc:
        if exc.errno == errno.ESRCH:
            return False
        if exc.errno in (errno.EPERM, errno.EACCES):
            return True
        return False
    return True


class MiningProcessArbiter:
    """Non-blocking cross-process exclusive lease for one mining runtime."""

    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path).expanduser().resolve() if path else data_path(
            "mining", "process_arbiter.lock"
        ).resolve()
        self._file: BinaryIO | None = None
        self._owner: str | None = None
        self._win_locked = False
        self._guard = threading.RLock()

    @property
    def held(self) -> bool:
        with self._guard:
            return self._file is not None

    @property
    def owner(self) -> str | None:
        with self._guard:
            return self._owner

    def _lock_os_file(self, handle: BinaryIO) -> None:
        handle.seek(0, os.SEEK_END)
        if handle.tell() == 0:
            handle.write(b"\0")
            handle.flush()
        handle.seek(0)
        if os.name == "nt":
            import msvcrt

            try:
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError as exc:
                if exc.errno in (errno.EACCES, errno.EAGAIN, errno.EDEADLK):
                    raise BlockingIOError(errno.EAGAIN, "NEXUS mining runtime is already locked") from exc
                raise
            self._win_locked = True
        else:
            import fcntl

            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)

    def _unlock_os_file(self, handle: BinaryIO) -> None:
        if os.name == "nt":
            import msvcrt

            if not self._win_locked:
                return
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            self._win_locked = False
        else:
            import fcntl

            handle.seek(0)
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)

    @staticmethod
    def _read_metadata(handle: BinaryIO) -> dict:
        try:
            handle.seek(1)
            raw = handle.read()
            value = json.loads(raw.decode("utf-8")) if raw else {}
            return value if isinstance(value, dict) else {}
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            return {}

    @staticmethod
    def _write_metadata(handle: BinaryIO, value: dict) -> None:
        raw = json.dumps(value, separators=(",", ":"), sort_keys=True).encode("utf-8")
        handle.seek(0)
        sentinel = handle.read(1) or b"\0"
        handle.seek(0)
        handle.write(sentinel + raw)
        handle.truncate(1 + len(raw))
        handle.flush()
        # Windows FlushFileBuffers on an actively byte-locked handle can
        # stall on some runners/filesystems. FileIO is unbuffered and flush()
        # has already handed the metadata to the OS cache; the live OS lock
        # protects concurrent readers. POSIX keeps fsync for crash durability.
        if os.name != "nt":
            try:
                os.fsync(handle.fileno())
            except OSError:
                pass

    def _metadata_has_live_process(self, metadata: dict) -> bool:
        owner_pid = metadata.get("owner_pid")
        if process_is_alive(owner_pid):
            return True
        pids = metadata.get("process_pids", [])
        if isinstance(pids, list):
            return any(process_is_alive(pid) for pid in pids)
        return False

    def acquire(self, owner: str, process_pids: Iterable[int] = ()) -> bool:
        owner = str(owner).strip()
        if not owner or len(owner) > 120:
            raise ValueError("Mining lease owner must be a non-empty label of at most 120 characters")
        with self._guard:
            if self._file is not None:
                return self._owner == owner

            self.path.parent.mkdir(parents=True, exist_ok=True)
            descriptor = os.open(self.path, os.O_CREAT | os.O_RDWR, 0o600)
            handle = os.fdopen(descriptor, "r+b", buffering=0)
            try:
                self._lock_os_file(handle)
            except OSError as exc:
                handle.close()
                if getattr(exc, "errno", None) in (errno.EACCES, errno.EAGAIN, errno.EDEADLK):
                    return False
                # Windows msvcrt reports lock contention as a generic OSError.
                if os.name == "nt":
                    return False
                raise

            previous = self._read_metadata(handle)
            if self._metadata_has_live_process(previous):
                try:
                    self._unlock_os_file(handle)
                finally:
                    handle.close()
                return False

            pids = sorted({int(pid) for pid in process_pids if isinstance(pid, int) and not isinstance(pid, bool) and pid > 0})
            self._write_metadata(handle, {
                "schema_version": 1,
                "owner": owner,
                "owner_pid": os.getpid(),
                "process_pids": pids,
            })
            self._file = handle
            self._owner = owner
            return True

    def update_processes(self, owner: str, process_pids: Iterable[int]) -> bool:
        with self._guard:
            if self._file is None or self._owner != owner:
                return False
            pids = sorted({int(pid) for pid in process_pids if isinstance(pid, int) and not isinstance(pid, bool) and pid > 0})
            self._write_metadata(self._file, {
                "schema_version": 1,
                "owner": owner,
                "owner_pid": os.getpid(),
                "process_pids": pids,
            })
            return True

    def release(self, owner: str) -> bool:
        with self._guard:
            if self._file is None:
                return False
            if self._owner != owner:
                return False
            handle, self._file = self._file, None
            self._owner = None
            try:
                # Keep the lock-byte sentinel, but remove the previous lease
                # so a clean shutdown is distinguishable from a crashed one.
                handle.seek(0)
                sentinel = handle.read(1) or b"\0"
                handle.seek(0)
                handle.write(sentinel)
                handle.truncate(1)
                handle.flush()
                self._unlock_os_file(handle)
            finally:
                handle.close()
            return True


MINING_PROCESS_ARBITER = MiningProcessArbiter()
