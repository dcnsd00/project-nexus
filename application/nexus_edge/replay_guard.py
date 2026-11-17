"""Persistent anti-replay guard for NEXUS EDGE protocol messages.

The guard stores only the highest accepted sequence number per node. It never
stores node HMAC secrets. SQLite transactions serialize concurrent updates so
a sequence can be accepted at most once, including across process restarts.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path
from threading import Lock
from typing import Protocol


class ReplayError(ValueError):
    """Raised when a protocol sequence is invalid or has already been used."""


class ReplayGuard(Protocol):
    def accept(self, node_id: str, sequence: int) -> None:
        """Atomically accept a strictly increasing sequence for a node."""


class MemoryReplayGuard:
    """Process-local guard for tests and explicitly ephemeral deployments."""

    def __init__(self) -> None:
        self._last: dict[str, int] = {}
        self._lock = Lock()

    def accept(self, node_id: str, sequence: int) -> None:
        _validate(node_id, sequence)
        with self._lock:
            previous = self._last.get(node_id, 0)
            if sequence <= previous:
                raise ReplayError("replayed or out-of-order protocol sequence")
            self._last[node_id] = sequence


class SQLiteReplayGuard:
    """Durable replay guard using an atomic SQLite write transaction."""

    def __init__(self, database: str | Path, *, timeout_s: float = 5.0) -> None:
        if timeout_s <= 0:
            raise ValueError("timeout_s must be positive")
        self.database = Path(database).expanduser().resolve()
        self.database.parent.mkdir(parents=True, exist_ok=True)
        self.timeout_s = float(timeout_s)
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS edge_protocol_sequences (
                    node_id TEXT PRIMARY KEY,
                    last_sequence INTEGER NOT NULL CHECK(last_sequence >= 0),
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            connection.execute(
                "PRAGMA user_version = 1"
            )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(
            str(self.database), timeout=self.timeout_s, isolation_level=None
        )
        connection.execute("PRAGMA busy_timeout = 5000")
        return connection

    def accept(self, node_id: str, sequence: int) -> None:
        _validate(node_id, sequence)
        with self._connect() as connection:
            try:
                connection.execute("BEGIN IMMEDIATE")
                row = connection.execute(
                    "SELECT last_sequence FROM edge_protocol_sequences WHERE node_id = ?",
                    (node_id,),
                ).fetchone()
                previous = int(row[0]) if row else 0
                if sequence <= previous:
                    raise ReplayError("replayed or out-of-order protocol sequence")
                connection.execute(
                    """
                    INSERT INTO edge_protocol_sequences(node_id, last_sequence)
                    VALUES (?, ?)
                    ON CONFLICT(node_id) DO UPDATE SET
                        last_sequence = excluded.last_sequence,
                        updated_at = CURRENT_TIMESTAMP
                    """,
                    (node_id, sequence),
                )
                connection.execute("COMMIT")
            except Exception:
                if connection.in_transaction:
                    connection.execute("ROLLBACK")
                raise


def _validate(node_id: str, sequence: int) -> None:
    if not isinstance(node_id, str) or not node_id.strip():
        raise ReplayError("node_id must be a non-empty string")
    if not isinstance(sequence, int) or isinstance(sequence, bool) or sequence < 1:
        raise ReplayError("sequence must be a positive integer")
