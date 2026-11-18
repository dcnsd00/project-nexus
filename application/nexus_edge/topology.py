"""NEXUS multi-server deployment topology validation."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class DeploymentMode(str, Enum):
    SINGLE = "single"
    PRIMARY_STANDBY = "primary_standby"
    ACTIVE_ACTIVE = "active_active"


@dataclass(frozen=True)
class DeploymentTopology:
    mode: DeploymentMode
    server_count: int
    state_backend: str
    shared_state: bool = False
    distributed_task_claims: bool = False

    def validate(self) -> None:
        if not isinstance(self.server_count, int) or isinstance(self.server_count, bool) or self.server_count < 1:
            raise ValueError("server_count must be a positive integer")
        if not isinstance(self.state_backend, str) or not self.state_backend.strip():
            raise ValueError("state_backend must be explicitly configured")
        if self.mode == DeploymentMode.SINGLE:
            if self.server_count != 1:
                raise ValueError("single mode requires exactly one server")
            if self.state_backend.lower() not in {"sqlite", "local_sqlite"}:
                raise ValueError("single-server EDGE currently implements only the local SQLite state backend")
            return
        if self.server_count < 2:
            raise ValueError("multi-server mode requires at least two servers")
        if self.mode == DeploymentMode.PRIMARY_STANDBY:
            if self.server_count != 2:
                raise ValueError("initial primary-standby topology is exactly two servers")
            if self.state_backend.lower() in {"sqlite", "local_sqlite"}:
                raise ValueError("two-server failover requires replicated/shared state; local SQLite is not sufficient")
            if not self.shared_state:
                raise ValueError("primary-standby requires a configured shared or replicated state backend")
            raise ValueError(
                "primary-standby deployment is not implemented; shared database "
                "adapter, fencing, and failover orchestration are not available"
            )
        if self.mode == DeploymentMode.ACTIVE_ACTIVE:
            if self.state_backend.lower() in {"sqlite", "local_sqlite"}:
                raise ValueError("active-active requires a shared transactional database, not local SQLite")
            if not self.shared_state or not self.distributed_task_claims:
                raise ValueError("active-active requires shared state and distributed atomic task claims")
            raise ValueError(
                "active-active deployment is not implemented; distributed atomic "
                "task claims and leader/fencing coordination are not available"
            )
        raise ValueError(f"unsupported deployment mode: {self.mode}")


def topology_from_env(env: dict[str, str]) -> DeploymentTopology:
    mode = DeploymentMode(env.get("NEXUS_DEPLOYMENT_MODE", "single"))
    topology = DeploymentTopology(
        mode=mode,
        server_count=int(env.get("NEXUS_SERVER_COUNT", "1")),
        state_backend=env.get("NEXUS_STATE_BACKEND", "sqlite"),
        shared_state=env.get("NEXUS_SHARED_STATE", "false").lower() == "true",
        distributed_task_claims=env.get("NEXUS_DISTRIBUTED_TASK_CLAIMS", "false").lower() == "true",
    )
    topology.validate()
    return topology
