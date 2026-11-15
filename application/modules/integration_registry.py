"""NEXUS connector registry.

This is a truthful capability/credential readiness layer, not a claim that a
provider is connected. Provider adapters remain read-only until individually
implemented and validated against their official API contracts.
"""
from __future__ import annotations
import os
from typing import Any
from fastapi import APIRouter

router = APIRouter(prefix="/api/integrations", tags=["NEXUS Integrations"])

PROVIDERS: tuple[dict[str, Any], ...] = (
    {"id":"acurast", "name":"Acurast", "category":"depin", "env":("NEXUS_ACURAST_API_URL", "NEXUS_ACURAST_API_TOKEN"), "capabilities":["account_read","rewards_read","device_status_read"]},
    {"id":"grass", "name":"Grass", "category":"depin", "env":("NEXUS_GRASS_API_URL", "NEXUS_GRASS_API_TOKEN"), "capabilities":["account_read","points_read","rewards_read"]},
    {"id":"aioz", "name":"AIOZ", "category":"depin", "env":("NEXUS_AIOZ_API_URL",), "capabilities":["public_chain_read","node_status_read","rewards_read"]},
    {"id":"theta", "name":"Theta", "category":"depin", "env":("NEXUS_THETA_API_URL",), "capabilities":["public_chain_read","edge_status_read"]},
    {"id":"nodle", "name":"Nodle", "category":"depin", "env":("NEXUS_NODLE_API_URL",), "capabilities":["public_chain_read","rewards_read"]},
    {"id":"helium_iot", "name":"Helium IoT", "category":"depin", "env":("NEXUS_HELIUM_API_URL",), "capabilities":["coverage_read","hotspot_read","rewards_read"]},
    {"id":"geodnet", "name":"GEODNET", "category":"depin", "env":("NEXUS_GEODNET_API_URL",), "capabilities":["station_read","coverage_read","rewards_read"]},
    {"id":"anyone", "name":"Anyone", "category":"depin", "env":("NEXUS_ANYONE_API_URL",), "capabilities":["relay_status_read","rewards_read"]},
    {"id":"weatherxm", "name":"WeatherXM", "category":"depin", "env":("NEXUS_WEATHERXM_API_URL",), "capabilities":["station_read","rewards_read"]},
    {"id":"wingbits", "name":"Wingbits", "category":"depin", "env":("NEXUS_WINGBITS_API_URL",), "capabilities":["receiver_read","coverage_read","rewards_read"]},
    {"id":"akash", "name":"Akash", "category":"compute", "env":("NEXUS_AKASH_API_URL",), "capabilities":["provider_read","deployment_read","billing_read"]},
    {"id":"nosana", "name":"Nosana", "category":"compute", "env":("NEXUS_NOSANA_API_URL",), "capabilities":["node_read","job_read","rewards_read"]},
)


def connector_status(env: dict[str, str] | None = None) -> list[dict[str, Any]]:
    source = os.environ if env is None else env
    rows = []
    for item in PROVIDERS:
        configured = [key for key in item["env"] if source.get(key)]
        ready = len(configured) == len(item["env"])
        rows.append({
            "id": item["id"], "name": item["name"], "category": item["category"],
            "status": "configured_pending_adapter_validation" if ready else "not_configured",
            "configured_fields": len(configured), "required_fields": len(item["env"]),
            "capabilities": list(item["capabilities"]), "mode": "read_only",
            "live_connection_verified": False, "writes_enabled": False,
            "missing_configuration": [key for key in item["env"] if key not in configured],
        })
    return rows


@router.get("/catalog")
def integrations_catalog():
    rows = connector_status()
    return {"providers": rows, "count": len(rows), "live_verified": 0,
            "policy": "No provider is marked live until its dedicated adapter passes contract, auth, freshness and response validation."}


@router.get("/status")
def integrations_status():
    rows = connector_status()
    return {"total": len(rows),
            "not_configured": sum(x["status"] == "not_configured" for x in rows),
            "configured_pending_adapter_validation": sum(x["status"] == "configured_pending_adapter_validation" for x in rows),
            "live_verified": sum(x["live_connection_verified"] for x in rows),
            "providers": rows}
