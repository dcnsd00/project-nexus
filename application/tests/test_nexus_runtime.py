from modules.nexus_runtime import build_runtime


def test_runtime_registers_local_services_without_starting_them():
    manager = build_runtime()
    snapshot = manager.snapshot()
    names = {row["name"] for row in snapshot["services"]}
    assert {"data_paths", "crypto_engine", "math_intelligence", "provider_registry", "rcsc_research", "research_hub", "mining_switch_controller"} <= names
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
    crypto_details = by_name["crypto_engine"]["health"]["details"]
    assert crypto_details["sha256_self_test"] is True
    assert crypto_details["sha256d_self_test"] is True
    assert {"sha256", "sha256d"} <= set(crypto_details["algorithm_names"])
    assert {"RandomX", "KawPow", "Scrypt", "Ethash"} <= set(crypto_details["pow_algorithms_not_implemented_here"])
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


def test_rcsc_runtime_adapter_is_read_only_and_does_not_initialize_database():
    from modules import rcsc_service

    database = rcsc_service.DB_PATH
    existed_before = database.exists()
    manager = build_runtime()
    snapshot = manager.start_all()
    by_name = {row["name"]: row for row in snapshot["services"]}

    rcsc = by_name["rcsc_research"]["health"]
    assert rcsc["ok"] is True
    assert rcsc["mode"] == "local_read_only_no_schema_mutation_no_provider_access"
    assert rcsc["details"]["database_present"] is existed_before
    assert database.exists() is existed_before
    assert manager.stop_all()["running"] == 0


def test_research_hub_runtime_probe_is_read_only():
    from modules import research_hub

    history_path = research_hub.HISTORY
    existed_before = history_path.exists()
    manager = build_runtime()
    snapshot = manager.start_all()
    by_name = {row["name"]: row for row in snapshot["services"]}

    hub = by_name["research_hub"]["health"]
    assert hub["ok"] is True
    assert hub["details"]["shortcuts_registered"] == len(research_hub.SHORTCUTS)
    assert hub["details"]["external_uploads"] is False
    assert hub["details"]["auto_apply"] is False
    assert history_path.exists() is existed_before
    assert manager.stop_all()["running"] == 0


def test_mining_switch_controller_is_registered_disabled_by_default():
    manager = build_runtime()
    snapshot = manager.start_all()
    by_name = {row["name"]: row for row in snapshot["services"]}
    controller = by_name["mining_switch_controller"]["health"]
    assert controller["ok"] is True
    assert controller["details"]["automatic_switch_enabled"] is False
    assert controller["details"]["minimum_measurement_windows"] == 3
    assert controller["details"]["cooldown_seconds"] == 1800
    assert controller["details"]["source_adapter"]["verified"] is False
    assert controller["details"]["source_adapter"]["providers_live"] == 0
    assert manager.stop_all()["running"] == 0
