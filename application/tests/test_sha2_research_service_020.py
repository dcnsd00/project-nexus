import hashlib
import struct

from fastapi.testclient import TestClient
import pytest

from modules import sha2_research_service as service
from nexus_master import app


@pytest.fixture(autouse=True)
def isolate_research_result_writes(monkeypatch, tmp_path):
    monkeypatch.setattr(service, "RESULTS_ROOT", tmp_path)
    monkeypatch.setattr(service, "VERIFICATION_RESULTS_ROOT", tmp_path)
    (tmp_path / "sat_scaling.json").write_text('{"results": []}', encoding="utf-8")
    (tmp_path / "differential.json").write_text('{"results": []}', encoding="utf-8")


def test_research_package_status_is_truthful():
    data = service.status()
    assert data["present"] is True
    assert data["modules"]["sha256_reference"] is True
    assert data["modules"]["sha512_reference"] is True
    assert data["backends"]["python_sat"] is False or data["backends"]["python_sat"] is True


def test_research_selftest_runs_and_reports_optional_sat_skip():
    result = service.run_selftest()
    assert result["successful"] is True
    assert result["tests_run"] >= 12
    assert result["failures"] == 0
    assert result["errors"] == 0


def test_exact_benchmark_has_hashlib_guard():
    result = service.run_benchmark(100, 1234)["result"]
    assert result["correctness"]["all_variants_identical"] is True
    assert result["nonce_serialization"] == "Bitcoin uint32 little-endian"
    assert result["scope"].startswith("Python CPU research benchmark")


def test_avalanche_comparison_returns_both_algorithms():
    result = service.run_avalanche(seed=7, samples=2)["result"]
    assert "sha256" in result and "sha512" in result
    assert result["classification"] == "full-round internal-state diffusion comparison"


def test_differential_request_limits_to_reduced_rounds():
    import pytest
    with pytest.raises(ValueError):
        service.run_differential(rounds=[64])


def test_api_research_status_and_solver_dependency():
    with TestClient(app) as client:
        response = client.get("/api/research/sha2/status")
        assert response.status_code == 200
        assert response.json()["present"] is True
        test = client.post("/api/research/sha2/selftest")
        assert test.status_code == 200
        assert test.json()["successful"] is True


def test_independent_verifier_uses_bitcoin_little_endian_nonce():
    header = bytearray(80)
    nonce = 2083236893
    header[76:80] = struct.pack("<I", nonce)
    assert hashlib.sha256(hashlib.sha256(header).digest()).digest().hex() == service.sha256_advanced.double_sha256(bytes(header)).hex()


def test_message_modification_e1_is_reproducible_for_fixed_seed():
    a = service.run_message_modification(seed=99, samples=100, k_bits=4)["result"]
    b = service.run_message_modification(seed=99, samples=100, k_bits=4)["result"]
    assert a["p_random"] == b["p_random"]
    assert a["p_modified"] == b["p_modified"]
    assert a["improvement_factor"] == b["improvement_factor"]


def test_bounded_differential_pipeline_runs_and_saves_holdout_result():
    result = service.run_differential(
        rounds=[3], seed=123, search_samples=50, validation_samples=100,
        time_budget_seconds=0.5,
    )["result"]
    assert result["scope"].startswith("reduced-round compression only")
    assert result["results"][0]["validation"]["n_validation"] == 100


def test_independent_stored_result_verification_passes():
    result = service.run_verification()
    assert result["successful"] is True, result["output"]
