from fastapi.testclient import TestClient
import pytest

from modules.ai_worker_coordinator import route_task, worker_catalog
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
    with TestClient(app) as client:
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
    assert all("tools" not in str(call) for call in calls)


def test_worker_execution_api_fails_closed_when_provider_is_disabled(monkeypatch):
    monkeypatch.setenv("NEXUS_AI_PROVIDER", "disabled")
    with TestClient(app) as client:
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
    with TestClient(app) as client:
        response = client.get("/api/nexus/workers/provider-status")
    assert response.status_code == 200
    assert "should-never-be-returned" not in response.text
