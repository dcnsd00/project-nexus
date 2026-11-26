"""NEXUS domain-worker registry and deterministic task-routing preview.

The registry is intentionally framework-neutral. It does not call an LLM or
execute tools until a model provider has been configured, validated and given
explicit scoped permissions.
"""
from __future__ import annotations

from fnmatch import fnmatchcase
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field


WORKERS: tuple[dict[str, Any], ...] = (
    {"id": "central_coordinator", "name": "NEXUS Central Coordinator",
     "domain": "coordination", "path_prefixes": (),
     "branch_patterns": ("main", "release/*"),
     "capabilities": ("task_decomposition", "cross_domain_synthesis", "dependency_planning")},
    {"id": "mining_compute", "name": "Mining & Compute Specialist", "domain": "mining",
     "path_prefixes": ("application/mining/", "application/modules/mining_"),
     "branch_patterns": ("feature/*mining*", "feature/*compute*", "feature/*miner*"),
     "capabilities": ("algorithm_research", "backend_compatibility", "benchmark_analysis",
                      "pool_validation", "thermal_safety", "efficiency_optimization")},
    {"id": "cryptography_research", "name": "Cryptography & Mathematics Specialist",
     "domain": "cryptography",
     "path_prefixes": ("application/modules/crypto_engine/", "application/research/sha2_",
                       "application/research/rcsc/", "application/modules/math_intelligence.py"),
     "branch_patterns": ("feature/*crypto*", "feature/*sha*", "feature/*math*", "feature/*rcsc*"),
     "capabilities": ("cryptographic_review", "hash_benchmarks", "statistical_validation",
                      "mathematical_proofs", "reproducible_experiments")},
    {"id": "blockchain_data", "name": "Blockchain & On-chain Data Specialist", "domain": "blockchain",
     "path_prefixes": ("application/modules/blockchain_", "application/modules/blockchain_node_telemetry.py",
                       "application/modules/evm_node_telemetry.py", "application/research/rcsc/"),
     "branch_patterns": ("feature/*blockchain*", "feature/*chain*"),
     "capabilities": ("chain_telemetry", "block_validation", "rpc_contracts",
                      "transaction_graph_analysis", "read_only_data")},
    {"id": "wallet_security", "name": "Wallet & Key-Safety Specialist", "domain": "wallet",
     "path_prefixes": ("application/modules/wallet_benchmark/", "application/nexus_wallet_recovery_api.py",
                       "application/tools_audit_vault.py"),
     "branch_patterns": ("feature/*wallet*", "feature/*recovery*"),
     "capabilities": ("wallet_format_review", "vault_integrity", "key_safety",
                      "watch_only_analysis", "recovery_test_design")},
    {"id": "edge_depin", "name": "NEXUS EDGE & DePIN Specialist", "domain": "edge",
     "path_prefixes": ("application/nexus_edge/", "application/adapters/fieldstation/"),
     "branch_patterns": ("feature/*edge*", "feature/*fieldstation*", "feature/*depin*"),
     "capabilities": ("edge_protocols", "replay_protection", "node_lifecycle",
                      "telemetry", "device_integration")},
    {"id": "integrations_data", "name": "Integrations & Market Data Specialist",
     "domain": "integrations",
     "path_prefixes": ("application/modules/integration_registry.py",
                       "application/modules/pool_connectors.py",
                       "application/modules/gate_paper_trading.py"),
     "branch_patterns": ("feature/*integration*", "feature/*gate-info*", "feature/*market*"),
     "capabilities": ("provider_contracts", "freshness_validation", "read_only_market_data",
                      "api_research", "source_provenance")},
    {"id": "dashboard_synapse", "name": "Dashboard & Synapse Visualization Specialist",
     "domain": "dashboard",
     "path_prefixes": ("application/dashboard.html", "application/wallet.html", "application/ui/"),
     "branch_patterns": ("feature/*dashboard*", "feature/*synapse*", "feature/*visual*"),
     "capabilities": ("dashboard_ux", "graph_visualization", "three_dimensional_graphs",
                      "temporal_replay", "accessibility")},
    {"id": "earnings_economics", "name": "Earnings, Economics & Opportunity Specialist",
     "domain": "earnings",
     "path_prefixes": ("application/modules/earnings_intelligence.py",
                       "application/modules/mining_efficiency_optimizer.py"),
     "branch_patterns": ("feature/*earnings*", "feature/*economics*", "feature/*opportunity*"),
     "capabilities": ("reward_accounting", "profitability_models", "device_inventory",
                      "power_cost_analysis", "payout_evidence")},
    {"id": "ai_platform", "name": "AI Worker Platform Specialist", "domain": "ai_platform",
     "path_prefixes": ("application/modules/ai_worker_coordinator.py", "application/agents/"),
     "branch_patterns": ("feature/*ai-worker*", "feature/*agent*", "feature/*orchestrat*"),
     "capabilities": ("agent_routing", "model_provider_adapters", "tool_permissions",
                      "human_approval", "agent_evaluation")},
    {"id": "quality_security", "name": "QA, Security & Release Validation Specialist",
     "domain": "quality",
     "path_prefixes": ("application/tests/", ".github/workflows/", "application/packaging/"),
     "branch_patterns": ("feature/*security*", "feature/*qa*", "fix/*"),
     "capabilities": ("test_design", "regression_analysis", "security_review",
                      "build_validation", "release_gates")},
)

WORKER_BY_DOMAIN = {row["domain"]: row for row in WORKERS}
TASK_KINDS = frozenset({
    "analysis", "research", "code_review", "test_design", "benchmark_analysis",
    "implementation", "merge", "security_review", "ui_design", "mining_start",
    "wallet_action", "provider_write", "deployment",
})
MUTATING_TASKS = frozenset({
    "implementation", "merge", "mining_start", "wallet_action",
    "provider_write", "deployment",
})
_READ_ONLY_PERMISSIONS = {
    "read_repository": True,
    "research_public_sources": True,
    "propose_patch": True,
    "write_repository": False,
    "execute_shell": False,
    "start_miner": False,
    "unlock_wallet": False,
    "sign_transaction": False,
    "broadcast_transaction": False,
    "write_to_external_provider": False,
}

router = APIRouter(prefix="/api/nexus/workers", tags=["NEXUS AI Workers"])


def _normalize_path(value: str | None) -> str | None:
    if value is None:
        return None
    path = value.strip().replace("\\", "/")
    if not path or len(path) > 300 or path.startswith("/"):
        raise ValueError("path must be a repository-relative path")
    parts = path.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        raise ValueError("path traversal or empty path segment is not allowed")
    if ":" in parts[0]:
        raise ValueError("absolute paths are not allowed")
    return path


def _normalize_branch(value: str | None) -> str | None:
    if value is None:
        return None
    branch = value.strip()
    if branch.startswith("refs/heads/"):
        branch = branch[len("refs/heads/"):]
    if (not branch or branch.startswith("/") or "\\" in branch
            or any(part in {"", ".", ".."} for part in branch.split("/"))):
        raise ValueError("invalid branch ref")
    return branch


def _path_worker(path: str) -> dict[str, Any] | None:
    if path.startswith("application/tests/"):
        name = path.rsplit("/", 1)[-1].casefold()
        for token, domain in (
            ("mining", "mining"), ("edge", "edge"), ("wallet", "wallet"),
            ("integration", "integrations"), ("pool", "integrations"),
            ("sha", "cryptography"), ("crypto", "cryptography"),
            ("rcsc", "cryptography"), ("math", "cryptography"),
            ("dashboard", "dashboard"),
        ):
            if token in name:
                return WORKER_BY_DOMAIN[domain]
        return WORKER_BY_DOMAIN["quality"]
    matches = [
        row for row in WORKERS
        if any(path.startswith(prefix) for prefix in row["path_prefixes"])
    ]
    if not matches:
        return None
    return max(matches, key=lambda row: max(
        (len(prefix) for prefix in row["path_prefixes"] if path.startswith(prefix)),
        default=0,
    ))


def _branch_worker(branch: str | None) -> dict[str, Any] | None:
    if not branch:
        return None
    matches = [
        row for row in WORKERS
        if any(fnmatchcase(branch, pattern) for pattern in row["branch_patterns"])
    ]
    if not matches:
        return None
    return max(matches, key=lambda row: max(
        (len(pattern.replace("*", "")) for pattern in row["branch_patterns"]
         if fnmatchcase(branch, pattern)),
        default=0,
    ))


def worker_catalog() -> dict[str, Any]:
    rows = [{
        **row,
        "path_prefixes": list(row["path_prefixes"]),
        "branch_patterns": list(row["branch_patterns"]),
        "capabilities": list(row["capabilities"]),
        "provider_status": "unconfigured",
        "runtime_status": "registered_not_running",
        "dispatch_enabled": False,
        "permissions": dict(_READ_ONLY_PERMISSIONS),
    } for row in WORKERS]
    return {
        "schema_version": 1,
        "coordinator": "central_coordinator",
        "workers": rows,
        "worker_count": len(rows),
        "configured_model_providers": 0,
        "active_ai_agents": 0,
        "dispatch_mode": "route_preview_only",
        "model_invocation_enabled": False,
        "policy": "Worker metadata and routing previews only; provider adapters must be configured and validated separately.",
    }


def route_task(
    *,
    task_kind: str,
    branch: str | None = None,
    path: str | None = None,
    domain: str | None = None,
) -> dict[str, Any]:
    if task_kind not in TASK_KINDS:
        raise ValueError("unsupported task_kind")
    normalized_path = _normalize_path(path)
    normalized_branch = _normalize_branch(branch)
    selected = None
    reason = "central_coordinator_default"

    if domain is not None:
        selected = WORKER_BY_DOMAIN.get(domain)
        if selected is None:
            raise ValueError("unknown worker domain")
        reason = "explicit_domain"
    elif normalized_path:
        selected = _path_worker(normalized_path)
        if selected:
            reason = "repository_path"
    if selected is None and normalized_branch:
        selected = _branch_worker(normalized_branch)
        if selected:
            reason = "branch_pattern"
    if selected is None:
        selected = WORKER_BY_DOMAIN["coordination"]

    reviewer = None
    if task_kind in {"implementation", "merge", "security_review"} and selected["id"] != "quality_security":
        reviewer = "quality_security"
    return {
        "worker_id": selected["id"],
        "worker_name": selected["name"],
        "domain": selected["domain"],
        "branch": normalized_branch,
        "path": normalized_path,
        "task_kind": task_kind,
        "route_reason": reason,
        "reviewer_worker_id": reviewer,
        "provider_status": "unconfigured",
        "execution": "routing_preview_only",
        "model_invoked": False,
        "human_review_required": task_kind in MUTATING_TASKS,
        "permissions": dict(_READ_ONLY_PERMISSIONS),
    }


class WorkerRouteRequest(BaseModel):
    task_kind: str = Field(default="analysis", min_length=1, max_length=40)
    branch: str | None = Field(default=None, max_length=120)
    path: str | None = Field(default=None, max_length=300)
    domain: str | None = Field(default=None, max_length=80)


@router.get("")
def get_worker_catalog() -> dict[str, Any]:
    return worker_catalog()


@router.post("/route")
def preview_worker_route(request: WorkerRouteRequest) -> dict[str, Any]:
    try:
        return route_task(
            task_kind=request.task_kind,
            branch=request.branch,
            path=request.path,
            domain=request.domain,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
