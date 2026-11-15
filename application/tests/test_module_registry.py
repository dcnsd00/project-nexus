from pathlib import Path
from types import SimpleNamespace

from modules.module_registry import build_module_registry


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
