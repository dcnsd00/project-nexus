"""Exclusive process lock for one NEXUS EDGE SQLite runtime.

SQLite protects individual transactions, but EDGE manager snapshots are held
in process memory. Only one independent NEXUS/EDGE runtime may own a database
at a time. The lock is advisory and held for the entire runtime lifetime.
"""
from __future__ import annotations

import errno
import os
from pathlib import Path
from typing import BinaryIO


class EdgeRuntimeLock:
    """Cross-platform non-blocking exclusive lock associated with one DB path."""

    def __init__(self, database: str | Path) -> None:
        db = Path(database).expanduser().resolve()
        self.path = db.with_name(db.name + ".runtime.lock")
        self._file: BinaryIO | None = None

    @property
    def acquired(self) -> bool:
        return self._file is not None

    def acquire(self) -> "EdgeRuntimeLock":
        if self._file is not None:
            return self
        self.path.parent.mkdir(parents=True, exist_ok=True)
        handle = self.path.open("a+b")
        try:
            if os.name == "nt":
                import msvcrt

                handle.seek(0, os.SEEK_END)
                if handle.tell() == 0:
                    handle.write(b"\0")
                    handle.flush()
                handle.seek(0)
                try:
                    msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                except OSError as exc:
                    raise RuntimeError(
                        f"NEXUS EDGE database is already in use by another process: {self.path}"
                    ) from exc
            else:
                import fcntl

                try:
                    fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                except OSError as exc:
                    if exc.errno in (errno.EACCES, errno.EAGAIN):
                        raise RuntimeError(
                            f"NEXUS EDGE database is already in use by another process: {self.path}"
                        ) from exc
                    raise
            self._file = handle
            return self
        except Exception:
            handle.close()
            raise

    def release(self) -> None:
        handle, self._file = self._file, None
        if handle is None:
            return
        try:
            handle.seek(0)
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        finally:
            handle.close()

    def __enter__(self) -> "EdgeRuntimeLock":
        return self.acquire()

    def __exit__(self, exc_type, exc, tb) -> None:
        self.release()
