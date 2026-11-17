"""Lifecycle-compatible adapter for the NEXUS EDGE control plane."""
from __future__ import annotations

from typing import Any

from .manager import EdgeManager


class EdgeService:
    """Optional NEXUS LifecycleManager service with no implicit network activity.

    Persistence can be injected through EdgeManager. Transport and physical
    device control remain separate explicit integrations.
    """

    def __init__(self, manager: EdgeManager | None = None) -> None:
        self.manager = manager or EdgeManager()
        self.initialized = False
        self.started = False

    def initialize(self) -> None:
        self.initialized = True

    def start(self) -> None:
        if not self.initialized:
            raise RuntimeError("NEXUS EDGE must be initialized before start")
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
        self.manager.close()
