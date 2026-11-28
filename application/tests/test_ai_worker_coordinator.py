from fastapi.testclient import TestClient
import pytest

from modules.ai_worker_coordinator import WORKER_BY_DOMAIN, route_task, worker_catalog
from nexus_master import app


def test_catalog_registers_11_specialist_slots_without_claiming_live_ai(monkeypatch):
    monkeypatch.setenv("NEXUS_AI_PROVIDER", "disabled")
    catalog = worker_catalog()
    ids = {row["id"] for row in catalog["workers"]}
    assert len(ids) == 11
    assert {"central_coordinator", "mining_compute", "edge_depin",
            "wallet_security", "dashboard_synapse", "quality_security"} <= ids
    assert catalog["configured_model_providers"] == 0
    assert catalog["active_ai_agents"] == 0
    assert catalog["model_invocation_enabled"] is False


def test_path_routes_mining_work_to_specialist():
    result = route_task(
        task_kind="benchmark_analysis",
        path="application/mining/hybrid_supervisor.py",
    )
    assert result["worker_id"] == "mining_compute"
    assert result["route_reason"] == "repository_path"
    assert result["model_invoked"] is False


def test_path_routes_puzzle_solver_to_cryptography_worker():
    result = route_task(
        task_kind="implementation",
        path="application/modules/puzzle_solver.py",
    )
    assert result["worker_id"] == "cryptography_research"
    assert result["route_reason"] == "repository_path"
    assert result["model_invoked"] is False


def test_branch_routes_edge_feature():
    result = route_task(
        task_kind="research",
        branch="feature/edge-replay-protection-sqlite-v1",
    )
    assert result["worker_id"] == "edge_depin"
    assert result["route_reason"] == "branch_pattern"


def test_mutating_task_requires_qa_reviewer_and_human_review():
    result = route_task(
        task_kind="implementation",
        path="application/modules/ai_worker_coordinator.py",
    )
    assert result["worker_id"] == "ai_platform"
    assert result["reviewer_worker_id"] == "quality_security"
    assert result["human_review_required"] is True
    assert result["permissions"]["write_repository"] is False
    assert result["permissions"]["execute_shell"] is False
    assert result["permissions"]["start_miner"] is False
    assert result["permissions"]["sign_transaction"] is False


def test_path_traversal_unknown_domain_and_task_are_rejected():
    with pytest.raises(ValueError, match="path traversal"):
        route_task(task_kind="analysis", path="application/../secrets.env")
    with pytest.raises(ValueError, match="unknown worker domain"):
        route_task(task_kind="analysis", domain="not-a-domain")
    with pytest.raises(ValueError, match="unsupported task_kind"):
        route_task(task_kind="unlisted")


def test_api_exposes_catalog_and_preview_only_routing():
    with TestClient(app, base_url="http://127.0.0.1", client=("127.0.0.1", 54321)) as client:
        catalog = client.get("/api/nexus/workers")
        assert catalog.status_code == 200
        assert catalog.json()["model_invocation_enabled"] is False
        preview = client.post("/api/nexus/workers/route", json={
            "task_kind": "implementation",
            "path": "application/mining/controller.py",
        })
        assert preview.status_code == 200
        assert preview.json()["worker_id"] == "mining_compute"
        assert preview.json()["reviewer_worker_id"] == "quality_security"
        assert preview.json()["model_invoked"] is False



def test_execution_invokes_domain_specialist_and_qa_reviewer_as_text_only(monkeypatch):
    from modules import ai_worker_coordinator as coordinator

    monkeypatch.setattr(coordinator, "ai_provider_status", lambda: {
        "provider_status": "configured_not_live_verified",
        "provider": "mock", "model": "unit-test-model",
        "configured_model_providers": 1, "model_invocation_enabled": True,
    })
    calls = []

    def fake_chat(messages, *, model=None):
        calls.append(messages)
        reviewer = "QA, Security" in messages[0]["content"]
        return {
            "content": "security review" if reviewer else "specialist proposal",
            "provider": "mock",
            "model": model or "unit-test-model",
            "remote": False,
            "prompt_tokens": 4,
            "completion_tokens": 5,
            "tools_available": False,
            "tool_calls_executed": 0,
            "side_effects_performed": False,
        }

    monkeypatch.setattr(coordinator, "chat_completion", fake_chat)
    result = coordinator.execute_worker_task(
        task_kind="implementation",
        path="application/modules/ai_worker_coordinator.py",
        branch="feature/nexus-ai-agent-runtime-synapse-v1",
        prompt="Propose an implementation plan for the provider adapter.",
    )

    assert result["worker"]["id"] == "ai_platform"
    assert result["worker"]["output"] == "specialist proposal"
    assert result["review"]["worker_id"] == "quality_security"
    assert result["review"]["output"] == "security review"
    assert len(calls) == 2
    assert result["model_invoked"] is True
    assert result["side_effects_performed"] is False
    assert result["repository_changes"] == 0
    assert result["miners_started"] == 0
    assert result["wallet_operations"] == 0
    assert result["human_review_required"] is True
    assert all(set(message) == {"role", "content"} for call in calls for message in call)


def test_worker_execution_api_fails_closed_when_provider_is_disabled(monkeypatch):
    monkeypatch.setenv("NEXUS_AI_PROVIDER", "disabled")
    with TestClient(app, base_url="http://127.0.0.1", client=("127.0.0.1", 54321)) as client:
        response = client.post("/api/nexus/workers/execute", json={
            "task_kind": "analysis",
            "domain": "mining",
            "prompt": "Compare RandomX benchmark methods.",
        })
    assert response.status_code == 503
    assert response.json()["detail"] == "ai_provider_not_configured"


def test_provider_status_api_never_exposes_environment_api_key(monkeypatch):
    monkeypatch.setenv("NEXUS_AI_PROVIDER", "disabled")
    monkeypatch.setenv("NEXUS_AI_API_KEY", "should-never-be-returned")
    with TestClient(app, base_url="http://127.0.0.1", client=("127.0.0.1", 54321)) as client:
        response = client.get("/api/nexus/workers/provider-status")
    assert response.status_code == 200
    assert "should-never-be-returned" not in response.text


def test_worker_provider_endpoints_reject_non_loopback_clients(monkeypatch):
    monkeypatch.setenv("NEXUS_AI_PROVIDER", "ollama")
    monkeypatch.setenv("NEXUS_AI_MODEL", "test-model")
    with TestClient(app, base_url="http://127.0.0.1", client=("192.0.2.10", 54321)) as client:
        status = client.get("/api/nexus/workers/provider-status")
        execute = client.post("/api/nexus/workers/execute", json={
            "task_kind": "analysis",
            "domain": "mining",
            "prompt": "Test non-loopback request rejection.",
        })
    assert status.status_code == 403
    assert status.json()["detail"] == "NEXUS CORE accepts local loopback requests only"
    assert execute.status_code == 403
    assert execute.json()["detail"] == "NEXUS CORE accepts local loopback requests only"


def test_integration_branches_route_to_domain_specialists():
    cases = {
        "integration/rainbowminer-mining-intelligence-v1": "mining",
        "integration/ai-worker-provider-main-v1": "ai_platform",
        "integration/math-intelligence-evidence-main-v1": "cryptography",
        "integration/provider-contract-tests-main-v1": "integrations",
        "integration/fieldstation-import-boundary-main-v1": "edge",
        "integration/pr26-security-baseline-main-v2": "quality",
        "integration/desktop-package-main-trigger-v1": "dashboard",
        "integration/phy-challenge-solver-v2": "cryptography",
    }
    for branch, expected_domain in cases.items():
        result = route_task(task_kind="research", branch=branch)
        assert result["domain"] == expected_domain, branch


def test_central_coordinator_runs_multiple_specialists_and_quality_review(monkeypatch):
    from modules import ai_worker_coordinator as coordinator

    monkeypatch.setattr(
        coordinator,
        "ai_provider_status",
        lambda: {
            "provider_status": "configured_not_live_verified",
            "model": "mock-model",
            "model_invocation_enabled": True,
        },
    )
    calls = []

    def fake_chat(messages, model=None):
        calls.append({"messages": messages, "model": model})
        role = messages[0]["content"]
        if "NEXUS Central Coordinator" in role:
            text = "Central execution brief: inspect telemetry contract and economics."
        elif "Quality, Security" in role:
            text = "Review: require authenticated local ingest and tests."
        else:
            text = "Specialist finding: recommendation only."
        return {
            "content": text,
            "model": model or "mock-model",
            "provider": "mock",
            "remote": False,
            "prompt_tokens": 10,
            "completion_tokens": 20,
            "tools_available": False,
            "tool_calls_executed": 0,
            "side_effects_performed": False,
        }

    monkeypatch.setattr(coordinator, "chat_completion", fake_chat)
    result = coordinator.execute_coordinated_task(
        task_kind="research",
        branch="integration/rainbowminer-mining-intelligence-v1",
        path="application/modules/mining_profit_intelligence.py",
        domains=["mining", "integrations"],
        prompt="Review the read-only RainbowMiner integration.",
    )

    assert result["dispatch_mode"] == "central_then_sequential_specialists"
    assert result["route"]["domain"] == "mining"
    assert [row["domain"] for row in result["specialists"]] == ["mining", "integrations"]
    assert result["central_coordinator"]["id"] == "central_coordinator"
    assert result["quality_review"]["worker_id"] == "quality_security"
    assert len(calls) == 4
    assert all(row["model"] == "mock-model" for row in calls)
    assert result["model_invoked"] is True
    assert result["side_effects_performed"] is False
    assert result["repository_changes"] == 0
    assert result["miners_started"] == 0
    assert result["wallet_operations"] == 0


def test_coordinated_worker_rejects_invalid_or_excessive_domains(monkeypatch):
    from modules import ai_worker_coordinator as coordinator

    monkeypatch.setattr(
        coordinator,
        "ai_provider_status",
        lambda: {"model_invocation_enabled": True, "model": "mock-model"},
    )
    with pytest.raises(ValueError, match="maximum_ten_specialist_domains"):
        coordinator.execute_coordinated_task(
            task_kind="research", prompt="test",
            domains=["mining"] * 11,
        )
    with pytest.raises(ValueError, match="unknown_or_reserved_specialist_domain"):
        coordinator.execute_coordinated_task(
            task_kind="research", prompt="test", domains=["coordination"],
        )


def test_coordinated_worker_api_is_loopback_and_invokes_central_specialists(monkeypatch):
    from modules import ai_worker_coordinator as coordinator

    monkeypatch.setattr(
        coordinator, "ai_provider_status",
        lambda: {"model_invocation_enabled": True, "model": "mock-model"},
    )
    monkeypatch.setattr(
        coordinator, "chat_completion",
        lambda messages, model=None: {
            "content": "Mock coordinated result",
            "model": model or "mock-model",
            "provider": "mock",
            "remote": False,
            "prompt_tokens": 1,
            "completion_tokens": 2,
            "tools_available": False,
            "tool_calls_executed": 0,
            "side_effects_performed": False,
        },
    )
    payload = {
        "task_kind": "research",
        "branch": "integration/rainbowminer-mining-intelligence-v1",
        "domains": ["mining", "integrations"],
        "prompt": "Review RainbowMiner telemetry and profitability integration.",
    }
    with TestClient(app, base_url="http://127.0.0.1",
                    client=("127.0.0.1", 54322)) as client:
        response = client.post("/api/nexus/workers/coordinate", json=payload)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["central_coordinator"]["id"] == "central_coordinator"
    assert [item["domain"] for item in body["specialists"]] == ["mining", "integrations"]
    assert body["quality_review"]["worker_id"] == "quality_security"
    assert body["side_effects_performed"] is False
    assert body["repository_changes"] == 0


def test_all_repository_branch_families_route_to_specialists_or_central():
    branches = [
        "main",
        "audit/full-repository-2026-11-26",
        "dependabot/github_actions/actions/checkout-7.0.1",
        "experiment/lfm3-core-security-lab-v1",
        "feature/core-lifecycle-isolation-registry-uniqueness",
        "feature/crypto-reference-validation-v1",
        "feature/edge-persistence-protocol-v1",
        "feature/edge-replay-protection-sqlite-v1",
        "feature/gate-info-paper-trading-100ron",
        "feature/nexus-ai-agent-runtime-synapse-v1",
        "feature/nexus-ai-worker-mining-safety-v1",
        "feature/nexus-edge-foundation",
        "feature/nexus-fieldstation-runtime-validation-v1",
        "feature/nexus-integrations-contract-tests-v1",
        "feature/nexus-math-intelligence-hardening-v1",
        "feature/phy-challenge-structure-solver-v1",
        "feature/puzzle-solver-dashboard-v1",
        "feature/puzzle-solver-multimethod-v1",
        "feature/read-only-market-data-adapters-v1",
        "fix/pr28-action-pin-validator-v1",
        "fix/windows-desktop-pythonnet-runtime-2026-11-27",
        "integration/ai-worker-provider-main-v1",
        "integration/desktop-package-main-trigger-v1",
        "integration/fieldstation-import-boundary-main-v1",
        "integration/gate-paper-trading-main-v1",
        "integration/market-data-main-reconcile-2026-11-26",
        "integration/math-intelligence-evidence-main-v1",
        "integration/phy-challenge-solver-v2",
        "integration/phy-challenge-structure-main-v1",
        "integration/pr24-crypto-reference-main-v1",
        "integration/pr26-security-baseline-main-v2",
        "integration/provider-contract-tests-main-v1",
        "integration/rainbowminer-mining-intelligence-v1",
        "integration/windows-process-safety-testclient-v1",
        "security/immutable-action-pins-v1",
        "security/mining-credential-log-hygiene-v1",
        "security/supply-chain-scans-v1",
        "docs/nexus-continuity-refresh-2026-11-25",
        "release/0.10.28",
    ]
    for branch in branches:
        result = route_task(task_kind="research", branch=branch)
        assert result["domain"] in WORKER_BY_DOMAIN, branch
        assert result["worker_id"] in {row["id"] for row in worker_catalog()["workers"]}, branch

    expected = {
        "audit/full-repository-2026-11-26": "quality",
        "dependabot/github_actions/actions/checkout-7.0.1": "quality",
        "experiment/lfm3-core-security-lab-v1": "ai_platform",
        "feature/phy-challenge-structure-solver-v1": "cryptography",
        "feature/puzzle-solver-multimethod-v1": "cryptography",
        "feature/core-lifecycle-isolation-registry-uniqueness": "quality",
        "security/supply-chain-scans-v1": "quality",
    }
    for branch, domain in expected.items():
        assert route_task(task_kind="research", branch=branch)["domain"] == domain


def test_coordinator_can_dispatch_all_ten_specialists_without_duplicate_quality_call(monkeypatch):
    from modules import ai_worker_coordinator as coordinator

    monkeypatch.setattr(
        coordinator,
        "ai_provider_status",
        lambda: {"model_invocation_enabled": True, "model": "lfm3"},
    )
    calls = []

    def fake_chat(messages, model=None):
        system = messages[0]["content"]
        if "NEXUS Central Coordinator" in system:
            role = "central"
        elif "Quality, Security" in system:
            role = "quality"
        else:
            role = "specialist"
        calls.append({"role": role, "model": model})
        return {
            "content": f"{role} result",
            "model": model or "lfm3",
            "provider": "ollama",
            "remote": False,
            "prompt_tokens": 12,
            "completion_tokens": 18,
            "tools_available": False,
            "tool_calls_executed": 0,
            "side_effects_performed": False,
        }

    monkeypatch.setattr(coordinator, "chat_completion", fake_chat)
    all_specialists = [
        "mining", "cryptography", "blockchain", "wallet", "edge",
        "integrations", "dashboard", "earnings", "ai_platform", "quality",
    ]
    result = coordinator.execute_coordinated_task(
        task_kind="research",
        prompt="Audit NEXUS end-to-end and report work packages.",
        domains=all_specialists,
    )
    assert result["central_coordinator"]["id"] == "central_coordinator"
    assert len(result["specialists"]) == 9
    assert {row["domain"] for row in result["specialists"]} == set(all_specialists) - {"quality"}
    assert result["quality_review"]["worker_id"] == "quality_security"
    assert result["quality_review"]["output"] == "quality result"
    assert result["execution_manifest"] == {
        "coordinator_profile": "central_coordinator",
        "specialist_profiles_requested": all_specialists,
        "specialist_profiles_invoked": all_specialists,
        "specialist_profiles_count": 10,
        "model_calls": 11,
        "all_ten_specialists_invoked": True,
        "all_eleven_profiles_invoked": True,
        "execution_is_sequential": True,
    }
    assert len(calls) == 11
    assert sum(row["role"] == "central" for row in calls) == 1
    assert sum(row["role"] == "quality" for row in calls) == 1
    assert sum(row["role"] == "specialist" for row in calls) == 9
    assert result["side_effects_performed"] is False
    assert result["repository_changes"] == 0
    assert result["miners_started"] == 0
    assert result["wallet_operations"] == 0


def test_coordinated_request_schema_accepts_ten_specialist_profiles():
    from modules.ai_worker_coordinator import WorkerCoordinatedExecuteRequest

    payload = WorkerCoordinatedExecuteRequest(
        task_kind="research",
        prompt="Run the full NEXUS specialist review.",
        domains=[
            "mining", "cryptography", "blockchain", "wallet", "edge",
            "integrations", "dashboard", "earnings", "ai_platform", "quality",
        ],
    )
    assert len(payload.domains) == 10
