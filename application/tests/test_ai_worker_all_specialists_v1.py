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
