from __future__ import annotations

import base64
import math
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from modules import puzzle_solver


def make_phy_project():
    boxes = []
    centre_x, centre_y = 1023.5, 1024.5
    for index in range(128):
        angle = math.radians(index * 2.8)
        radius = 250.0 + index * 2.0
        for side, offset, emoji in (
            (0, 0.0, "1F468"),
            (1, math.pi, "1F600"),
        ):
            boxes.append({
                "id": index * 2 + side + 1,
                "x": centre_x + radius * math.cos(angle + offset),
                "y": centre_y + radius * math.sin(angle + offset),
                "w": 0,
                "h": 0,
                "char": "test",
                "name": "test emoji",
                "unified": emoji,
            })
    boxes.append({
        "id": 258, "x": centre_x, "y": centre_y, "w": 0, "h": 0,
        "char": "b", "name": "BITCOIN LOGO CENTER", "unified": "0062",
    })
    return {"natW": 2048, "natH": 2048, "boxes": boxes}


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


def test_classical_atbash_and_a1z26_decoders():
    text_result = puzzle_solver.solve({"kind": "text_decode", "text": "SVOOL"})
    candidates = {item["text"]: item["method"] for item in text_result["candidates"]}
    assert candidates["HELLO"] == "atbash"
    number_result = puzzle_solver.solve({"kind": "text_decode", "text": "8-5-12-12-15"})
    assert "HELLO" in {item["text"] for item in number_result["candidates"]}


def test_vigenere_rail_fence_and_affine_known_parameter_decoders():
    assert puzzle_solver.solve({
        "kind": "vigenere", "text": "LXFOPVEFRNHR", "key": "LEMON"
    })["plaintext"] == "ATTACKATDAWN"
    assert puzzle_solver.solve({
        "kind": "rail_fence", "text": "WECRLTEERDSOEEFEAOCAIVDEN", "rails": 3
    })["plaintext"] == "WEAREDISCOVEREDFLEEATONCE"
    assert puzzle_solver.solve({
        "kind": "affine_substitution", "text": "IHHWVC", "a": 5, "b": 8
    })["plaintext"] == "AFFINE"


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


def test_finite_csp_sum_constraint_handles_negative_domains():
    result = puzzle_solver.solve({
        "kind": "finite_csp",
        "variables": {"x": [5], "y": [-2, -1]},
        "constraints": [{"type": "sum_eq", "variables": ["x", "y"], "target": 3}],
    })
    assert result["status"] == "SOLVED"
    assert result["solutions"] == [{"x": 5, "y": -2}]
    assert result["verified"] is True


def test_finite_csp_rejects_duplicate_variable_names_in_constraint():
    with pytest.raises(ValueError, match="must be unique"):
        puzzle_solver.solve({
            "kind": "finite_csp",
            "variables": {"x": [1, 2], "y": [1, 2]},
            "constraints": [{"type": "sum_eq", "variables": ["x", "x"], "target": 2}],
        })


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


def test_phy_challenge_is_exposed_as_a_bounded_puzzle_strategy():
    capabilities = puzzle_solver.capabilities()
    strategy = next(item for item in capabilities["strategies"]
                    if item["id"] == "phy_challenge_structure")
    assert strategy["available"] is True
    assert strategy["private_key_search"] is False


def test_phy_challenge_dispatch_requires_public_mapping_payload():
    with pytest.raises(ValueError, match="project_file"):
        puzzle_solver.solve({"kind": "phy_challenge"})


def test_phy_challenge_dispatch_reaches_offline_analyzer():
    result = puzzle_solver.solve({
        "kind": "phy_challenge",
        "project_file": make_phy_project(),
    })
    assert result["kind"] == "phy_challenge"
    assert result["status"] == "structural_analysis_only"
    assert result["pair_count"] == 128
    assert result["reference_observations"]["forum_reported_canvas_id_at_index_86"] == 217


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
    phy = client.post("/api/puzzles/solve", json={
        "problem": {"kind": "phy_challenge", "project_file": make_phy_project()}
    })
    assert phy.status_code == 200
    assert phy.json()["kind"] == "phy_challenge"
    assert phy.json()["pair_count"] == 128
