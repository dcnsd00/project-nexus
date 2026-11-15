"""NEXUS module inventory and runtime integration evidence.

The registry deliberately distinguishes source presence from runtime route
registration. It never reports a module as operational merely because files exist.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable

MODULES: tuple[dict[str, Any], ...] = (
    {"id": "core", "name": "NEXUS Core", "paths": ("core/PROJECT-NEXUS-LOCAL/app/main.py",), "route_prefixes": ("/api/nexus",), "critical": True},
    {"id": "wallet", "name": "Wallet Engine", "paths": ("modules/wallet_benchmark/nexus_wallet_manager.py",), "route_prefixes": ("/api/wallet",), "critical": True},
    {"id": "mining_supervisor", "name": "Hybrid Mining Supervisor", "paths": ("mining/hybrid_supervisor.py", "mining/hybrid_orchestrator.py"), "route_prefixes": ("/api/mining",), "critical": True},
    {"id": "crypto_engine", "name": "Cryptographic Engine", "paths": ("modules/crypto_engine/engine.py",), "route_prefixes": ("/api/crypto",), "critical": True},
    {"id": "rcsc", "name": "RCSC Research", "paths": ("research/rcsc/nexus_rcsc/nexus_rcsc/collector.py", "modules/rcsc_service.py"), "route_prefixes": ("/api/research/rcsc",), "critical": False},
    {"id": "earnings_intelligence", "name": "Earnings Intelligence", "paths": ("modules/earnings_intelligence.py",), "route_prefixes": ("/api/earnings",), "critical": False},
    {"id": "integrations", "name": "Provider Integrations", "paths": ("modules/integration_registry.py",), "route_prefixes": ("/api/integrations",), "critical": False},
    {"id": "math_intelligence", "name": "Math Intelligence", "paths": ("modules/math_intelligence.py",), "route_prefixes": ("/api/math",), "critical": False},
    {"id": "research_hub", "name": "Research Hub", "paths": ("modules/research_hub.py",), "route_prefixes": ("/api/research",), "critical": False},
    {"id": "depin_fieldstation", "name": "DePIN Fieldstation", "paths": ("adapters/fieldstation/crypto_fieldstation/app.py",), "route_prefixes": (), "critical": False},
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
                          modules: Iterable[dict[str, Any]] = MODULES) -> dict[str, Any]:
    base = Path(root)
    routes = _route_paths(app)
    results: list[dict[str, Any]] = []
    for item in modules:
        present_paths = [rel for rel in item["paths"] if (base / rel).is_file()]
        missing_paths = [rel for rel in item["paths"] if not (base / rel).is_file()]
        prefixes = tuple(item.get("route_prefixes", ()))
        registered = sorted(path for path in routes
                            if any(path == prefix or path.startswith(prefix + "/") for prefix in prefixes))
        source_present = bool(present_paths)
        route_required = bool(prefixes)
        integrated = source_present and (bool(registered) if route_required else False)
        if not source_present:
            state = "missing_source"
        elif integrated:
            state = "route_registered_runtime_unverified"
        else:
            state = "source_present_not_integrated"
        results.append({
            "id": item["id"], "name": item["name"], "critical": bool(item.get("critical")),
            "state": state, "source_present": source_present,
            "present_paths": present_paths, "missing_paths": missing_paths,
            "route_registration_required": route_required,
            "registered_routes": registered,
            "operational_verified": False,
        })
    counts = {key: sum(row["state"] == key for row in results)
              for key in ("missing_source", "source_present_not_integrated", "route_registered_runtime_unverified")}
    return {"modules": results, "total": len(results), "counts": counts,
            "system_operational_verified": False,
            "policy": "Source presence and route registration are evidence of packaging/integration only; runtime operation requires separate health and functional tests."}
