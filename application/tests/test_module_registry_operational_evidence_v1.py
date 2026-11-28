"""Functional-evidence gates for NEXUS module operational verification."""
from fastapi import FastAPI

from modules.module_registry import build_module_registry


def _app_with_route(path):
    app = FastAPI()

    async def health():
        return {"ok": True}

    app.add_api_route(path, health, methods=["GET"])
    return app


def test_source_route_and_runtime_registration_are_not_enough_without_health_evidence(tmp_path):
    (tmp_path / "modules").mkdir()
    (tmp_path / "modules" / "service.py").write_text("VALUE = 1", encoding="utf-8")
    item = {
        "id": "sample",
        "name": "Sample",
        "paths": ("modules/service.py",),
        "route_prefixes": ("/api/sample",),
        "runtime_service": "sample_service",
        "critical": True,
    }
    result = build_module_registry(
        tmp_path,
        _app_with_route("/api/sample"),
        modules=(item,),
        runtime_services=("sample_service",),
    )
    row = result["modules"][0]
    assert row["source_present"] is True
    assert row["runtime_registered"] is True
    assert row["operational_verified"] is False
    assert result["system_operational_verified"] is False
    assert row["verification_reason"] == "runtime_health_missing_or_failed"


def test_module_becomes_operational_only_with_matching_live_health_and_route(tmp_path):
    (tmp_path / "modules").mkdir()
    (tmp_path / "modules" / "service.py").write_text("VALUE = 1", encoding="utf-8")
    item = {
        "id": "sample",
        "name": "Sample",
        "paths": ("modules/service.py",),
        "route_prefixes": ("/api/sample",),
        "runtime_service": "sample_service",
        "critical": True,
    }
    result = build_module_registry(
        tmp_path,
        _app_with_route("/api/sample"),
        modules=(item,),
        runtime_services=("sample_service",),
        runtime_health={"sample_service": {"ok": True, "details": {"self_test": True}}},
    )
    assert result["modules"][0]["operational_verified"] is True
    assert result["operational_verified_modules"] == 1
    assert result["operational_pending_modules"] == 0
    assert result["system_operational_verified"] is True


def test_module_does_not_verify_without_its_required_route_even_when_service_is_healthy(tmp_path):
    (tmp_path / "modules").mkdir()
    (tmp_path / "modules" / "service.py").write_text("VALUE = 1", encoding="utf-8")
    item = {
        "id": "sample",
        "name": "Sample",
        "paths": ("modules/service.py",),
        "route_prefixes": ("/api/sample",),
        "runtime_service": "sample_service",
        "critical": True,
    }
    result = build_module_registry(
        tmp_path,
        _app_with_route("/api/other"),
        modules=(item,),
        runtime_services=("sample_service",),
        runtime_health={"sample_service": {"ok": True}},
    )
    assert result["modules"][0]["operational_verified"] is False


def test_ai_worker_module_requires_live_provider_and_all_eleven_worker_tests(tmp_path):
    (tmp_path / "modules").mkdir()
    (tmp_path / "modules" / "ai_worker_coordinator.py").write_text("VALUE = 1", encoding="utf-8")
    item = {
        "id": "ai_worker_coordinator",
        "name": "NEXUS AI Worker Coordinator",
        "paths": ("modules/ai_worker_coordinator.py",),
        "route_prefixes": ("/api/nexus/workers",),
        "runtime_service": "ai_worker_coordinator",
        "critical": False,
    }
    common = {
        "source_present": True,
        "route_registered": True,
        "runtime_registered": True,
    }
    app = _app_with_route("/api/nexus/workers")
    health = {
        "ok": True,
        "details": {
            "provider_live_verified": True,
            "worker_self_test": {
                "operational_verified": True,
                "workers_tested": 11,
                "workers_passed": 10,
            },
        },
    }
    partial = build_module_registry(
        tmp_path, app, modules=(item,), runtime_services=("ai_worker_coordinator",),
        runtime_health={"ai_worker_coordinator": health},
    )
    assert partial["modules"][0]["operational_verified"] is False
    assert partial["modules"][0]["external_dependencies_verified"] is True
    assert partial["modules"][0]["verification_reason"] == "all_eleven_worker_self_test_required"

    health["details"]["worker_self_test"]["workers_passed"] = 11
    complete = build_module_registry(
        tmp_path, app, modules=(item,), runtime_services=("ai_worker_coordinator",),
        runtime_health={"ai_worker_coordinator": health},
    )
    assert complete["modules"][0]["operational_verified"] is True


def test_integrations_module_requires_all_registered_external_connectors(tmp_path):
    (tmp_path / "modules").mkdir()
    (tmp_path / "modules" / "integration_registry.py").write_text("VALUE = 1", encoding="utf-8")
    item = {
        "id": "integrations",
        "name": "Provider Integrations",
        "paths": ("modules/integration_registry.py",),
        "route_prefixes": ("/api/integrations",),
        "runtime_service": "provider_registry",
        "critical": False,
    }
    app = _app_with_route("/api/integrations")
    health = {
        "ok": True,
        "details": {
            "providers_catalogued": 12,
            "live_connections_verified": 11,
        },
    }
    partial = build_module_registry(
        tmp_path, app, modules=(item,), runtime_services=("provider_registry",),
        runtime_health={"provider_registry": health},
    )
    assert partial["modules"][0]["operational_verified"] is False
    assert partial["modules"][0]["external_dependencies_verified"] is False

    health["details"]["live_connections_verified"] = 12
    complete = build_module_registry(
        tmp_path, app, modules=(item,), runtime_services=("provider_registry",),
        runtime_health={"provider_registry": health},
    )
    assert complete["modules"][0]["operational_verified"] is True
    assert complete["system_operational_verified"] is True
