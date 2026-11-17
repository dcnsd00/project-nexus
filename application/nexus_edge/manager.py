"""NEXUS EDGE control plane with versioned replay protection and durable state.

The manager remains transport-agnostic. SQLite stores operational metadata and
task state; node HMAC keys are supplied by an injected key provider and are
never written to the database.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import re
import secrets
import time
import uuid
from dataclasses import dataclass, field, replace
from functools import wraps
from threading import RLock
from typing import Any, Callable

from .persistence import EdgeKeyProvider, EdgeStateStore, InMemoryEdgeKeyProvider


class EdgeError(ValueError):
    """Raised when a node or task operation violates the EDGE contract."""


def _canonical(value: Any) -> bytes:
    try:
        return json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise EdgeError(f"message is not canonical JSON: {exc}") from exc


def sign_message(secret: bytes, message: Any) -> str:
    """Return a SHA-256 HMAC for a JSON-compatible message."""
    if not isinstance(secret, bytes) or len(secret) < 32:
        raise EdgeError("node secret must contain at least 32 bytes")
    return hmac.new(secret, _canonical(message), hashlib.sha256).hexdigest()


def _verify(secret: bytes, message: Any, signature: str) -> bool:
    if not isinstance(signature, str):
        return False
    expected = sign_message(secret, message)
    return hmac.compare_digest(expected, signature.lower())


def _synchronized(method):
    @wraps(method)
    def wrapped(self, *args, **kwargs):
        with self._lock:
            return method(self, *args, **kwargs)
    return wrapped


@dataclass
class _Node:
    node_id: str
    capabilities: frozenset[str]
    secret: bytes = field(repr=False)
    max_parallel: int = 1
    last_seen: float | None = None
    active_tasks: set[str] = field(default_factory=set)
    last_heartbeat_sequence: int = -1
    last_result_sequence: int = -1


@dataclass
class _Task:
    task_id: str
    task_type: str
    payload: dict[str, Any]
    required_capabilities: frozenset[str]
    created_at: float
    deadline: float
    state: str = "QUEUED"
    node_id: str | None = None
    lease_until: float | None = None
    assignment_nonce: str | None = None
    result: Any = None
    result_sha256: str | None = None
    error: str | None = None


class EdgeManager:
    """Node registry, capability scheduler, lease manager and result verifier."""

    PROTOCOL_VERSION = 1

    def __init__(
        self,
        *,
        heartbeat_ttl_s: int = 90,
        lease_s: int = 60,
        max_payload_bytes: int = 65_536,
        clock: Callable[[], float] = time.time,
        store: EdgeStateStore | None = None,
        key_provider: EdgeKeyProvider | None = None,
    ) -> None:
        if heartbeat_ttl_s < 1 or lease_s < 1 or max_payload_bytes < 128:
            raise EdgeError("invalid EDGE manager limits")
        if store is not None and key_provider is None:
            raise EdgeError("persistent EDGE storage requires an external key provider")
        self.heartbeat_ttl_s = heartbeat_ttl_s
        self.lease_s = lease_s
        self.max_payload_bytes = max_payload_bytes
        self._clock = clock
        self._store = store
        self._key_provider = key_provider or InMemoryEdgeKeyProvider()
        self._lock = RLock()
        self._nodes: dict[str, _Node] = {}
        self._tasks: dict[str, _Task] = {}
        if self._store is not None:
            self._restore_state()

    def _restore_state(self) -> None:
        try:
            node_rows, task_rows = self._store.load_state()
            for row in node_rows:
                secret = self._key_provider.get_key(row["node_id"])
                if not isinstance(secret, bytes) or len(secret) < 32:
                    raise EdgeError(
                        f"secure key unavailable for persisted node {row['node_id']}; "
                        "startup stopped rather than disabling authentication"
                    )
                node = _Node(
                    node_id=row["node_id"],
                    capabilities=frozenset(row["capabilities"]),
                    secret=secret,
                    max_parallel=row["max_parallel"],
                    last_seen=row["last_seen"],
                    last_heartbeat_sequence=row["last_heartbeat_sequence"],
                    last_result_sequence=row["last_result_sequence"],
                )
                self._nodes[node.node_id] = node
            for row in task_rows:
                task = _Task(
                    task_id=row["task_id"],
                    task_type=row["task_type"],
                    payload=row["payload"],
                    required_capabilities=frozenset(row["required_capabilities"]),
                    created_at=row["created_at"],
                    deadline=row["deadline"],
                    state=row["state"],
                    node_id=row["node_id"],
                    lease_until=row["lease_until"],
                    assignment_nonce=row["assignment_nonce"],
                    result=row["result"],
                    result_sha256=row["result_sha256"],
                    error=row["error"],
                )
                self._tasks[task.task_id] = task
                if task.state in {"ASSIGNED", "RUNNING"} and task.node_id in self._nodes:
                    self._nodes[task.node_id].active_tasks.add(task.task_id)
        except EdgeError:
            raise
        except Exception as exc:
            raise EdgeError(f"could not restore persistent EDGE state: {exc}") from exc

    def _node_record(self, node: _Node) -> dict[str, Any]:
        return {
            "node_id": node.node_id,
            "capabilities": sorted(node.capabilities),
            "max_parallel": node.max_parallel,
            "last_seen": node.last_seen,
            "last_heartbeat_sequence": node.last_heartbeat_sequence,
            "last_result_sequence": node.last_result_sequence,
        }

    def _task_record(self, task: _Task) -> dict[str, Any]:
        return {
            "task_id": task.task_id,
            "task_type": task.task_type,
            "payload": task.payload,
            "required_capabilities": sorted(task.required_capabilities),
            "created_at": task.created_at,
            "deadline": task.deadline,
            "state": task.state,
            "node_id": task.node_id,
            "lease_until": task.lease_until,
            "assignment_nonce": task.assignment_nonce,
            "result": task.result,
            "result_sha256": task.result_sha256,
            "error": task.error,
        }

    def _save(self, *, nodes=(), tasks=()) -> None:
        if self._store is not None:
            self._store.save_batch(
                [self._node_record(node) for node in nodes],
                [self._task_record(task) for task in tasks],
            )

    @staticmethod
    def _validate_sequence(sequence: int, previous: int, label: str) -> None:
        if not isinstance(sequence, int) or isinstance(sequence, bool) or sequence < 0:
            raise EdgeError(f"{label} sequence must be a non-negative integer")
        if sequence <= previous:
            raise EdgeError(f"replayed or out-of-order {label} sequence")

    @_synchronized
    def register_node(
        self, node_id: str, capabilities: list[str] | tuple[str, ...],
        secret: bytes, *, max_parallel: int = 1,
    ) -> dict[str, Any]:
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]{2,63}", node_id or ""):
            raise EdgeError("node_id must be 3-64 safe identifier characters")
        if node_id in self._nodes:
            raise EdgeError(f"node already registered: {node_id}")
        if not isinstance(secret, bytes) or len(secret) < 32:
            raise EdgeError("node secret must contain at least 32 bytes")
        if not isinstance(max_parallel, int) or isinstance(max_parallel, bool) or max_parallel < 1:
            raise EdgeError("max_parallel must be a positive integer")
        caps = frozenset(str(c).strip().lower() for c in capabilities if str(c).strip())
        if not caps:
            raise EdgeError("at least one capability is required")

        node = _Node(node_id, caps, secret, max_parallel)
        self._key_provider.put_key(node_id, secret)
        try:
            self._save(nodes=(node,))
        except Exception:
            self._key_provider.delete_key(node_id)
            raise
        self._nodes[node_id] = node
        return self.node_status(node_id)

    @_synchronized
    def heartbeat(
        self, node_id: str, timestamp: float, sequence: int, signature: str,
    ) -> dict[str, Any]:
        node = self._get_node(node_id)
        now = self._clock()
        if not isinstance(timestamp, (int, float)) or isinstance(timestamp, bool):
            raise EdgeError("heartbeat timestamp must be numeric")
        if abs(now - float(timestamp)) > self.heartbeat_ttl_s:
            raise EdgeError("heartbeat timestamp outside allowed clock-skew window")
        self._validate_sequence(sequence, node.last_heartbeat_sequence, "heartbeat")
        message = {
            "protocol_version": self.PROTOCOL_VERSION,
            "kind": "heartbeat",
            "node_id": node_id,
            "timestamp": timestamp,
            "sequence": sequence,
        }
        if not _verify(node.secret, message, signature):
            raise EdgeError("invalid heartbeat signature")
        updated = replace(node, last_seen=now, last_heartbeat_sequence=sequence)
        self._save(nodes=(updated,))
        self._nodes[node_id] = updated
        return self.node_status(node_id)

    @_synchronized
    def submit_task(
        self, task_type: str, payload: dict[str, Any],
        required_capabilities: list[str] | tuple[str, ...], *,
        ttl_s: int = 300, task_id: str | None = None,
    ) -> dict[str, Any]:
        if not re.fullmatch(r"[a-z][a-z0-9_.-]{1,63}", task_type or ""):
            raise EdgeError("task_type must be a lowercase capability-style identifier")
        if not isinstance(payload, dict):
            raise EdgeError("task payload must be a JSON object")
        if len(_canonical(payload)) > self.max_payload_bytes:
            raise EdgeError("task payload exceeds configured size limit")
        if not isinstance(ttl_s, int) or isinstance(ttl_s, bool) or ttl_s < 1:
            raise EdgeError("ttl_s must be a positive integer")
        required = frozenset(str(c).strip().lower() for c in required_capabilities if str(c).strip())
        if not required:
            raise EdgeError("at least one required capability is required")
        identifier = task_id or str(uuid.uuid4())
        if identifier in self._tasks:
            raise EdgeError(f"duplicate task_id: {identifier}")
        now = self._clock()
        task = _Task(identifier, task_type, payload, required, now, now + ttl_s)
        self._save(tasks=(task,))
        self._tasks[identifier] = task
        return self.task_status(identifier)

    @_synchronized
    def claim_task(self, node_id: str) -> dict[str, Any] | None:
        node = self._get_node(node_id)
        now = self._clock()
        if not self._is_online(node, now):
            raise EdgeError("node is offline or has not sent an authenticated heartbeat")
        self.reap_expired()
        node = self._get_node(node_id)
        if len(node.active_tasks) >= node.max_parallel:
            return None
        for task in self._tasks.values():
            if task.state != "QUEUED" or not task.required_capabilities.issubset(node.capabilities):
                continue
            updated = replace(
                task, state="ASSIGNED", node_id=node_id,
                lease_until=min(task.deadline, now + self.lease_s),
                assignment_nonce=secrets.token_urlsafe(24),
            )
            self._save(tasks=(updated,))
            self._tasks[task.task_id] = updated
            node.active_tasks.add(task.task_id)
            return self.task_status(task.task_id)
        return None

    @_synchronized
    def start_task(self, node_id: str, task_id: str) -> dict[str, Any]:
        task = self._get_task(task_id)
        if task.node_id != node_id or task.state != "ASSIGNED":
            raise EdgeError("task is not assigned to this node")
        if task.lease_until is None or task.lease_until <= self._clock():
            raise EdgeError("task lease expired")
        updated = replace(task, state="RUNNING")
        self._save(tasks=(updated,))
        self._tasks[task_id] = updated
        return self.task_status(task_id)

    @_synchronized
    def complete_task(
        self, node_id: str, task_id: str, result: Any, sequence: int,
        assignment_nonce: str, signature: str,
    ) -> dict[str, Any]:
        node = self._get_node(node_id)
        task = self._get_task(task_id)
        if task.node_id != node_id or task.state != "RUNNING":
            raise EdgeError("task is not running on this node")
        now = self._clock()
        if task.lease_until is None or task.lease_until <= now or task.deadline <= now:
            raise EdgeError("task lease or deadline expired")
        if not isinstance(assignment_nonce, str) or not hmac.compare_digest(
            task.assignment_nonce or "", assignment_nonce
        ):
            raise EdgeError("assignment nonce mismatch; stale worker result rejected")
        self._validate_sequence(sequence, node.last_result_sequence, "result")
        if len(_canonical(result)) > self.max_payload_bytes:
            raise EdgeError("task result exceeds configured size limit")
        message = {
            "protocol_version": self.PROTOCOL_VERSION,
            "kind": "task_result",
            "node_id": node_id,
            "task_id": task_id,
            "assignment_nonce": assignment_nonce,
            "sequence": sequence,
            "result": result,
        }
        if not _verify(node.secret, message, signature):
            raise EdgeError("invalid task result signature")

        updated_task = replace(
            task, result=result,
            result_sha256=hashlib.sha256(_canonical(result)).hexdigest(),
            state="SUCCEEDED", lease_until=None, assignment_nonce=None,
        )
        updated_node = replace(
            node, active_tasks=set(node.active_tasks),
            last_result_sequence=sequence,
        )
        updated_node.active_tasks.discard(task_id)
        self._save(nodes=(updated_node,), tasks=(updated_task,))
        self._nodes[node_id] = updated_node
        self._tasks[task_id] = updated_task
        return self.task_status(task_id)

    @_synchronized
    def reap_expired(self) -> dict[str, int]:
        """Expire overdue work and requeue work whose worker lease elapsed."""
        now = self._clock()
        counts = {"expired": 0, "requeued": 0}
        updates: list[_Task] = []
        for task in self._tasks.values():
            if task.state == "QUEUED" and task.deadline <= now:
                updates.append(replace(task, state="EXPIRED"))
                counts["expired"] += 1
            elif task.state in {"ASSIGNED", "RUNNING"} and task.lease_until is not None and task.lease_until <= now:
                if task.deadline <= now:
                    updates.append(replace(
                        task, state="EXPIRED", node_id=None, lease_until=None,
                        assignment_nonce=None,
                    ))
                    counts["expired"] += 1
                else:
                    updates.append(replace(
                        task, state="QUEUED", node_id=None, lease_until=None,
                        assignment_nonce=None,
                    ))
                    counts["requeued"] += 1
        if updates:
            self._save(tasks=updates)
            for updated in updates:
                original = self._tasks[updated.task_id]
                if original.node_id in self._nodes:
                    self._nodes[original.node_id].active_tasks.discard(original.task_id)
                self._tasks[updated.task_id] = updated
        return counts

    @_synchronized
    def node_status(self, node_id: str) -> dict[str, Any]:
        node = self._get_node(node_id)
        now = self._clock()
        return {
            "node_id": node.node_id,
            "protocol_version": self.PROTOCOL_VERSION,
            "capabilities": sorted(node.capabilities),
            "online": self._is_online(node, now),
            "last_seen": node.last_seen,
            "last_heartbeat_sequence": node.last_heartbeat_sequence,
            "last_result_sequence": node.last_result_sequence,
            "active_tasks": sorted(node.active_tasks),
            "max_parallel": node.max_parallel,
            "key_available": True,
        }

    @_synchronized
    def task_status(self, task_id: str) -> dict[str, Any]:
        task = self._get_task(task_id)
        return {
            "task_id": task.task_id, "task_type": task.task_type,
            "protocol_version": self.PROTOCOL_VERSION,
            "required_capabilities": sorted(task.required_capabilities),
            "created_at": task.created_at, "deadline": task.deadline,
            "state": task.state, "node_id": task.node_id,
            "lease_until": task.lease_until,
            "assignment_nonce": task.assignment_nonce,
            "result": task.result, "result_sha256": task.result_sha256,
            "error": task.error,
        }

    @_synchronized
    def snapshot(self) -> dict[str, Any]:
        now = self._clock()
        states: dict[str, int] = {}
        for task in self._tasks.values():
            states[task.state] = states.get(task.state, 0) + 1
        return {
            "component": "nexus_edge_manager",
            "mode": "sqlite_persistent" if self._store is not None else "in_memory_pilot",
            "protocol_version": self.PROTOCOL_VERSION,
            "persistence_enabled": self._store is not None,
            "nodes_total": len(self._nodes),
            "nodes_online": sum(self._is_online(n, now) for n in self._nodes.values()),
            "tasks_total": len(self._tasks),
            "task_states": states,
            "network_io_enabled": False,
            "wallet_access_enabled": False,
            "miner_autostart_enabled": False,
        }

    def close(self) -> None:
        if self._store is not None:
            self._store.close()

    def _is_online(self, node: _Node, now: float) -> bool:
        return node.last_seen is not None and now - node.last_seen <= self.heartbeat_ttl_s

    def _get_node(self, node_id: str) -> _Node:
        try:
            return self._nodes[node_id]
        except KeyError as exc:
            raise EdgeError(f"unknown node: {node_id}") from exc

    def _get_task(self, task_id: str) -> _Task:
        try:
            return self._tasks[task_id]
        except KeyError as exc:
            raise EdgeError(f"unknown task: {task_id}") from exc
