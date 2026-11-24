"""Input and evidence-gate tests for Math Intelligence."""
import pytest

from modules.math_intelligence import solve_modular_congruence, triage_candidate


def test_modular_solver_returns_verified_solution_class():
    result = solve_modular_congruence(14, 30, 100)
    assert result["solvable"] is True
    assert result["one_solution"] == 45
    assert result["solution_count"] == 2
    assert result["verification"] is True


def test_modular_solver_reports_inconsistent_congruence():
    result = solve_modular_congruence(6, 5, 15)
    assert result["solvable"] is False


def test_candidate_triage_requires_independent_measured_evidence():
    result = triage_candidate({
        "baseline_hashrate": 100.0,
        "candidate_hashrate": 102.0,
        "duration_seconds": 300,
        "accepted_shares": 1000,
        "rejected_shares": 0,
        "exact_equivalence_verified": True,
        "independent_runs": 3,
    })
    assert result["verdict"] == "PROMISING_MEASURED_GAIN"
    assert result["eligible_for_manual_review"] is True
    assert result["auto_apply"] is False


@pytest.mark.parametrize("field,value", [
    ("duration_seconds", -1),
    ("accepted_shares", -1),
    ("rejected_shares", -1),
    ("independent_runs", -1),
    ("accepted_shares", 1.5),
    ("independent_runs", True),
])
def test_candidate_triage_rejects_invalid_counts(field, value):
    data = {
        "baseline_hashrate": 100,
        "candidate_hashrate": 102,
        "duration_seconds": 300,
        "accepted_shares": 1000,
        "rejected_shares": 0,
        "exact_equivalence_verified": True,
        "independent_runs": 3,
    }
    data[field] = value
    with pytest.raises(ValueError):
        triage_candidate(data)


@pytest.mark.parametrize("field,value", [
    ("baseline_hashrate", float("nan")),
    ("candidate_hashrate", float("inf")),
    ("baseline_hashrate", True),
    ("candidate_hashrate", -0.1),
])
def test_candidate_triage_rejects_non_finite_or_invalid_hashrates(field, value):
    data = {
        "baseline_hashrate": 100,
        "candidate_hashrate": 102,
        "duration_seconds": 300,
        "accepted_shares": 1000,
        "rejected_shares": 0,
        "exact_equivalence_verified": True,
        "independent_runs": 3,
    }
    data[field] = value
    with pytest.raises(ValueError):
        triage_candidate(data)


def test_candidate_triage_requires_boolean_equivalence_evidence():
    with pytest.raises(ValueError):
        triage_candidate({
            "baseline_hashrate": 100,
            "candidate_hashrate": 102,
            "duration_seconds": 300,
            "accepted_shares": 1000,
            "rejected_shares": 0,
            "exact_equivalence_verified": "yes",
            "independent_runs": 3,
        })
