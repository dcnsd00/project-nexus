import os
from fastapi.testclient import TestClient


def test_nexus_core_api_workflow(monkeypatch, tmp_path):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    from app import main as core_main
    from nexus_master import app
    monkeypatch.setattr(core_main, "DB", str(tmp_path / "nexus_test.db"))
    checks = []
    with TestClient(app) as c:
        def check(name, response, expected=(200, 201)):
            assert response.status_code in expected, (name, response.status_code, response.text)
            checks.append(name)
            return response
        check("health", c.get("/api/health"))
        check("summary", c.get("/api/summary"))
        check("plugins", c.get("/api/plugins"))
        check("agents", c.get("/api/agents"))
        check("tasks_list", c.get("/api/tasks"))
        task_id = check("task_create", c.post("/api/tasks", json={"title":"audit","description":"test","domain":"core","priority":"normal"})).json()["id"]
        check("task_update", c.patch(f"/api/tasks/{task_id}?status=done"))
        check("notes_create", c.post("/api/notes", json={"title":"audit","body":"test","tags":"audit"}))
        check("notes_list", c.get("/api/notes?q=audit"))
        approval_id = check("approval_create", c.post("/api/approvals", json={"action":"test","target":"sandbox","details":"no external action"})).json()["id"]
        check("approval_decision", c.post(f"/api/approvals/{approval_id}?decision=approved"))
        check("approvals_list", c.get("/api/approvals"))
        check("audit_list", c.get("/api/audit"))
        check("math_status", c.get("/api/math/status"))
        check("math_simplify", c.post("/api/math/compute", json={"operation":"simplify","expression":"sin(x)**2+cos(x)**2"}))
        check("number_theory", c.post("/api/math/number-theory", json={"operation":"isprime","n":97}))
        check("bank_sandbox", c.get("/api/banking/sandbox"))
        check("bank_analysis", c.get("/api/banking/analysis"))
        check("bank_simulation", c.post("/api/banking/simulate"))
        check("chat_no_api_key", c.post("/api/chat", json={"message":"status","domain":"core"}))
    assert len(checks) == 20
