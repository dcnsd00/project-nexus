"""Opt-in, read-only Bitcoin peer privacy endpoint."""
from __future__ import annotations

from fastapi import APIRouter

from modules.blockchain_node_telemetry import bitcoin_node_snapshot
from modules.bitcoin_privacy_guard import privacy_guard_enabled

router = APIRouter(tags=["bitcoin-privacy"])


@router.get("/api/blockchain/nodes/bitcoin/privacy")
def bitcoin_privacy_guard_status() -> dict:
    """Return aggregate peer-topology findings only; never return raw peer rows."""
    if not privacy_guard_enabled():
        return {"enabled": False, "status": "disabled"}

    snapshot = bitcoin_node_snapshot(include_privacy=True)
    rpc = snapshot.get("rpc") if isinstance(snapshot, dict) else None
    rpc = rpc if isinstance(rpc, dict) else {}
    if rpc.get("status") != "connected":
        return {
            "enabled": True, "read_only": True, "status": "unavailable",
            "rpc_status": rpc.get("status", "unknown"),
            "peer_addresses_returned": False, "actions_taken": [],
        }

    privacy = snapshot.get("privacy")
    if not isinstance(privacy, dict):
        privacy = {
            "status": "assessment_unavailable", "severity": "unknown",
            "finding": "The optional analyzer did not return a result.",
            "wallet_state": "not_inspected",
            "wallet_broadcast_setting": "not_inspected",
            "peer_address_fields_inspected": False,
            "transaction_data_inspected": False,
            "peer_addresses_returned": False, "actions_taken": [],
        }

    network = snapshot.get("network")
    chain = network.get("chain") if isinstance(network, dict) else None
    return {
        "enabled": True, "read_only": True,
        "status": privacy.get("status", "unknown"),
        "sampled_at": snapshot.get("sampled_at"), "chain": chain,
        "assessment": privacy,
        "peer_addresses_returned": False, "actions_taken": [],
    }
