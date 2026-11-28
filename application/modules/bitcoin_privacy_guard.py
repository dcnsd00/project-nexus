"""Read-only Bitcoin peer-topology privacy assessment.

This module is intentionally pure: it consumes already-observed getpeerinfo
metadata and never connects to Bitcoin Core, reads wallet state, or changes
network settings. Raw peer records must not be returned or persisted.
"""
from __future__ import annotations

import os
from typing import Any, Mapping


_TRUE_VALUES = frozenset({"1", "true", "yes", "on"})
_CLEARNET_NETWORKS = frozenset({"ipv4", "ipv6"})


def privacy_guard_enabled(environ: Mapping[str, str] | None = None) -> bool:
    """Return whether the optional monitor is explicitly enabled."""
    source = os.environ if environ is None else environ
    return str(source.get("NEXUS_BITCOIN_PRIVACY_GUARD", "")).strip().lower() in _TRUE_VALUES


def _relay_state(peer: Mapping[str, Any]) -> bool | None:
    value = peer.get("relaytxes")
    if isinstance(value, bool):
        return value
    if str(peer.get("connection_type", "")).strip().lower() == "block-relay-only":
        return False
    return None


def assess_bitcoin_peer_privacy(peer_rows: Any) -> dict[str, Any]:
    """Summarize clearnet transaction-relay exposure without exposing peers.

    Only aggregate-safe network and relay fields are inspected. Peer addresses,
    IDs, user agents, wallet records and transaction data are ignored.
    """
    if not isinstance(peer_rows, list):
        return {
            "status": "insufficient_peer_data", "severity": "unknown",
            "observed_peer_count": 0, "clearnet_peers": 0,
            "clearnet_tx_relay_peers": 0, "clearnet_non_tx_relay_peers": 0,
            "clearnet_unknown_relay_peers": 0, "onion_peers": 0, "i2p_peers": 0,
            "other_network_peers": 0, "unknown_network_peers": 0,
            "wallet_state": "not_inspected", "wallet_broadcast_setting": "not_inspected",
            "peer_address_fields_inspected": False,
            "transaction_data_inspected": False, "peer_addresses_returned": False,
            "actions_taken": [],
            "finding": "Bitcoin Core peer metadata was unavailable or malformed.",
        }

    counts = {
        "clearnet_peers": 0, "clearnet_tx_relay_peers": 0,
        "clearnet_non_tx_relay_peers": 0, "clearnet_unknown_relay_peers": 0,
        "onion_peers": 0, "i2p_peers": 0, "other_network_peers": 0,
        "unknown_network_peers": 0,
    }
    valid_peer_count = 0

    for row in peer_rows:
        if not isinstance(row, Mapping):
            continue
        valid_peer_count += 1
        network = str(row.get("network", "")).strip().lower()
        if network in _CLEARNET_NETWORKS:
            counts["clearnet_peers"] += 1
            relay_state = _relay_state(row)
            if relay_state is True:
                counts["clearnet_tx_relay_peers"] += 1
            elif relay_state is False:
                counts["clearnet_non_tx_relay_peers"] += 1
            else:
                counts["clearnet_unknown_relay_peers"] += 1
        elif network == "onion":
            counts["onion_peers"] += 1
        elif network == "i2p":
            counts["i2p_peers"] += 1
        elif network:
            counts["other_network_peers"] += 1
        else:
            counts["unknown_network_peers"] += 1

    if valid_peer_count == 0:
        status, severity = "no_peer_evidence", "unknown"
        finding = "No valid peer metadata was observed; network privacy cannot be assessed."
    elif counts["clearnet_tx_relay_peers"] > 0:
        status, severity = "conditional_clearnet_relay_exposure", "elevated"
        finding = (
            "At least one clearnet peer is marked as transaction-relay capable. "
            "If a Bitcoin Core wallet tracks a previously used address and "
            "rebroadcasts an unconfirmed transaction, a network observer may "
            "be able to correlate that activity with this node."
        )
    elif counts["clearnet_unknown_relay_peers"] > 0 or counts["unknown_network_peers"] > 0:
        status, severity = "review_required", "unknown"
        finding = "Peer metadata is incomplete; clearnet relay exposure cannot be ruled out."
    elif counts["clearnet_peers"] > 0:
        status, severity = "clearnet_peers_without_tx_relay_observed", "lower_but_not_safe"
        finding = (
            "Clearnet peers were observed, but none was marked transaction-relay capable "
            "in this snapshot. This is not proof that the wallet or node is private."
        )
    elif counts["onion_peers"] + counts["i2p_peers"] > 0:
        status, severity = "no_clearnet_peers_observed", "lower_but_not_safe"
        finding = (
            "No IPv4/IPv6 peers were observed in this snapshot. This does not verify "
            "wallet rebroadcast settings, address tracking, historical peer state, "
            "or future network connections."
        )
    else:
        status, severity = "insufficient_peer_evidence", "unknown"
        finding = "The observed peer types are insufficient to establish network privacy."

    return {
        "status": status, "severity": severity,
        "observed_peer_count": valid_peer_count, **counts,
        "wallet_state": "not_inspected",
        "wallet_broadcast_setting": "not_inspected",
        "peer_address_fields_inspected": False,
        "transaction_data_inspected": False,
        "peer_addresses_returned": False,
        "actions_taken": [],
        "finding": finding,
        "limitations": [
            "This is an on-demand snapshot, not continuous monitoring.",
            "Peer network types do not establish the host public IP or full routing path.",
            "Wallet address tracking and wallet rebroadcast configuration are not inspected.",
            "The monitor does not prevent rebroadcasts, enforce Tor/I2P, or change Bitcoin Core settings.",
            "A lower severity is not a guarantee of anonymity or safety.",
        ],
    }
