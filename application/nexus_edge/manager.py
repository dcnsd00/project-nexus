"""Small, transport-agnostic NEXUS EDGE control plane.

This first increment is an in-memory reference implementation. It deliberately
does not open sockets, execute arbitrary commands, access wallets, or start
miners. A transport adapter (MQTT/HTTPS) and durable store are separate layers.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import math
import re
import threading
import time
from functools import wraps
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable

from .replay_guard import MemoryReplayGuard, ReplayGuard



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



def _validate_timestamp(value: Any) -> float:
    """Require a finite JSON number for signed protocol timestamps."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise EdgeError("timestamp must be a finite number")
    result = float(value)
    if not math.isfinite(result):
        raise EdgeError("timestamp must be a finite number")
    return result

def _verify(secret: bytes, message: Any, signature: str) -> bool:
    if not isinstance(signature, str):
        return False
    expected = sign_message(secret, message)
    return hmac.compare_digest(expected, signature.lower())


@dataclass
class _Node:
    node_id: str
    capabilities: frozenset[str]
    secret: bytes = field(repr=False)
    max_parallel: int = 1
    last_seen: float | None = None
    active_tasks: set[str] = field(default_factory=set)


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
    result: Any = None
    result_sha256: str | None = None
    error: str | None = None


def _synchronized(method):
    """Serialize manager operations within this process; SQLite handles DB transactions."""
    @wraps(method)
    def wrapped(self, *args, **kwargs):
        with self._lock:
            return method(self, *args, **kwargs)
    return wrapped


class EdgeManager:
    """In-memory scheduler, node registry, lease manager and result verifier."""

    def __init__(
        self,
        *,
        heartbeat_ttl_s: int = 90,
        lease_s: int = 60,
        max_payload_bytes: int = 65_536,
        clock: Callable[[], float] = time.time,
        replay_guard: ReplayGuard | None = None,
        store: Any | None = None,
    ) -> None:
        if heartbeat_ttl_s < 1 or lease_s < 1 or max_payload_bytes < 128:
            raise EdgeError("invalid EDGE manager limits")
        self._lock = threading.RLock()
        self.heartbeat_ttl_s = heartbeat_ttl_s
        self.lease_s = lease_s
        self.max_payload_bytes = max_payload_bytes
        self._clock = clock
        self._replay_guard = replay_guard or MemoryReplayGuard()
        self._store = store
        self._nodes: dict[str, _Node] = {}
        self._tasks: dict[str, _Task] = {}
        if self._store is not None:
            self._restore(self._store.load_state())
            self.reap_expired()

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
        self._nodes[node_id] = _Node(node_id, caps, secret, max_parallel)
        self._persist()
        return self.node_status(node_id)

    @_synchronized
    def rotate_node_secret(self, node_id: str, new_secret: bytes) -> dict[str, Any]:
        """Replace a node credential without resetting its anti-replay sequence."""
        node = self._get_node(node_id)
        if not isinstance(new_secret, bytes) or len(new_secret) < 32:
            raise EdgeError("node secret must contain at least 32 bytes")
        if hmac.compare_digest(node.secret, new_secret):
            raise EdgeError("new node secret must differ from the current secret")
        node.secret = new_secret
        self._persist()
        return self.node_status(node_id)

    @_synchronized
    def next_node_sequence(self, node_id: str) -> int:
        """Return the minimum next outbound sequence required for this node."""
        self._get_node(node_id)
        return self._replay_guard.last_accepted_sequence(node_id) + 1

    @_synchronized
    def revoke_node(self, node_id: str) -> dict[str, Any]:
        """Revoke a node and safely requeue its unfinished work.

        The replay-guard sequence is deliberately retained so re-provisioning
        the same node ID cannot reset its anti-replay counter.
        """
        self._get_node(node_id)
        now = self._clock()
        counts = {"requeued_tasks": 0, "expired_tasks": 0}
        for task in self._tasks.values():
            if task.node_id != node_id or task.state not in {"ASSIGNED", "RUNNING"}:
                continue
            if task.deadline <= now:
                task.state = "EXPIRED"
                counts["expired_tasks"] += 1
            else:
                task.state = "QUEUED"
                counts["requeued_tasks"] += 1
            task.node_id = None
            task.lease_until = None
        del self._nodes[node_id]
        self._persist()
        return {"node_id": node_id, "revoked": True, **counts}

    @_synchronized
    def heartbeat(self, node_id: str, timestamp: float, sequence: int, signature: str) -> dict[str, Any]:
        node = self._get_node(node_id)
        now = self._clock()
        timestamp_value = _validate_timestamp(timestamp)
        if abs(now - timestamp_value) > self.heartbeat_ttl_s:
            raise EdgeError("heartbeat timestamp outside allowed clock-skew window")
        message = {"kind": "heartbeat", "node_id": node_id, "timestamp": timestamp, "sequence": sequence}
        if not _verify(node.secret, message, signature):
            raise EdgeError("invalid heartbeat signature")
        try:
            self._replay_guard.accept(node_id, sequence)
        except ValueError as exc:
            raise EdgeError(str(exc)) from exc
        node.last_seen = now
        self._persist()
        return self.node_status(node_id)

    @_synchronized
    def authenticate_request(
        self, node_id: str, action: str, timestamp: float, sequence: int,
        payload: Any, signature: str,
    ) -> None:
        """Authenticate and anti-replay-protect a node-originated control request."""
        node = self._get_node(node_id)
        now = self._clock()
        timestamp_value = _validate_timestamp(timestamp)
        if abs(now - timestamp_value) > self.heartbeat_ttl_s:
            raise EdgeError("request timestamp outside allowed clock-skew window")
        if not isinstance(action, str) or not re.fullmatch(r"[a-z][a-z0-9_.-]{1,63}", action):
            raise EdgeError("invalid request action")
        if not isinstance(payload, dict):
            raise EdgeError("node request payload must be a JSON object")
        if len(_canonical(payload)) > self.max_payload_bytes:
            raise EdgeError("node request payload exceeds configured size limit")
        message = {"kind": "node_request", "action": action, "node_id": node_id,
                   "timestamp": timestamp, "sequence": sequence, "payload": payload}
        if not _verify(node.secret, message, signature):
            raise EdgeError("invalid node request signature")
        try:
            self._replay_guard.accept(node_id, sequence)
        except ValueError as exc:
            raise EdgeError(str(exc)) from exc

    @_synchronized
    def record_authenticated_heartbeat(self, node_id: str, timestamp: float) -> dict[str, Any]:
        """Update liveness after the transport has authenticated and replay-checked a request."""
        node = self._get_node(node_id)
        now = self._clock()
        timestamp_value = _validate_timestamp(timestamp)
        if abs(now - timestamp_value) > self.heartbeat_ttl_s:
            raise EdgeError("heartbeat timestamp outside allowed clock-skew window")
        node.last_seen = now
        self._persist()
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
        self._tasks[identifier] = task
        self._persist()
        return self.task_status(identifier)

    @_synchronized
    def claim_task(self, node_id: str) -> dict[str, Any] | None:
        node = self._get_node(node_id)
        now = self._clock()
        if not self._is_online(node, now):
            raise EdgeError("node is offline or has not sent an authenticated heartbeat")
        if len(node.active_tasks) >= node.max_parallel:
            return None
        expired_changed = False
        for task in self._tasks.values():
            if task.state == "QUEUED" and task.deadline <= now:
                task.state = "EXPIRED"
                expired_changed = True
            if task.state != "QUEUED" or not task.required_capabilities.issubset(node.capabilities):
                continue
            task.state = "ASSIGNED"
            task.node_id = node_id
            task.lease_until = min(task.deadline, now + self.lease_s)
            node.active_tasks.add(task.task_id)
            self._persist()
            return self.task_status(task.task_id)
        if expired_changed:
            self._persist()
        return None

    @_synchronized
    def start_task(self, node_id: str, task_id: str) -> dict[str, Any]:
        task = self._get_task(task_id)
        if task.node_id != node_id or task.state != "ASSIGNED":
            raise EdgeError("task is not assigned to this node")
        if task.lease_until is None or task.lease_until <= self._clock():
            raise EdgeError("task lease expired")
        task.state = "RUNNING"
        self._persist()
        return self.task_status(task_id)

    @_synchronized
    def complete_task(
        self, node_id: str, task_id: str, result: Any, signature: str,
    ) -> dict[str, Any]:
        node = self._get_node(node_id)
        task = self._get_task(task_id)
        if task.node_id != node_id or task.state != "RUNNING":
            raise EdgeError("task is not running on this node")
        now = self._clock()
        if task.lease_until is None or task.lease_until <= now or task.deadline <= now:
            raise EdgeError("task lease or deadline expired")
        if len(_canonical(result)) > self.max_payload_bytes:
            raise EdgeError("task result exceeds configured size limit")
        message = {"kind": "task_result", "node_id": node_id,
                   "task_id": task_id, "result": result}
        if not _verify(node.secret, message, signature):
            raise EdgeError("invalid task result signature")
        task.result = result
        task.result_sha256 = hashlib.sha256(_canonical(result)).hexdigest()
        task.state = "SUCCEEDED"
        task.lease_until = None
        node.active_tasks.discard(task_id)
        self._persist()
        return self.task_status(task_id)

    @_synchronized
    def reap_expired(self) -> dict[str, int]:
        """Expire overdue work and requeue work whose worker lease elapsed."""
        now = self._clock()
        counts = {"expired": 0, "requeued": 0}
        for task in self._tasks.values():
            if task.state in {"QUEUED", "ASSIGNED", "RUNNING"} and task.deadline <= now:
                if task.node_id in self._nodes:
                    self._nodes[task.node_id].active_tasks.discard(task.task_id)
                task.state = "EXPIRED"
                task.node_id = None
                task.lease_until = None
                counts["expired"] += 1
            elif task.state in {"ASSIGNED", "RUNNING"} and task.lease_until is not None and task.lease_until <= now:
                if task.node_id in self._nodes:
                    self._nodes[task.node_id].active_tasks.discard(task.task_id)
                task.state = "QUEUED"
                task.node_id = None
                task.lease_until = None
                counts["requeued"] += 1
        if counts["expired"] or counts["requeued"]:
            self._persist()
        return counts

    @_synchronized
    def list_nodes(self) -> list[dict[str, Any]]:
        """Return operator-safe node status without exposing authentication secrets."""
        return [self.node_status(node_id) for node_id in sorted(self._nodes)]

    @_synchronized
    def list_tasks(self) -> list[dict[str, Any]]:
        """Return operator-safe task status without payloads or raw results."""
        rows = [
            self.task_status(task_id)
            for task_id in sorted(
                self._tasks,
                key=lambda item: (self._tasks[item].created_at, item),
            )
        ]
        for row in rows:
            row["result_available"] = row.pop("result") is not None
        return rows

    @_synchronized
    def node_status(self, node_id: str) -> dict[str, Any]:
        node = self._get_node(node_id)
        now = self._clock()
        return {
            "node_id": node.node_id,
            "capabilities": sorted(node.capabilities),
            "online": self._is_online(node, now),
            "last_seen": node.last_seen,
            "active_tasks": sorted(node.active_tasks),
            "max_parallel": node.max_parallel,
        }

    @_synchronized
    def task_status(self, task_id: str) -> dict[str, Any]:
        task = self._get_task(task_id)
        return {
            "task_id": task.task_id, "task_type": task.task_type,
            "required_capabilities": sorted(task.required_capabilities),
            "created_at": task.created_at, "deadline": task.deadline,
            "state": task.state, "node_id": task.node_id,
            "lease_until": task.lease_until, "result": task.result,
            "result_sha256": task.result_sha256, "error": task.error,
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
            "nodes_total": len(self._nodes),
            "nodes_online": sum(self._is_online(n, now) for n in self._nodes.values()),
            "tasks_total": len(self._tasks),
            "task_states": states,
            "network_io_enabled": False,
            "wallet_access_enabled": False,
            "miner_autostart_enabled": False,
        }

    def _persist(self) -> None:
        if self._store is None:
            return
        try:
            self._store.save_state(
                nodes=[{
                    "node_id": node.node_id,
                    "capabilities": sorted(node.capabilities),
                    "secret": node.secret,
                    "max_parallel": node.max_parallel,
                    "last_seen": node.last_seen,
                } for node in self._nodes.values()],
                tasks=[{
                    "task_id": task.task_id,
                    "task_type": task.task_type,
                    "payload": task.payload,
                    "required_capabilities": sorted(task.required_capabilities),
                    "created_at": task.created_at,
                    "deadline": task.deadline,
                    "state": task.state,
                    "node_id": task.node_id,
                    "lease_until": task.lease_until,
                    "result": task.result,
                    "result_sha256": task.result_sha256,
                    "error": task.error,
                } for task in self._tasks.values()],
            )
        except Exception:
            # Manager methods mutate their in-memory objects before persisting.
            # Reconcile from the last committed snapshot so a failed write does
            # not leave this process reporting state that SQLite never accepted.
            try:
                persisted_state = self._store.load_state()
                self._nodes.clear()
                self._tasks.clear()
                self._restore(persisted_state)
            except Exception as recovery_error:
                raise RuntimeError(
                    "EDGE persistence failed and in-memory state could not be reconciled"
                ) from recovery_error
            raise

    def _restore(self, state: dict[str, Any]) -> None:
        for item in state.get("nodes", []):
            node = _Node(
                item["node_id"], frozenset(item["capabilities"]), item["secret"],
                int(item["max_parallel"]), item.get("last_seen"), set(),
            )
            self._nodes[node.node_id] = node
        for item in state.get("tasks", []):
            task = _Task(
                task_id=item["task_id"], task_type=item["task_type"],
                payload=item["payload"],
                required_capabilities=frozenset(item["required_capabilities"]),
                created_at=float(item["created_at"]), deadline=float(item["deadline"]),
                state=item["state"], node_id=item.get("node_id"),
                lease_until=item.get("lease_until"), result=item.get("result"),
                result_sha256=item.get("result_sha256"), error=item.get("error"),
            )
            self._tasks[task.task_id] = task
            if task.state in {"ASSIGNED", "RUNNING"} and task.node_id in self._nodes:
                self._nodes[task.node_id].active_tasks.add(task.task_id)

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
