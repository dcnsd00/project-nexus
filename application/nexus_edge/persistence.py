"""Durable NEXUS EDGE state and secure key-provider contracts."""
from __future__ import annotations

import base64
import json
import sqlite3
from pathlib import Path
from threading import RLock
from typing import Any, Protocol


class EdgeStorageError(RuntimeError):
    """Raised for incompatible or failed EDGE persistence operations."""


class EdgeStateStore(Protocol):
    def load_state(self) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]: ...
    def save_batch(self, nodes: list[dict[str, Any]], tasks: list[dict[str, Any]]) -> None: ...
    def close(self) -> None: ...


class EdgeKeyProvider(Protocol):
    def put_key(self, node_id: str, secret: bytes) -> None: ...
    def get_key(self, node_id: str) -> bytes | None: ...
    def delete_key(self, node_id: str) -> None: ...


class InMemoryEdgeKeyProvider:
    """Process-memory key provider for tests and ephemeral development only."""

    def __init__(self) -> None:
        self._keys: dict[str, bytes] = {}

    def put_key(self, node_id: str, secret: bytes) -> None:
        if not isinstance(secret, bytes) or len(secret) < 32:
            raise EdgeStorageError("node key must contain at least 32 bytes")
        self._keys[node_id] = bytes(secret)

    def get_key(self, node_id: str) -> bytes | None:
        return self._keys.get(node_id)

    def delete_key(self, node_id: str) -> None:
        self._keys.pop(node_id, None)


class KeyringEdgeKeyProvider:
    """Store per-node HMAC keys in the active OS keyring; fail if no backend exists."""

    SERVICE_NAME = "NEXUS-EDGE-HMAC-v1"

    def __init__(self) -> None:
        try:
            import keyring
        except ImportError as exc:
            raise EdgeStorageError("install the 'keyring' package to use OS-backed EDGE keys") from exc
        backend = keyring.get_keyring()
        if getattr(backend, "priority", 0) <= 0:
            raise EdgeStorageError("no secure OS keyring backend is active")
        self._keyring = keyring

    @staticmethod
    def _username(node_id: str) -> str:
        return f"edge-node:{node_id}"

    def put_key(self, node_id: str, secret: bytes) -> None:
        if not isinstance(secret, bytes) or len(secret) < 32:
            raise EdgeStorageError("node key must contain at least 32 bytes")
        encoded = base64.b64encode(secret).decode("ascii")
        self._keyring.set_password(self.SERVICE_NAME, self._username(node_id), encoded)

    def get_key(self, node_id: str) -> bytes | None:
        encoded = self._keyring.get_password(self.SERVICE_NAME, self._username(node_id))
        if encoded is None:
            return None
        try:
            secret = base64.b64decode(encoded, validate=True)
        except (ValueError, TypeError) as exc:
            raise EdgeStorageError(f"invalid keyring data for node {node_id}") from exc
        if len(secret) < 32:
            raise EdgeStorageError(f"stored key for node {node_id} is too short")
        return secret

    def delete_key(self, node_id: str) -> None:
        username = self._username(node_id)
        if self._keyring.get_password(self.SERVICE_NAME, username) is not None:
            self._keyring.delete_password(self.SERVICE_NAME, username)


def _json(value: Any) -> str:
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise EdgeStorageError(f"EDGE state is not valid JSON: {exc}") from exc


class SQLiteEdgeStore:
    """Versioned SQLite store for node metadata and task state, excluding secrets."""

    SCHEMA_VERSION = 1

    def __init__(self, path: str | Path) -> None:
        self.path = str(path)
        if self.path != ":memory:":
            target = Path(self.path).expanduser()
            target.parent.mkdir(parents=True, exist_ok=True)
            self.path = str(target)
        self._lock = RLock()
        try:
            self._connection = sqlite3.connect(
                self.path, timeout=5.0, check_same_thread=False, isolation_level=None
            )
            self._connection.row_factory = sqlite3.Row
            self._connection.execute("PRAGMA foreign_keys=ON")
            self._connection.execute("PRAGMA busy_timeout=5000")
            if self.path != ":memory:":
                self._connection.execute("PRAGMA journal_mode=WAL")
            self._migrate()
        except Exception as exc:
            raise EdgeStorageError(f"could not initialize EDGE SQLite store: {exc}") from exc

    def _migrate(self) -> None:
        version = self._connection.execute("PRAGMA user_version").fetchone()[0]
        if version > self.SCHEMA_VERSION:
            raise EdgeStorageError(
                f"EDGE database schema {version} is newer than supported {self.SCHEMA_VERSION}"
            )
        if version == 0:
            self._connection.executescript("""
                BEGIN IMMEDIATE;
                CREATE TABLE IF NOT EXISTS edge_nodes (
                    node_id TEXT PRIMARY KEY,
                    capabilities_json TEXT NOT NULL,
                    max_parallel INTEGER NOT NULL CHECK(max_parallel > 0),
                    last_seen REAL,
                    last_heartbeat_sequence INTEGER NOT NULL DEFAULT -1,
                    last_result_sequence INTEGER NOT NULL DEFAULT -1
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
                    assignment_nonce TEXT,
                    result_json TEXT,
                    result_sha256 TEXT,
                    error TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_edge_tasks_state_deadline
                    ON edge_tasks(state, deadline);
                CREATE INDEX IF NOT EXISTS idx_edge_tasks_node_state
                    ON edge_tasks(node_id, state);
                PRAGMA user_version=1;
                COMMIT;
            """)

    def load_state(self) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        with self._lock:
            try:
                node_rows = self._connection.execute(
                    "SELECT * FROM edge_nodes ORDER BY node_id"
                ).fetchall()
                task_rows = self._connection.execute(
                    "SELECT * FROM edge_tasks ORDER BY created_at, task_id"
                ).fetchall()
                nodes = [{
                    "node_id": row["node_id"],
                    "capabilities": json.loads(row["capabilities_json"]),
                    "max_parallel": row["max_parallel"],
                    "last_seen": row["last_seen"],
                    "last_heartbeat_sequence": row["last_heartbeat_sequence"],
                    "last_result_sequence": row["last_result_sequence"],
                } for row in node_rows]
                tasks = [{
                    "task_id": row["task_id"],
                    "task_type": row["task_type"],
                    "payload": json.loads(row["payload_json"]),
                    "required_capabilities": json.loads(row["required_capabilities_json"]),
                    "created_at": row["created_at"],
                    "deadline": row["deadline"],
                    "state": row["state"],
                    "node_id": row["node_id"],
                    "lease_until": row["lease_until"],
                    "assignment_nonce": row["assignment_nonce"],
                    "result": json.loads(row["result_json"]) if row["result_json"] is not None else None,
                    "result_sha256": row["result_sha256"],
                    "error": row["error"],
                } for row in task_rows]
                return nodes, tasks
            except Exception as exc:
                raise EdgeStorageError(f"could not load EDGE state: {exc}") from exc

    def save_batch(
        self, nodes: list[dict[str, Any]] | None = None,
        tasks: list[dict[str, Any]] | None = None,
    ) -> None:
        nodes = nodes or []
        tasks = tasks or []
        if not nodes and not tasks:
            return
        with self._lock:
            try:
                self._connection.execute("BEGIN IMMEDIATE")
                for node in nodes:
                    self._connection.execute("""
                        INSERT INTO edge_nodes (
                            node_id, capabilities_json, max_parallel, last_seen,
                            last_heartbeat_sequence, last_result_sequence
                        ) VALUES (?, ?, ?, ?, ?, ?)
                        ON CONFLICT(node_id) DO UPDATE SET
                            capabilities_json=excluded.capabilities_json,
                            max_parallel=excluded.max_parallel,
                            last_seen=excluded.last_seen,
                            last_heartbeat_sequence=excluded.last_heartbeat_sequence,
                            last_result_sequence=excluded.last_result_sequence
                    """, (
                        node["node_id"], _json(node["capabilities"]), node["max_parallel"],
                        node["last_seen"], node["last_heartbeat_sequence"],
                        node["last_result_sequence"],
                    ))
                for task in tasks:
                    self._connection.execute("""
                        INSERT INTO edge_tasks (
                            task_id, task_type, payload_json, required_capabilities_json,
                            created_at, deadline, state, node_id, lease_until,
                            assignment_nonce, result_json, result_sha256, error
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(task_id) DO UPDATE SET
                            task_type=excluded.task_type,
                            payload_json=excluded.payload_json,
                            required_capabilities_json=excluded.required_capabilities_json,
                            created_at=excluded.created_at,
                            deadline=excluded.deadline,
                            state=excluded.state,
                            node_id=excluded.node_id,
                            lease_until=excluded.lease_until,
                            assignment_nonce=excluded.assignment_nonce,
                            result_json=excluded.result_json,
                            result_sha256=excluded.result_sha256,
                            error=excluded.error
                    """, (
                        task["task_id"], task["task_type"], _json(task["payload"]),
                        _json(task["required_capabilities"]), task["created_at"],
                        task["deadline"], task["state"], task["node_id"],
                        task["lease_until"], task["assignment_nonce"],
                        _json(task["result"]) if task["result"] is not None else None,
                        task["result_sha256"], task["error"],
                    ))
                self._connection.execute("COMMIT")
            except Exception as exc:
                try:
                    self._connection.execute("ROLLBACK")
                except sqlite3.Error:
                    pass
                raise EdgeStorageError(f"could not save EDGE state atomically: {exc}") from exc

    def close(self) -> None:
        with self._lock:
            self._connection.close()
