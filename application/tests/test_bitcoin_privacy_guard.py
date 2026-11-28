from modules.bitcoin_privacy_guard import (
    assess_bitcoin_peer_privacy,
    privacy_guard_enabled,
)


def test_guard_is_disabled_by_default():
    assert privacy_guard_enabled({}) is False
    assert privacy_guard_enabled({"NEXUS_BITCOIN_PRIVACY_GUARD": "0"}) is False


def test_guard_requires_explicit_opt_in():
    for value in ("1", "true", "YES", "on"):
        assert privacy_guard_enabled({"NEXUS_BITCOIN_PRIVACY_GUARD": value}) is True


def test_clearnet_transaction_relay_is_flagged_without_exposing_peer_data():
    result = assess_bitcoin_peer_privacy([
        {
            "id": 7, "addr": "203.0.113.9:8333",
            "addrbind": "192.0.2.7:8333", "addrlocal": "198.51.100.8:8333",
            "network": "ipv4", "relaytxes": True, "subver": "/Satoshi:test/",
        },
        {"network": "onion", "relaytxes": True},
    ])
    assert result["status"] == "conditional_clearnet_relay_exposure"
    assert result["severity"] == "elevated"
    assert result["clearnet_peers"] == 1
    assert result["clearnet_tx_relay_peers"] == 1
    assert result["onion_peers"] == 1
    assert result["wallet_state"] == "not_inspected"
    assert result["wallet_broadcast_setting"] == "not_inspected"
    assert result["peer_address_fields_inspected"] is False
    assert result["transaction_data_inspected"] is False
    assert result["peer_addresses_returned"] is False
    assert "203.0.113.9" not in repr(result)
    assert "192.0.2.7" not in repr(result)
    assert "198.51.100.8" not in repr(result)
    assert "Satoshi" not in repr(result)


def test_clearnet_peer_without_transaction_relay_is_not_called_safe():
    result = assess_bitcoin_peer_privacy([{"network": "ipv6", "relaytxes": False}])
    assert result["status"] == "clearnet_peers_without_tx_relay_observed"
    assert result["severity"] == "lower_but_not_safe"


def test_block_relay_only_connection_is_classified_without_guessing():
    result = assess_bitcoin_peer_privacy([
        {"network": "ipv4", "connection_type": "block-relay-only"},
    ])
    assert result["clearnet_non_tx_relay_peers"] == 1
    assert result["clearnet_unknown_relay_peers"] == 0


def test_missing_relay_metadata_fails_closed():
    result = assess_bitcoin_peer_privacy([{"network": "ipv4"}])
    assert result["status"] == "review_required"
    assert result["severity"] == "unknown"
    assert result["clearnet_unknown_relay_peers"] == 1


def test_onion_and_i2p_only_snapshot_does_not_claim_anonymity():
    result = assess_bitcoin_peer_privacy([
        {"network": "onion", "relaytxes": True},
        {"network": "i2p", "relaytxes": True},
    ])
    assert result["status"] == "no_clearnet_peers_observed"
    assert result["severity"] == "lower_but_not_safe"
    assert "not a guarantee" in " ".join(result["limitations"]).lower()


def test_empty_or_malformed_peer_rows_produce_unknown():
    assert assess_bitcoin_peer_privacy([])["status"] == "no_peer_evidence"
    assert assess_bitcoin_peer_privacy(None)["status"] == "insufficient_peer_data"
    assert assess_bitcoin_peer_privacy([None, 42])["status"] == "no_peer_evidence"


def test_only_aggregate_metadata_is_returned():
    result = assess_bitcoin_peer_privacy([
        {"network": "ipv4", "relaytxes": True, "addr": "203.0.113.10:8333"},
        {"network": "ipv4", "relaytxes": False, "addr": "203.0.113.11:8333"},
        {"network": "cjdns", "relaytxes": False, "addr": "fd00::1"},
    ])
    assert set(result).isdisjoint({"addr", "addrbind", "addrlocal", "id", "subver"})
    assert "203.0.113.10" not in repr(result)
    assert "203.0.113.11" not in repr(result)
    assert "fd00::1" not in repr(result)
