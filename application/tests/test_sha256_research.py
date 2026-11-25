import os, sys
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("NEXUS_WALLET_DB", "/tmp/nexus-sha-research-wallet.db")
os.environ.setdefault("NEXUS_DB", "/tmp/nexus-sha-research-core.db")
sys.path.insert(0, str(ROOT))

from modules.sha256_research.sha256_core import compress, verify_against_hashlib
from modules.sha256_research.lab import run_differential, run_round_sweep
from nexus_master import app


def test_full_sha256_matches_hashlib_vectors():
    assert verify_against_hashlib()["passed"] is True


def test_round_validation_rejects_2000_internal_rounds():
    with pytest.raises(ValueError):
        compress([0] * 16, 2000)


def test_word_14_not_absorbed_before_round_15():
    result = run_differential(14, 128, word=14, input_bit=0, seed=22)
    assert result["zero_output_difference_samples"] == 128
    assert result["input_delta_effect"] == "no_observed_effect_in_any_sample"
    assert result["best_output_bit"]["z_score"] is None


def test_word_14_begins_affecting_at_round_15():
    result = run_differential(15, 128, word=14, input_bit=0, seed=23)
    assert result["zero_output_difference_samples"] == 0
    assert result["mean_changed_output_bits"] > 0


def test_differential_is_reproducible_with_seed():
    a = run_differential(20, 200, 14, 0, 123)
    b = run_differential(20, 200, 14, 0, 123)
    assert a["mean_changed_output_bits"] == b["mean_changed_output_bits"]
    assert a["best_output_bit"]["flips"] == b["best_output_bit"]["flips"]


def test_round_sweep_applies_familywise_correction():
    result = run_round_sweep([14, 15, 20, 21], 128, 14, 0, 44)
    assert result["family_size_for_multiple_testing_correction"] == 4 * 256
    assert len(result["results"]) == 4
    assert result["results"][0]["p_familywise_bonferroni_exact"] is None


def test_research_api_info_and_run():
    with TestClient(app) as client:
        info = client.get("/api/research/sha256/info")
        assert info.status_code == 200
        assert info.json()["standard_sha256_rounds"] == 64
        run = client.post("/api/research/sha256/differential", json={
            "rounds": 20, "samples": 128, "word": 14, "input_bit": 0, "seed": 55
        })
        assert run.status_code == 200
        assert run.json()["result"]["samples"] == 128
        assert run.json()["result"]["consensus_compatible"] is False


def test_research_api_rejects_nonstandard_2000_round_request():
    with TestClient(app) as client:
        response = client.post("/api/research/sha256/differential", json={
            "rounds": 2000, "samples": 2000, "word": 14, "input_bit": 0
        })
        assert response.status_code == 422


def test_multi_delta_patterns_cover_single_and_multi_bit_inputs():
    from modules.sha256_research.lab import run_multi_delta_sweep
    result = run_multi_delta_sweep(20, 128, 777)
    assert len(result["results"]) == 8
    assert any(x["input_delta"]["active_bit_count"] > 1 for x in result["results"])
    assert result["consensus_compatible"] is False


def test_research_api_multi_delta_route():
    with TestClient(app) as client:
        response = client.post("/api/research/sha256/multi-delta", json={
            "rounds": 20, "samples": 128, "seed": 99
        })
        assert response.status_code == 200
        assert len(response.json()["result"]["results"]) == 8


def test_research_api_uses_unique_run_ids():
    with TestClient(app) as client:
        payload = {"rounds": 20, "samples": 128, "word": 14, "input_bit": 0, "seed": 56}
        first = client.post("/api/research/sha256/differential", json=payload)
        second = client.post("/api/research/sha256/differential", json=payload)
        assert first.status_code == second.status_code == 200
        assert first.json()["run_id"] != second.json()["run_id"]


def test_compression_carry_trace_matches_reference_output():
    from modules.sha256_research.sha256_core import (
        compress_schedule, compress_schedule_with_round_carries, expand_schedule
    )
    import random
    rng = random.Random(1234)
    schedule = expand_schedule([rng.getrandbits(32) for _ in range(16)])
    out_a = compress_schedule(schedule, 64)
    out_b, trace = compress_schedule_with_round_carries(schedule, 64)
    assert out_a == out_b
    assert len(trace) == 64
    assert all(len(row) == 7 and all(bit in (0, 1) for bit in row) for row in trace)


def test_compression_carry_differential_api():
    from modules.sha256_research.lab import run_compression_carry_differential
    result = run_compression_carry_differential(20, 128, 14, 0, 4321)
    assert result["consensus_compatible"] is False
    assert len(result["per_round_operation_results"]) == 20 * 7
    assert all(0.0 <= x["carry_decision_mismatch_rate"] <= 1.0
               for x in result["per_round_operation_results"])


def test_research_api_compression_carries_route():
    with TestClient(app) as client:
        response = client.post("/api/research/sha256/compression-carries", json={
            "rounds": 12, "samples": 128, "word": 14, "input_bit": 0, "seed": 9
        })
        assert response.status_code == 200
        assert len(response.json()["result"]["per_round_operation_results"]) == 12 * 7
