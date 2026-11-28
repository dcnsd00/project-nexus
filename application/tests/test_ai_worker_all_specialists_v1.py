"""Coverage of the full registered NEXUS specialist-worker catalogue."""
from modules import ai_worker_coordinator as coordinator


def test_all_eleven_registered_worker_profiles_can_be_dispatched(monkeypatch):
    monkeypatch.setattr(
        coordinator,
        "ai_provider_status",
        lambda: {
            "provider_status": "configured_not_live_verified",
            "model": "contract-test-model",
            "model_invocation_enabled": True,
        },
    )
    calls = []

    def fake_chat(messages, model=None):
        calls.append((messages, model))
        return {
            "content": "synthetic test output",
            "provider": "fake",
            "model": model or "contract-test-model",
            "remote": False,
            "prompt_tokens": 3,
            "completion_tokens": 2,
            "tools_available": False,
            "tool_calls_executed": 0,
            "side_effects_performed": False,
        }

    monkeypatch.setattr(coordinator, "chat_completion", fake_chat)
    catalog = coordinator.worker_catalog()
    assert catalog["worker_count"] == 11
    assert len(coordinator.WORKERS) == 11
    assert len(coordinator.WORKER_BY_DOMAIN) == 11

    dispatched = set()
    for row in coordinator.WORKERS:
        result = coordinator.execute_worker_task(
            task_kind="analysis",
            domain=row["domain"],
            prompt="Run a bounded synthetic worker contract check.",
        )
        assert result["worker"]["id"] == row["id"]
        assert result["model_invoked"] is True
        assert result["side_effects_performed"] is False
        assert result["repository_changes"] == 0
        assert result["miners_started"] == 0
        assert result["wallet_operations"] == 0
        dispatched.add(result["worker"]["id"])

    assert dispatched == {row["id"] for row in coordinator.WORKERS}
    assert len(calls) == 11
    assert all(all(set(message) == {"role", "content"} for message in call[0]) for call in calls)


def test_all_ten_specialist_domains_have_unique_route_and_profile():
    profiles = [row for row in coordinator.WORKERS if row["domain"] != "coordination"]
    assert len(profiles) == 10
    assert len({row["domain"] for row in profiles}) == 10
    for row in profiles:
        route = coordinator.route_task(
            task_kind="research",
            domain=row["domain"],
        )
        assert route["worker_id"] == row["id"]
        assert route["domain"] == row["domain"]
        assert route["model_invoked"] is False
        assert route["permissions"]["write_repository"] is False
        assert route["permissions"]["start_miner"] is False
        assert route["permissions"]["sign_transaction"] is False


def test_live_worker_self_test_exercises_all_eleven_profiles_and_records_verification(monkeypatch):
    monkeypatch.setattr(
        coordinator,
        "ai_provider_status",
        lambda: {
            "provider": "mock-provider",
            "model": "mock-model",
            "operational_verified": True,
            "model_invocation_enabled": True,
        },
    )
    monkeypatch.setattr(
        coordinator,
        "probe_ai_provider",
        lambda: {
            "provider": "mock-provider",
            "model": "mock-model",
            "operational_verified": True,
            "status": "live_verified",
        },
    )
    calls = []

    def fake_execute_worker_task(**kwargs):
        calls.append(kwargs["domain"])
        worker = coordinator.WORKER_BY_DOMAIN[kwargs["domain"]]
        return {
            "worker": {
                "id": worker["id"],
                "model": "mock-model",
                "output": f"Self-test passed for {worker['domain']}.",
            },
            "model_invoked": True,
            "side_effects_performed": False,
            "repository_changes": 0,
            "miners_started": 0,
            "wallet_operations": 0,
        }

    monkeypatch.setattr(coordinator, "execute_worker_task", fake_execute_worker_task)
    result = coordinator.run_worker_self_test()
    assert result["status"] == "live_verified"
    assert result["operational_verified"] is True
    assert result["workers_tested"] == result["workers_passed"] == 11
    assert len(calls) == 11
    assert {row["worker_id"] for row in result["worker_results"]} == {
        row["id"] for row in coordinator.WORKERS
    }
    assert result["side_effects_performed"] is False


def test_worker_live_self_test_api_is_loopback_only(monkeypatch):
    from fastapi.testclient import TestClient
    from nexus_master import app

    from modules import ai_worker_coordinator as coordinator
    expected = {"status": "live_verified", "operational_verified": True, "workers_tested": 11}
    monkeypatch.setattr(coordinator, "run_worker_self_test", lambda: expected)

    with TestClient(app, base_url="http://127.0.0.1",
                    client=("127.0.0.1", 54331)) as client:
        response = client.post("/api/nexus/workers/self-test")
    assert response.status_code == 200
    assert response.json() == expected

    with TestClient(app, base_url="http://127.0.0.1",
                    client=("192.0.2.31", 54331)) as client:
        blocked = client.post("/api/nexus/workers/self-test")
    assert blocked.status_code == 403


def test_owner_instructions_are_injected_for_all_specialist_prompts_without_granting_tools(monkeypatch):
    monkeypatch.setenv(
        "NEXUS_AI_OWNER_INSTRUCTIONS",
        "Answer in Romanian. Prioritize NEXUS MASTER implementation over generic discussion.",
    )
    worker = coordinator.WORKER_BY_DOMAIN["mining"]
    route = coordinator.route_task(task_kind="implementation", domain="mining")
    messages = coordinator._worker_prompt(
        worker, route, "Prepare a concrete benchmark implementation."
    )
    system = messages[0]["content"]
    assert "Answer in Romanian." in system
    assert "Prioritize NEXUS MASTER implementation" in system
    assert "cannot call tools" in system
    assert "cannot call tools" in system
    assert set(messages[0]) == {"role", "content"}
    assert all(set(message) == {"role", "content"} for message in messages)


def test_owner_instructions_have_a_bounded_configuration_size(monkeypatch):
    monkeypatch.setenv("NEXUS_AI_OWNER_INSTRUCTIONS", "x" * 4001)
    worker = coordinator.WORKER_BY_DOMAIN["mining"]
    route = coordinator.route_task(task_kind="analysis", domain="mining")
    import pytest
    with pytest.raises(ValueError, match="NEXUS_AI_OWNER_INSTRUCTIONS exceeds 4000 characters"):
        coordinator._worker_prompt(worker, route, "test")


def test_worker_catalog_includes_local_open_weight_models_without_claiming_runtime_health(monkeypatch):
    monkeypatch.setenv("NEXUS_AI_PROVIDER", "disabled")
    catalog = coordinator.worker_catalog()
    assert catalog["local_open_weight_models_available"] is True
    assert catalog["local_model_catalog_count"] >= 5
    assert catalog["provider_live_verified"] is False
    assert catalog["operational_verified"] is False
