from pathlib import Path
from types import SimpleNamespace

import pytest

from modules.module_registry import MODULES, build_module_registry


def test_registry_distinguishes_missing_source_from_unregistered_module(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "module.py").write_text("# source", encoding="utf-8")
    modules = (
        {"id": "present", "name": "Present", "paths": ("src/module.py",),
         "route_prefixes": ("/api/present",), "critical": True},
        {"id": "missing", "name": "Missing", "paths": ("missing.py",),
         "route_prefixes": (), "critical": False},
    )
    result = build_module_registry(tmp_path, SimpleNamespace(routes=[]), modules)
    rows = {row["id"]: row for row in result["modules"]}
    assert rows["present"]["state"] == "source_present_not_integrated"
    assert rows["missing"]["state"] == "missing_source"
    assert result["system_operational_verified"] is False


def test_registry_marks_route_registered_but_not_operational(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "module.py").write_text("# source", encoding="utf-8")
    modules = ({"id": "x", "name": "X", "paths": ("src/module.py",),
                "route_prefixes": ("/api/x",), "critical": True},)
    app = SimpleNamespace(routes=[SimpleNamespace(path="/api/x/status")])
    row = build_module_registry(tmp_path, app, modules)["modules"][0]
    assert row["state"] == "route_registered_runtime_unverified"
    assert row["registered_routes"] == ["/api/x/status"]
    assert row["operational_verified"] is False


def test_registry_distinguishes_runtime_registration_from_operational_validation(tmp_path):
    (tmp_path / "nexus_edge").mkdir()
    (tmp_path / "nexus_edge" / "service.py").write_text("# source", encoding="utf-8")
    modules = ({"id": "edge", "name": "EDGE", "paths": ("nexus_edge/service.py",),
                "route_prefixes": (), "runtime_service": "edge_manager", "critical": False},)
    row = build_module_registry(tmp_path, SimpleNamespace(routes=[]), modules,
                                runtime_services={"edge_manager"})["modules"][0]
    assert row["state"] == "runtime_registered_health_unverified"
    assert row["runtime_registered"] is True
    assert row["operational_verified"] is False



def test_default_module_catalog_has_unique_ids_and_correct_earnings_route():
    ids = [item["id"] for item in MODULES]
    assert len(ids) == len(set(ids))

    earnings = [item for item in MODULES if item["id"] == "earnings_intelligence"]
    assert len(earnings) == 1
    assert earnings[0]["route_prefixes"] == ("/api/intel",)


def test_edge_registry_includes_security_persistence_and_transport_sources():
    edge = next(item for item in MODULES if item["id"] == "edge_manager")
    required = {
        "nexus_edge/manager.py",
        "nexus_edge/replay_guard.py",
        "nexus_edge/sqlite_store.py",
        "nexus_edge/gateway.py",
        "nexus_edge/gateway_runtime.py",
        "nexus_edge/runtime.py",
        "nexus_edge/transports.py",
        "nexus_edge/topology.py",
        "nexus_edge/config.py",
        "nexus_edge/rotate_storage_key.py",
    }
    assert required <= set(edge["paths"])
    assert edge["runtime_service"] == "edge_manager"


def test_registry_rejects_duplicate_module_ids(tmp_path):
    (tmp_path / "one.py").write_text("# one", encoding="utf-8")
    modules = (
        {"id": "duplicate", "name": "One", "paths": ("one.py",),
         "route_prefixes": (), "critical": False},
        {"id": "duplicate", "name": "Two", "paths": ("one.py",),
         "route_prefixes": (), "critical": False},
    )
    with pytest.raises(ValueError, match="duplicate module registry id: duplicate"):
        build_module_registry(tmp_path, modules=modules)



def test_puzzle_solver_registry_entry_is_discoverable_without_claiming_operation():
    entry = next(item for item in MODULES if item["id"] == "puzzle_solver")
    assert entry["runtime_service"] == "puzzle_solver"
    assert entry["route_prefixes"] == ("/api/puzzles",)


def test_ai_worker_registry_entry_is_discoverable_without_claiming_operation():
    entry = next(item for item in MODULES if item["id"] == "ai_worker_coordinator")
    assert entry["runtime_service"] == "ai_worker_coordinator"
    assert entry["route_prefixes"] == ("/api/nexus/workers",)


def test_module_registry_ids_remain_unique_after_ai_worker_registration():
    ids = [item["id"] for item in MODULES]
    assert len(ids) == len(set(ids))


def test_public_market_data_module_is_registered_as_route_and_runtime_service():
    market_data = next(item for item in MODULES if item["id"] == "market_data")
    assert market_data["paths"] == ("modules/market_data.py",)
    assert market_data["route_prefixes"] == ("/api/market-data",)
    assert market_data["runtime_service"] == "market_data"
    assert market_data["critical"] is False


def test_rainbowminer_modules_are_registered_without_claiming_live_operation():
    telemetry = next(item for item in MODULES if item["id"] == "rainbowminer_telemetry")
    profit = next(item for item in MODULES if item["id"] == "mining_profit_intelligence")
    assert telemetry["paths"] == ("modules/rainbowminer_telemetry.py",)
    assert telemetry["route_prefixes"] == ("/api/mining/rainbowminer",)
    assert telemetry["runtime_service"] == "rainbowminer_telemetry"
    assert profit["paths"] == ("modules/mining_profit_intelligence.py",)
    assert profit["route_prefixes"] == ("/api/mining/profit-intelligence",)
    assert "runtime_service" not in profit
