from modules.nexus_runtime import build_runtime


def test_runtime_registers_local_services_without_starting_them():
    manager = build_runtime()
    snapshot = manager.snapshot()
    names = {row["name"] for row in snapshot["services"]}
    assert {"data_paths", "crypto_engine", "math_intelligence", "provider_registry"} <= names
    assert snapshot["running"] == 0
    assert snapshot["system_ready"] is False


def test_runtime_starts_only_local_read_only_adapters():
    manager = build_runtime()
    snapshot = manager.start_all()
    assert snapshot["system_ready"] is True
    assert snapshot["running"] == snapshot["total"]
    by_name = {row["name"]: row for row in snapshot["services"]}
    assert by_name["data_paths"]["health"]["ok"] is True
    data_health = by_name["data_paths"]["health"]["details"]
    assert data_health["data_root"]
    assert data_health["filesystem_created_by_probe"] is False
    assert by_name["crypto_engine"]["health"]["ok"] is True
    assert by_name["provider_registry"]["health"]["details"]["live_connections_verified"] == 0
    assert by_name["provider_registry"]["health"]["details"]["writes_enabled"] is False
    assert manager.stop_all()["running"] == 0


def test_runtime_registers_wallet_and_mining_supervisor_without_starting_workers():
    manager = build_runtime()
    names = {row["name"] for row in manager.snapshot()["services"]}
    assert {"wallet_engine", "mining_supervisor"} <= names
    assert manager.snapshot()["running"] == 0


def test_wallet_and_mining_adapters_are_read_only_and_do_not_autostart(tmp_path):
    manager = build_runtime()
    snapshot = manager.start_all()
    by_name = {row["name"]: row for row in snapshot["services"]}

    wallet = by_name["wallet_engine"]["health"]
    assert wallet["ok"] is True
    assert wallet["mode"] == "local_read_only_no_unlock_no_schema_mutation"
    assert wallet["details"]["vaults_or_keys_opened"] is False

    mining = by_name["mining_supervisor"]["health"]
    assert mining["ok"] is True
    assert mining["mode"] == "status_only_no_mining_autostart"
    assert mining["details"]["workers_started_by_runtime"] is False
    assert set(mining["details"]["engine_states"].values()) == {"stopped"}

    assert manager.stop_all()["running"] == 0
