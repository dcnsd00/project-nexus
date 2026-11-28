"""NEXUS module inventory and runtime integration evidence.

The registry deliberately distinguishes source presence from runtime route
registration. It never reports a module as operational merely because files exist.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable, Mapping

MODULES: tuple[dict[str, Any], ...] = (
    {"id": "core", "name": "NEXUS Core", "paths": ("core/PROJECT-NEXUS-LOCAL/app/main.py",), "route_prefixes": ("/api/nexus",), "critical": True},
    {"id": "wallet", "name": "Wallet Engine", "paths": ("modules/wallet_benchmark/nexus_wallet_manager.py",), "route_prefixes": ("/api/wallet",), "runtime_service": "wallet_engine", "critical": True},
    {"id": "mining_supervisor", "name": "Hybrid Mining Supervisor", "paths": ("mining/hybrid_supervisor.py", "mining/hybrid_orchestrator.py"), "route_prefixes": ("/api/mining",), "runtime_service": "mining_supervisor", "critical": True},
    {"id": "crypto_engine", "name": "Cryptographic Engine", "paths": ("modules/crypto_engine/engine.py",), "route_prefixes": ("/api/crypto",), "runtime_service": "crypto_engine", "critical": True},
    {"id": "rcsc", "name": "RCSC Research", "paths": ("research/rcsc/nexus_rcsc/nexus_rcsc/collector.py", "modules/rcsc_service.py"), "route_prefixes": ("/api/research/rcsc",), "runtime_service": "rcsc_research", "critical": False},
    {"id": "integrations", "name": "Provider Integrations", "paths": ("modules/integration_registry.py",), "route_prefixes": ("/api/integrations",), "runtime_service": "provider_registry", "critical": False},
    {"id": "market_data", "name": "Public Market Data", "paths": ("modules/market_data.py",), "route_prefixes": ("/api/market-data",), "runtime_service": "market_data", "critical": False},
    {"id": "rainbowminer_telemetry", "name": "RainbowMiner Read-only Telemetry", "paths": ("modules/rainbowminer_telemetry.py",), "route_prefixes": ("/api/mining/rainbowminer",), "runtime_service": "rainbowminer_telemetry", "critical": False},
    {"id": "mining_profit_intelligence", "name": "Mining Profit Intelligence", "paths": ("modules/mining_profit_intelligence.py",), "route_prefixes": ("/api/mining/profit-intelligence",), "critical": False},
    {"id": "ai_worker_coordinator", "name": "NEXUS AI Worker Coordinator", "paths": ("modules/ai_worker_coordinator.py", "modules/ai_worker_provider.py", "modules/local_ai_models.py"), "route_prefixes": ("/api/nexus/workers",), "runtime_service": "ai_worker_coordinator", "critical": False},
    {"id": "gate_info", "name": "Gate Info Research & Paper Trading", "paths": ("modules/gate_paper_trading.py",), "route_prefixes": ("/api/gate", "/gate-paper"), "critical": False},
    {"id": "math_intelligence", "name": "Math Intelligence", "paths": ("modules/math_intelligence.py",), "route_prefixes": ("/api/math",), "critical": False},
    {"id": "puzzle_solver", "name": "Multi-Method Puzzle Solver", "paths": ("modules/puzzle_solver.py",), "route_prefixes": ("/api/puzzles",), "runtime_service": "puzzle_solver", "critical": False},
    {"id": "research_hub", "name": "Research Hub", "paths": ("modules/research_hub.py",), "route_prefixes": ("/api/research",), "runtime_service": "research_hub", "critical": False},
    {"id": "earnings_intelligence", "name": "Earnings Intelligence", "paths": ("modules/earnings_intelligence.py",), "route_prefixes": ("/api/intel",), "runtime_service": "earnings_intelligence", "critical": False},
    {"id": "mining_switch_controller", "name": "Conditional Mining Switch", "paths": ("modules/mining_switch_controller.py",), "route_prefixes": ("/api/mining/hybrid",), "runtime_service": "mining_switch_controller", "critical": False},
    {"id": "blockchain_regtest", "name": "Local Blockchain Regtest", "paths": ("modules/blockchain_regtest/nexus_v05_integration.py",), "route_prefixes": (), "runtime_service": "blockchain_regtest", "critical": False},
    {"id": "edge_manager", "name": "NEXUS EDGE Manager", "paths": (
        "nexus_edge/manager.py", "nexus_edge/service.py",
        "nexus_edge/replay_guard.py", "nexus_edge/sqlite_store.py",
        "nexus_edge/gateway.py", "nexus_edge/gateway_runtime.py",
        "nexus_edge/runtime.py", "nexus_edge/transports.py",
        "nexus_edge/topology.py", "nexus_edge/config.py",
        "nexus_edge/rotate_storage_key.py",
    ), "route_prefixes": (), "runtime_service": "edge_manager", "critical": False},
    {"id": "depin_fieldstation", "name": "DePIN Fieldstation", "paths": ("adapters/fieldstation/crypto_fieldstation/app.py",), "route_prefixes": (), "runtime_service": "depin_fieldstation", "critical": False},
)


def _route_paths(app: Any | None) -> set[str]:
    if app is None:
        return set()
    # OpenAPI is the stable public surface across FastAPI versions. Newer
    # FastAPI releases may keep included routers as lazy internal objects
    # without a direct .path attribute.
    try:
        schema = app.openapi()
        paths = schema.get("paths", {}) if isinstance(schema, dict) else {}
        if isinstance(paths, dict):
            return {path for path in paths if isinstance(path, str)}
    except Exception:
        pass
    paths: set[str] = set()
    for route in getattr(app, "routes", ()):
        path = getattr(route, "path", None)
        if isinstance(path, str):
            paths.add(path)
    return paths


def build_module_registry(root: str | Path, app: Any | None = None,
                          modules: Iterable[dict[str, Any]] = MODULES,
                          runtime_services: Iterable[str] | None = None,
                          runtime_health: Mapping[str, Any] | None = None) -> dict[str, Any]:
    base = Path(root)
    routes = _route_paths(app)
    active_runtime_services = set(runtime_services or ())
    health_by_service = dict(runtime_health or {})
    module_items = tuple(modules)

    # Fail clearly rather than silently collapsing duplicate IDs in consumers
    # that build dictionaries keyed by module ID.
    seen_ids: set[str] = set()
    for item in module_items:
        module_id = item.get("id")
        if not isinstance(module_id, str) or not module_id.strip():
            raise ValueError("every module registry entry must have a non-empty string id")
        if module_id in seen_ids:
            raise ValueError(f"duplicate module registry id: {module_id}")
        seen_ids.add(module_id)

    results: list[dict[str, Any]] = []
    for item in module_items:
        present_paths = [rel for rel in item["paths"] if (base / rel).is_file()]
        missing_paths = [rel for rel in item["paths"] if not (base / rel).is_file()]
        prefixes = tuple(item.get("route_prefixes", ()))
        registered = sorted(path for path in routes
                            if any(path == prefix or path.startswith(prefix + "/") for prefix in prefixes))
        source_present = bool(present_paths)
        route_required = bool(prefixes)
        runtime_service = item.get("runtime_service")
        runtime_registered = bool(runtime_service and runtime_service in active_runtime_services)
        route_registered = bool(registered) if route_required else False
        integrated = source_present and (route_registered or runtime_registered)
        service_health = health_by_service.get(runtime_service, {}) if runtime_service else {}
        runtime_health_ok = bool(
            runtime_registered
            and isinstance(service_health, Mapping)
            and service_health.get("ok") is True
        )
        health_details = service_health.get("details", {}) if isinstance(service_health, Mapping) else {}
        external_dependencies_verified: bool | None = None
        operational_requirement_met = runtime_health_ok
        verification_reason = (
            "runtime_health_passed" if runtime_health_ok else
            "runtime_health_missing_or_failed" if runtime_service else
            "runtime_health_not_mapped"
        )

        # These two modules have explicit external prerequisites beyond their
        # local service health: every worker needs a real model self-test, and
        # all catalogued external connectors need a successful live probe.
        if item["id"] == "ai_worker_coordinator":
            worker_test = health_details.get("worker_self_test", {})
            provider_live = health_details.get("provider_live_verified") is True
            self_test_live = (
                isinstance(worker_test, Mapping)
                and worker_test.get("operational_verified") is True
                and worker_test.get("workers_tested") == 11
                and worker_test.get("workers_passed") == 11
            )
            external_dependencies_verified = provider_live
            operational_requirement_met = runtime_health_ok and provider_live and self_test_live
            if not provider_live:
                verification_reason = "live_ai_provider_probe_required"
            elif not self_test_live:
                verification_reason = "all_eleven_worker_self_test_required"
            else:
                verification_reason = "provider_and_all_eleven_workers_live_verified"
        elif item["id"] == "integrations":
            provider_count = health_details.get("providers_catalogued", 0)
            live_count = health_details.get("live_connections_verified", 0)
            external_dependencies_verified = bool(provider_count and live_count == provider_count)
            operational_requirement_met = runtime_health_ok and external_dependencies_verified
            verification_reason = (
                "all_external_connectors_live_verified" if operational_requirement_met
                else "all_catalogued_external_connectors_must_be_live_verified"
            )

        route_requirement_met = (not route_required) or route_registered
        operational_verified = bool(
            source_present and route_requirement_met and operational_requirement_met
        )
        if not source_present:
            state = "missing_source"
        elif route_registered and runtime_registered:
            state = "runtime_and_route_registered_health_unverified"
        elif route_registered:
            state = "route_registered_runtime_unverified"
        elif runtime_registered:
            state = "runtime_registered_health_unverified"
        else:
            state = "source_present_not_integrated"
        results.append({
            "id": item["id"], "name": item["name"], "critical": bool(item.get("critical")),
            "state": state, "source_present": source_present,
            "present_paths": present_paths, "missing_paths": missing_paths,
            "route_registration_required": route_required,
            "registered_routes": registered,
            "runtime_service": runtime_service,
            "runtime_registered": runtime_registered,
            "runtime_health_ok": runtime_health_ok,
            "operational_verified": operational_verified,
            "external_dependencies_verified": external_dependencies_verified,
            "verification_reason": verification_reason,
        })
    counts = {key: sum(row["state"] == key for row in results)
              for key in ("missing_source", "source_present_not_integrated", "route_registered_runtime_unverified", "runtime_registered_health_unverified", "runtime_and_route_registered_health_unverified")}
    operational_count = sum(bool(row["operational_verified"]) for row in results)
    return {
        "modules": results,
        "total": len(results),
        "counts": counts,
        "operational_verified_modules": operational_count,
        "operational_pending_modules": len(results) - operational_count,
        "system_operational_verified": bool(results) and operational_count == len(results),
        "policy": (
            "Operational verification requires source presence, required route registration, "
            "a successful live runtime health probe and any module-specific external acceptance "
            "gate. AI requires all 11 live worker tests; Integrations requires all registered "
            "external connectors to pass their live probes."
        ),
    }
