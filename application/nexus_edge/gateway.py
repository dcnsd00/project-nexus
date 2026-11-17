"""Opt-in HTTPS gateway factory for NEXUS EDGE.

Deploy behind a TLS terminator. The gateway does not start miners, execute
shell commands, unlock wallets, or broadcast blockchain transactions.
"""
from __future__ import annotations

import base64
import hmac
import os
import secrets
from typing import Any

from fastapi import APIRouter, FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

from .manager import EdgeError, EdgeManager, sign_message
from .replay_guard import SQLiteReplayGuard
from .sqlite_store import SQLiteEdgeStore
from .transports import transport_matrix


class ProvisionRequest(BaseModel):
    node_id: str = Field(min_length=3, max_length=64, pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{2,63}$")
    capabilities: list[str] = Field(min_length=1, max_length=32)
    max_parallel: int = Field(default=1, ge=1, le=64)


class TaskRequest(BaseModel):
    task_type: str = Field(min_length=2, max_length=64)
    payload: dict[str, Any]
    required_capabilities: list[str] = Field(min_length=1, max_length=32)
    ttl_s: int = Field(default=300, ge=1, le=86400)


class NodeEnvelope(BaseModel):
    timestamp: int
    sequence: int = Field(ge=1)
    payload: dict[str, Any] = Field(default_factory=dict)
    signature: str = Field(min_length=64, max_length=64, pattern=r"^[0-9a-fA-F]{64}$")


def create_edge_manager_from_env(env: dict[str, str] | None = None) -> EdgeManager:
    """Create durable gateway state; fail closed if encryption key is absent."""
    values = os.environ if env is None else env
    key = values.get("NEXUS_EDGE_STORAGE_KEY")
    if not key:
        raise RuntimeError("NEXUS_EDGE_STORAGE_KEY is required for online EDGE gateway")
    database = values.get("NEXUS_EDGE_DATABASE", "./data/db/edge_state.sqlite3")
    try:
        key_bytes = key.encode("ascii")
    except UnicodeEncodeError as exc:
        raise RuntimeError("NEXUS_EDGE_STORAGE_KEY must be a Fernet URL-safe base64 key") from exc
    store = SQLiteEdgeStore(database, encryption_key=key_bytes)
    replay = SQLiteReplayGuard(database)
    return EdgeManager(store=store, replay_guard=replay)


def create_edge_app(manager: EdgeManager | None = None, *,
                    provisioning_token: str | None = None,
                    env: dict[str, str] | None = None) -> FastAPI:
    values = os.environ if env is None else env
    token = provisioning_token if provisioning_token is not None else values.get("NEXUS_EDGE_PROVISIONING_TOKEN")
    if not token or len(token) < 32:
        raise RuntimeError("NEXUS_EDGE_PROVISIONING_TOKEN must contain at least 32 characters")
    edge = manager or create_edge_manager_from_env(dict(values))
    app = FastAPI(title="NEXUS EDGE Gateway", version="1.0.0")
    router = APIRouter(prefix="/v1/edge", tags=["NEXUS EDGE"])

    def require_operator(authorization: str | None) -> None:
        supplied = authorization.removeprefix("Bearer ").strip() if authorization else ""
        if not hmac.compare_digest(supplied, token):
            raise HTTPException(status_code=401, detail="operator authentication failed")

    def authenticate(node_id: str, action: str, envelope: NodeEnvelope) -> None:
        try:
            edge.authenticate_request(node_id, action, envelope.timestamp,
                                      envelope.sequence, envelope.payload,
                                      envelope.signature)
        except EdgeError as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc

    @router.get("/transports")
    def transports():
        return {
            "network_paths": transport_matrix(),
            "https_gateway": "active_in_this_process",
            "mqtts": "adapter_available_opt_in_not_started",
            "lorawan_webhook": "authenticated_ingress_available_network_server_not_configured",
            "iot_webhook": "authenticated_ingress_available_device_adapter_not_configured",
            "lan_wan_mobile_data": "same_https_api_over_ip_when_routing_tls_and_firewall_are_configured",
        }

    @router.get("/health")
    def health():
        snapshot = edge.snapshot()
        return {"ok": True, "transport": "https_gateway_requires_tls_terminator",
                "network_io_enabled": True, "wallet_access_enabled": False,
                "miner_autostart_enabled": False, "snapshot": snapshot}

    @router.post("/nodes/provision")
    def provision(body: ProvisionRequest, authorization: str | None = Header(default=None)):
        require_operator(authorization)
        secret = secrets.token_bytes(32)
        try:
            node = edge.register_node(body.node_id, body.capabilities, secret,
                                      max_parallel=body.max_parallel)
        except EdgeError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        # Returned once. The operator must deliver it to the physical node over
        # a separately authenticated provisioning channel.
        return {"node": node, "node_secret_b64url": base64.urlsafe_b64encode(secret).decode("ascii"),
                "secret_delivery": "one_time_response_operator_must_provision_securely"}

    @router.post("/tasks")
    def submit_task(body: TaskRequest, authorization: str | None = Header(default=None)):
        require_operator(authorization)
        try:
            return edge.submit_task(body.task_type, body.payload,
                                    body.required_capabilities, ttl_s=body.ttl_s)
        except EdgeError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.post("/nodes/{node_id}/uplink/{network}")
    def uplink(node_id: str, network: str, body: NodeEnvelope):
        if network not in {"lorawan", "iot"}:
            raise HTTPException(status_code=404, detail="unsupported uplink network")
        try:
            authenticate(node_id, f"{network}.uplink", body)
        except HTTPException:
            raise
        return {"accepted": True, "node_id": node_id, "network": network,
                "payload": body.payload, "note": "application payload authenticated; decoder/NS adapter is deployment-specific"}

    @router.post("/nodes/{node_id}/heartbeat")
    def heartbeat(node_id: str, body: NodeEnvelope):
        if body.payload:
            raise HTTPException(status_code=400, detail="heartbeat payload must be empty")
        authenticate(node_id, "heartbeat", body)
        # authenticate_request consumed the sequence; heartbeat() has its own
        # replay check, so this endpoint updates liveness without a second check.
        try:
            return edge.record_authenticated_heartbeat(node_id, body.timestamp)
        except EdgeError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.post("/nodes/{node_id}/claim")
    def claim(node_id: str, body: NodeEnvelope):
        if body.payload:
            raise HTTPException(status_code=400, detail="claim payload must be empty")
        authenticate(node_id, "claim_task", body)
        try:
            return {"task": edge.claim_task(node_id)}
        except EdgeError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.post("/nodes/{node_id}/tasks/{task_id}/start")
    def start(node_id: str, task_id: str, body: NodeEnvelope):
        if body.payload != {"task_id": task_id}:
            raise HTTPException(status_code=400, detail="signed payload must contain this task_id")
        authenticate(node_id, "start_task", body)
        try:
            return edge.start_task(node_id, task_id)
        except EdgeError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.post("/nodes/{node_id}/tasks/{task_id}/complete")
    def complete(node_id: str, task_id: str, body: NodeEnvelope):
        required = {"task_id", "result", "result_signature"}
        if set(body.payload) != required or body.payload.get("task_id") != task_id:
            raise HTTPException(status_code=400, detail="signed payload must contain task_id, result, and result_signature")
        authenticate(node_id, "complete_task", body)
        try:
            return edge.complete_task(node_id, task_id, body.payload["result"],
                                      body.payload["result_signature"])
        except EdgeError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    app.include_router(router)
    app.state.edge_manager = edge
    return app
