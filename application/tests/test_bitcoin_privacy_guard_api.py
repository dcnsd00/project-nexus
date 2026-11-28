from modules import bitcoin_privacy_guard_api as api


def test_endpoint_is_disabled_without_explicit_feature_flag(monkeypatch):
    monkeypatch.setattr(api, "privacy_guard_enabled", lambda: False)
    monkeypatch.setattr(
        api, "bitcoin_node_snapshot",
        lambda **kwargs: (_ for _ in ()).throw(AssertionError("RPC must not be called")),
    )

    assert api.bitcoin_privacy_guard_status() == {
        "enabled": False,
        "status": "disabled",
    }


def test_endpoint_returns_only_aggregate_privacy_assessment(monkeypatch):
    assessment = {
        "status": "conditional_clearnet_relay_exposure",
        "severity": "elevated",
        "clearnet_tx_relay_peers": 1,
        "wallet_state": "not_inspected",
        "wallet_broadcast_setting": "not_inspected",
        "peer_address_fields_inspected": False,
        "transaction_data_inspected": False,
        "peer_addresses_returned": False,
        "actions_taken": [],
    }
    snapshot = {
        "sampled_at": 123.0,
        "rpc": {"status": "connected"},
        "network": {"chain": "main"},
        "privacy": assessment,
        # The API must not surface accidental extra/raw fields from a source.
        "raw_peer_rows": [{"addr": "203.0.113.10:8333"}],
    }
    calls = []
    monkeypatch.setattr(api, "privacy_guard_enabled", lambda: True)
    monkeypatch.setattr(
        api, "bitcoin_node_snapshot",
        lambda **kwargs: calls.append(kwargs) or snapshot,
    )

    result = api.bitcoin_privacy_guard_status()

    assert calls == [{"include_privacy": True}]
    assert result["enabled"] is True
    assert result["read_only"] is True
    assert result["chain"] == "main"
    assert result["assessment"] == assessment
    assert "raw_peer_rows" not in result
    assert "203.0.113.10" not in repr(result)


def test_endpoint_does_not_disclose_rpc_error_details(monkeypatch):
    monkeypatch.setattr(api, "privacy_guard_enabled", lambda: True)
    monkeypatch.setattr(
        api,
        "bitcoin_node_snapshot",
        lambda **kwargs: {
            "rpc": {
                "status": "blocked_non_loopback_endpoint",
                "endpoint": "http://203.0.113.10:8332",
                "error": "sensitive endpoint detail",
            }
        },
    )

    result = api.bitcoin_privacy_guard_status()

    assert result["status"] == "unavailable"
    assert result["rpc_status"] == "blocked_non_loopback_endpoint"
    assert "endpoint" not in result
    assert "error" not in result
    assert "203.0.113.10" not in repr(result)
