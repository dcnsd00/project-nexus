"""Lifecycle-compatible adapter for the NEXUS EDGE control plane."""
from __future__ import annotations

from typing import Any

from .manager import EdgeManager
from .replay_guard import ReplayGuard


class EdgeService:
    """Optional NEXUS LifecycleManager service with no implicit network activity.

    The existing NEXUS runtime registers this object through a factory.
    Replay protection and an optional encrypted SQLite state store are injected
    by the runtime; transport remains disabled in this local control-plane stage.
    """

    def __init__(self, manager: EdgeManager | None = None, *,
                 replay_guard: ReplayGuard | None = None,
                 store: Any | None = None) -> None:
        if manager is not None and (replay_guard is not None or store is not None):
            raise ValueError("provide either manager or manager dependencies, not both")
        self.manager = manager or EdgeManager(replay_guard=replay_guard, store=store)
        self.initialized = False
        self.started = False

    def initialize(self) -> None:
        self.initialized = True

    def start(self) -> None:
        if not self.initialized:
            raise RuntimeError("NEXUS EDGE must be initialized before start")
        # No broker connection, firmware update, wallet access or miner control.
        self.started = True

    def health_check(self) -> dict[str, Any]:
        if not self.initialized:
            return {"ok": False, "reason": "not_initialized"}
        snapshot = self.manager.snapshot()
        return {
            "ok": self.started,
            "module": "nexus_edge",
            "label": "NEXUS EDGE Manager",
            "details": snapshot,
            "mode": "local_control_plane_no_transport",
        }

    def stop(self) -> None:
        self.started = False

    def shutdown(self) -> None:
        self.started = False
        self.initialized = False
