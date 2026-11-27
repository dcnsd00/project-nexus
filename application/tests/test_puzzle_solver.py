from __future__ import annotations

import base64
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from modules import puzzle_solver


def test_capabilities_distinguish_supported_and_experimental_strategies():
    data = puzzle_solver.capabilities()
    ids = {item["id"]: item for item in data["strategies"]}
    assert ids["text_decode"]["available"] is True
    assert ids["finite_csp"]["available"] is True
    assert ids["sha256_reduced_round_research"]["available"] is False


def test_text_decode_base64_and_caesar_candidates():
    encoded = base64.b64encode(b"NEXUS puzzle").decode("ascii")
    result = puzzle_solver.solve({"kind": "text_decode", "text": encoded})
    candidates = {item["text"] for item in result["candidates"]}
    assert "NEXUS puzzle" in candidates
    assert result["candidate_count"] >= 2


def test_modular_congruence_routes_to_existing_exact_solver():
    result = puzzle_solver.solve({"kind": "modular_congruence", "a": 14, "b": 30, "modulus": 100})
    assert result["solvable"] is True
    assert result["verified"] is True
    assert (14 * result["one_solution"] - 30) % 100 == 0


def test_linear_system_routes_to_exact_rational_solver():
    pytest.importorskip("sympy")
    result = puzzle_solver.solve({
        "kind": "linear_system",
        "matrix": [[2, 1], [1, -1]],
        "rhs": [5, 1],
    })
    assert result["verified"] is True
    assert result["solution"] == ["2", "1"]


def test_bitvector_xor_uses_verified_native_solution():
    result = puzzle_solver.solve({
        "kind": "bitvector_xor", "variables": ["a", "b", "c"],
        "target": 0xA5, "width": 8,
    })
    assert result["verified"] is True
    assert result["solution"]["a"] ^ result["solution"]["b"] ^ result["solution"]["c"] == 0xA5


def test_finite_csp_solves_and_verifies_all_different_sum_puzzle():
    result = puzzle_solver.solve({
        "kind": "finite_csp",
        "variables": {"x": [1, 2, 3], "y": [1, 2, 3]},
        "constraints": [
            {"type": "all_different", "variables": ["x", "y"]},
            {"type": "sum_eq", "variables": ["x", "y"], "target": 4},
        ],
    })
    assert result["status"] == "SOLVED"
    assert result["verified"] is True
    assert {tuple(sorted(item.values())) for item in result["solutions"]} == {(1, 3)}


def test_finite_csp_reports_unsat():
    result = puzzle_solver.solve({
        "kind": "finite_csp",
        "variables": {"x": [1], "y": [1]},
        "constraints": [{"type": "all_different", "variables": ["x", "y"]}],
    })
    assert result["status"] == "UNSAT"
    assert result["verified"] is False


def test_finite_csp_enforces_search_limits_and_rejects_expression_payloads():
    with pytest.raises(ValueError, match="search space"):
        puzzle_solver.solve({
            "kind": "finite_csp",
            "variables": {f"v{i}": list(range(1, 17)) for i in range(5)},
            "constraints": [{"type": "all_different", "variables": ["v0", "v1"]}],
        })
    with pytest.raises(ValueError, match="unsupported"):
        puzzle_solver.solve({
            "kind": "finite_csp",
            "variables": {"x": [1, 2]},
            "constraints": [{"type": "python_eval", "expression": "__import__('os').system('id')"}],
        })


def test_unknown_puzzle_kind_is_rejected():
    with pytest.raises(ValueError, match="unsupported kind"):
        puzzle_solver.solve({"kind": "unbounded_bruteforce"})



def test_binary_ascii_and_morse_decoding_candidates():
    binary = puzzle_solver.solve({"kind": "text_decode", "text": "01001000 01101001"})
    morse = puzzle_solver.solve({"kind": "text_decode", "text": ".... . .-.. .-.. ---"})
    assert "Hi" in {item["text"] for item in binary["candidates"]}
    assert "HELLO" in {item["text"] for item in morse["candidates"]}


def test_puzzle_solver_fastapi_routes_are_callable():
    app = FastAPI()
    app.include_router(puzzle_solver.router)
    client = TestClient(app)
    capabilities = client.get("/api/puzzles/capabilities")
    assert capabilities.status_code == 200
    assert capabilities.json()["module"] == "NEXUS Multi-Method Puzzle Solver"
    solved = client.post("/api/puzzles/solve", json={
        "problem": {"kind": "modular_congruence", "a": 7, "b": 1, "modulus": 10}
    })
    assert solved.status_code == 200
    assert solved.json()["verified"] is True
