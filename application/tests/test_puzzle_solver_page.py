from fastapi.testclient import TestClient

from nexus_master import app


def _client():
    return TestClient(app, base_url="http://127.0.0.1", client=("127.0.0.1", 53124))


def test_puzzle_solver_page_is_served_by_existing_nexus_app():
    with _client() as client:
        response = client.get("/puzzles")
    assert response.status_code == 200
    assert "NEXUS · Multi-Method Puzzle Solver" in response.text
    assert "/api/puzzles/capabilities" in response.text
    assert "/api/puzzles/solve" in response.text
    assert "finite_csp" in response.text


def test_dashboard_links_to_the_puzzle_solver_page():
    with _client() as client:
        response = client.get("/api/nexus/dashboard")
    assert response.status_code == 200
    assert 'href="/puzzles"' in response.text
    assert "Puzzle Solver" in response.text


def test_solver_page_never_renders_user_input_as_html():
    with _client() as client:
        page = client.get("/puzzles")
    assert page.status_code == 200
    assert 'textContent=JSON.stringify(payload,null,2)' in page.text
    assert '$("result").textContent="Eroare: "+error.message' in page.text
