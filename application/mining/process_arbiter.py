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
import hashlib
import json
import os
import threading
from pathlib import Path
from typing import BinaryIO, Iterable

from modules.data_paths import data_path


def process_is_alive(pid: int | None) -> bool:
    """Return a conservative process-liveness result for a positive PID."""
    if isinstance(pid, bool) or not isinstance(pid, int) or pid <= 0:
        return False
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
        self._mutex_handle = None
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
            import ctypes
            from ctypes import wintypes

            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            kernel32.CreateMutexW.argtypes = (
                wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR,
            )
            kernel32.CreateMutexW.restype = wintypes.HANDLE
            kernel32.WaitForSingleObject.argtypes = (wintypes.HANDLE, wintypes.DWORD)
            kernel32.WaitForSingleObject.restype = wintypes.DWORD
            kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
            kernel32.CloseHandle.restype = wintypes.BOOL

            identity = hashlib.sha256(
                str(self.path).casefold().encode("utf-8")
            ).hexdigest()
            mutex_name = "Local\\NEXUS_MINING_RUNTIME_" + identity
            mutex_handle = kernel32.CreateMutexW(None, False, mutex_name)
            if not mutex_handle:
                raise ctypes.WinError(ctypes.get_last_error())

            wait_result = kernel32.WaitForSingleObject(mutex_handle, 0)
            if wait_result in (0x00000000, 0x00000080):  # WAIT_OBJECT_0 / WAIT_ABANDONED
                self._mutex_handle = mutex_handle
                return

            kernel32.CloseHandle(mutex_handle)
            if wait_result == 0x00000102:  # WAIT_TIMEOUT
                raise BlockingIOError(errno.EAGAIN, "NEXUS mining runtime is already locked")
            raise ctypes.WinError(ctypes.get_last_error())
        else:
            import fcntl

            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)

    def _unlock_os_file(self, handle: BinaryIO) -> None:
        if os.name == "nt":
            import ctypes
            from ctypes import wintypes

            mutex_handle = self._mutex_handle
            if mutex_handle is None:
                return
            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            kernel32.ReleaseMutex.argtypes = (wintypes.HANDLE,)
            kernel32.ReleaseMutex.restype = wintypes.BOOL
            kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
            kernel32.CloseHandle.restype = wintypes.BOOL
            released = kernel32.ReleaseMutex(mutex_handle)
            error_code = ctypes.get_last_error()
            kernel32.CloseHandle(mutex_handle)
            self._mutex_handle = None
            if not released:
                raise ctypes.WinError(error_code)
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
