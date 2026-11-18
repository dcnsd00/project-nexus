"""Durable SQLite state store for the NEXUS EDGE manager.

Node authentication secrets are encrypted at rest with Fernet. The caller must
supply a stable Fernet key from a protected secret store; keys are never
generated or written into this database.
"""
from __future__ import annotations

import hashlib
import json
import math
import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Any

from cryptography.fernet import Fernet, InvalidToken


class SQLiteEdgeStore:
    """Atomic SQLite persistence for EDGE nodes, tasks, leases and results."""

    SCHEMA_VERSION = 3
    MAX_TELEMETRY_EVENTS = 10_000
    TELEMETRY_PRUNE_INTERVAL = 100

    def __init__(
        self,
        database: str | Path,
        *,
        encryption_key: bytes,
        timeout_s: float = 5.0,
    ) -> None:
        if not isinstance(encryption_key, bytes):
            raise TypeError("encryption_key must be Fernet key bytes")
        if timeout_s <= 0:
            raise ValueError("timeout_s must be positive")
        self.database = Path(database).expanduser().resolve()
        self.database.parent.mkdir(parents=True, exist_ok=True)
        self.timeout_s = float(timeout_s)
        self._fernet = Fernet(encryption_key)

        # sqlite3.Connection.__exit__ commits/rolls back but does not close.
        # Explicit closing prevents one leaked connection per store operation.
        with closing(self._connect()) as connection:
            with connection:
                connection.execute("""
                    CREATE TABLE IF NOT EXISTS nexus_edge_schema (
                        component TEXT PRIMARY KEY,
                        version INTEGER NOT NULL
                    )
                """)
                row = connection.execute(
                    "SELECT version FROM nexus_edge_schema WHERE component = 'edge_store'"
                ).fetchone()
                if row and int(row[0]) > self.SCHEMA_VERSION:
                    raise RuntimeError(
                        "EDGE database schema is newer than this NEXUS version"
                    )
                connection.executescript("""
                    CREATE TABLE IF NOT EXISTS edge_nodes (
                        node_id TEXT PRIMARY KEY,
                        capabilities_json TEXT NOT NULL,
                        secret_ciphertext BLOB NOT NULL,
                        max_parallel INTEGER NOT NULL CHECK(max_parallel > 0),
                        last_seen REAL
                    );
                    CREATE TABLE IF NOT EXISTS edge_tasks (
                        task_id TEXT PRIMARY KEY,
                        task_type TEXT NOT NULL,
                        payload_json TEXT NOT NULL,
                        required_capabilities_json TEXT NOT NULL,
                        created_at REAL NOT NULL,
                        deadline REAL NOT NULL,
                        state TEXT NOT NULL,
                        node_id TEXT,
                        lease_until REAL,
                        result_json TEXT,
                        result_sha256 TEXT,
                        error TEXT
                    );
                    CREATE INDEX IF NOT EXISTS idx_edge_tasks_state_deadline
                        ON edge_tasks(state, deadline);
                    CREATE INDEX IF NOT EXISTS idx_edge_tasks_node_lease
                        ON edge_tasks(node_id, lease_until);
                    CREATE TABLE IF NOT EXISTS edge_protocol_sequences (
                        node_id TEXT PRIMARY KEY,
                        last_sequence INTEGER NOT NULL CHECK(last_sequence >= 0),
                        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                    );
                    CREATE TABLE IF NOT EXISTS edge_telemetry (
                        event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        node_id TEXT NOT NULL,
                        sequence INTEGER NOT NULL CHECK(sequence >= 1),
                        received_at REAL NOT NULL,
                        transport TEXT NOT NULL,
                        payload_json TEXT NOT NULL,
                        payload_sha256 TEXT NOT NULL
                    );
                    CREATE INDEX IF NOT EXISTS idx_edge_telemetry_node_received
                        ON edge_telemetry(node_id, received_at DESC);
                """)
                telemetry_columns = {
                    row[1] for row in connection.execute(
                        "PRAGMA table_info(edge_telemetry)"
                    )
                }
                if "sequence" not in telemetry_columns:
                    connection.execute(
                        "ALTER TABLE edge_telemetry ADD COLUMN "
                        "sequence INTEGER NOT NULL DEFAULT 0 CHECK(sequence >= 0)"
                    )
                connection.execute("""
                    CREATE UNIQUE INDEX IF NOT EXISTS idx_edge_telemetry_node_sequence
                    ON edge_telemetry(node_id, sequence) WHERE sequence > 0
                """)
                connection.execute("""
                    INSERT INTO nexus_edge_schema(component, version)
                    VALUES ('edge_store', ?)
                    ON CONFLICT(component) DO UPDATE SET version = excluded.version
                """, (self.SCHEMA_VERSION,))

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(
            str(self.database), timeout=self.timeout_s
        )
        connection.execute(f"PRAGMA busy_timeout = {int(self.timeout_s * 1000)}")
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    @staticmethod
    def _json(value: Any) -> str:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )

    def load_state(self) -> dict[str, list[dict[str, Any]]]:
        with closing(self._connect()) as connection:
            with connection:
                node_rows = connection.execute("""
                    SELECT node_id, capabilities_json, secret_ciphertext,
                           max_parallel, last_seen
                    FROM edge_nodes ORDER BY node_id
                """).fetchall()
                task_rows = connection.execute("""
                    SELECT task_id, task_type, payload_json,
                           required_capabilities_json, created_at, deadline, state,
                           node_id, lease_until, result_json, result_sha256, error
                    FROM edge_tasks ORDER BY created_at, task_id
                """).fetchall()

        nodes = []
        for node_id, caps, ciphertext, parallel, last_seen in node_rows:
            try:
                secret = self._fernet.decrypt(bytes(ciphertext))
            except InvalidToken as exc:
                raise RuntimeError(
                    f"cannot decrypt EDGE credential for node {node_id}; "
                    "verify the configured key"
                ) from exc
            nodes.append({
                "node_id": node_id,
                "capabilities": json.loads(caps),
                "secret": secret,
                "max_parallel": parallel,
                "last_seen": last_seen,
            })

        tasks = []
        for row in task_rows:
            (
                task_id, task_type, payload, required, created, deadline, state,
                node_id, lease_until, result, digest, error,
            ) = row
            tasks.append({
                "task_id": task_id,
                "task_type": task_type,
                "payload": json.loads(payload),
                "required_capabilities": json.loads(required),
                "created_at": created,
                "deadline": deadline,
                "state": state,
                "node_id": node_id,
                "lease_until": lease_until,
                "result": json.loads(result) if result is not None else None,
                "result_sha256": digest,
                "error": error,
            })
        return {"nodes": nodes, "tasks": tasks}

    def accept_and_append_telemetry(
        self,
        *,
        node_id: str,
        sequence: int,
        received_at: float,
        transport: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        """Atomically advance anti-replay state and persist one telemetry event."""
        if not isinstance(node_id, str) or not node_id.strip():
            raise ValueError("node_id must be a non-empty string")
        if not isinstance(transport, str) or not transport.strip():
            raise ValueError("transport must be a non-empty string")
        if not isinstance(sequence, int) or isinstance(sequence, bool) or sequence < 1:
            raise ValueError("sequence must be a positive integer")
        if isinstance(received_at, bool) or not isinstance(received_at, (int, float)) or not math.isfinite(float(received_at)):
            raise ValueError("received_at must be a finite number")
        payload_json = self._json(payload)
        digest = hashlib.sha256(payload_json.encode("utf-8")).hexdigest()
        with closing(self._connect()) as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                row = connection.execute(
                    "SELECT last_sequence FROM edge_protocol_sequences WHERE node_id = ?",
                    (node_id,),
                ).fetchone()
                previous = int(row[0]) if row else 0
                if sequence <= previous:
                    raise ValueError("replayed or out-of-order protocol sequence")
                connection.execute("""
                    INSERT INTO edge_protocol_sequences(node_id, last_sequence)
                    VALUES (?, ?)
                    ON CONFLICT(node_id) DO UPDATE SET
                        last_sequence = excluded.last_sequence,
                        updated_at = CURRENT_TIMESTAMP
                """, (node_id, sequence))
                cursor = connection.execute("""
                    INSERT INTO edge_telemetry(
                        node_id, sequence, received_at, transport,
                        payload_json, payload_sha256
                    ) VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    node_id, sequence, float(received_at), transport,
                    payload_json, digest,
                ))
                event_id = int(cursor.lastrowid)
                if event_id % self.TELEMETRY_PRUNE_INTERVAL == 0:
                    connection.execute("""
                        DELETE FROM edge_telemetry
                        WHERE event_id NOT IN (
                            SELECT event_id FROM edge_telemetry
                            ORDER BY event_id DESC LIMIT ?
                        )
                    """, (self.MAX_TELEMETRY_EVENTS,))
                connection.commit()
            except Exception:
                connection.rollback()
                raise
        return {
            "event_id": event_id,
            "node_id": node_id,
            "sequence": sequence,
            "received_at": float(received_at),
            "transport": transport,
            "payload_sha256": digest,
            "duplicate": False,
        }

    def get_telemetry_event(self, node_id: str, sequence: int) -> dict[str, Any] | None:
        with closing(self._connect()) as connection:
            row = connection.execute("""
                SELECT event_id, node_id, sequence, received_at, transport,
                       payload_json, payload_sha256
                FROM edge_telemetry
                WHERE node_id = ? AND sequence = ? AND sequence > 0
            """, (node_id, sequence)).fetchone()
        if row is None:
            return None
        return {
            "event_id": int(row[0]),
            "node_id": row[1],
            "sequence": int(row[2]),
            "received_at": float(row[3]),
            "transport": row[4],
            "payload": json.loads(row[5]),
            "payload_sha256": row[6],
        }

    def list_telemetry(self, *, limit: int = 100) -> list[dict[str, Any]]:
        if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 1000:
            raise ValueError("telemetry limit must be an integer between 1 and 1000")
        with closing(self._connect()) as connection:
            rows = connection.execute("""
                SELECT event_id, node_id, sequence, received_at, transport,
                       payload_json, payload_sha256
                FROM edge_telemetry
                ORDER BY event_id DESC LIMIT ?
            """, (limit,)).fetchall()
        return [{
            "event_id": int(row[0]),
            "node_id": row[1],
            "sequence": int(row[2]),
            "received_at": float(row[3]),
            "transport": row[4],
            "payload": json.loads(row[5]),
            "payload_sha256": row[6],
        } for row in rows]

    def telemetry_count(self) -> int:
        with closing(self._connect()) as connection:
            return int(connection.execute(
                "SELECT COUNT(*) FROM edge_telemetry"
            ).fetchone()[0])

    def rotate_encryption_key(self, new_key: bytes) -> dict[str, int]:
        """Atomically re-encrypt every stored node secret with a new Fernet key.

        Call only while all NEXUS EDGE processes using this database are stopped.
        The new key is held in memory only and is never written to SQLite.
        """
        if not isinstance(new_key, bytes):
            raise TypeError("new_key must be Fernet key bytes")
        new_fernet = Fernet(new_key)
        with closing(self._connect()) as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                rows = connection.execute(
                    "SELECT node_id, secret_ciphertext FROM edge_nodes ORDER BY node_id"
                ).fetchall()
                replacements = []
                for node_id, ciphertext in rows:
                    try:
                        plaintext = self._fernet.decrypt(bytes(ciphertext))
                    except InvalidToken as exc:
                        raise RuntimeError(
                            f"cannot decrypt EDGE credential for node {node_id}; "
                            "current key is incorrect or database data is damaged"
                        ) from exc
                    replacements.append(
                        (new_fernet.encrypt(plaintext), node_id)
                    )
                connection.executemany(
                    "UPDATE edge_nodes SET secret_ciphertext = ? WHERE node_id = ?",
                    replacements,
                )
                connection.commit()
            except Exception:
                connection.rollback()
                raise
        self._fernet = new_fernet
        return {"nodes_reencrypted": len(replacements)}

    def save_state(
        self,
        *,
        nodes: list[dict[str, Any]],
        tasks: list[dict[str, Any]],
    ) -> None:
        """Replace the snapshot atomically; readers never observe half a state."""
        with closing(self._connect()) as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                connection.execute("DELETE FROM edge_tasks")
                connection.execute("DELETE FROM edge_nodes")
                connection.executemany("""
                    INSERT INTO edge_nodes(
                        node_id, capabilities_json, secret_ciphertext,
                        max_parallel, last_seen
                    ) VALUES (?, ?, ?, ?, ?)
                """, [(
                    node["node_id"],
                    self._json(node["capabilities"]),
                    self._fernet.encrypt(node["secret"]),
                    node["max_parallel"],
                    node["last_seen"],
                ) for node in nodes])
                connection.executemany("""
                    INSERT INTO edge_tasks(
                        task_id, task_type, payload_json,
                        required_capabilities_json, created_at, deadline, state,
                        node_id, lease_until, result_json, result_sha256, error
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, [(
                    task["task_id"],
                    task["task_type"],
                    self._json(task["payload"]),
                    self._json(task["required_capabilities"]),
                    task["created_at"],
                    task["deadline"],
                    task["state"],
                    task["node_id"],
                    task["lease_until"],
                    self._json(task["result"]) if task["result"] is not None else None,
                    task["result_sha256"],
                    task["error"],
                ) for task in tasks])
                connection.commit()
            except Exception:
                connection.rollback()
                raise
