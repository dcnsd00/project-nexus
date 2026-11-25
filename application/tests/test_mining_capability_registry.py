import json

from modules.mining_capability_registry import (
    algorithm_profile, catalog_coverage, evaluate_capability, normalize_algorithm,
)


def test_algorithm_aliases_normalize_to_shared_profiles():
    assert normalize_algorithm("rx/0") == "RandomX"
    assert normalize_algorithm("sha256d") == "SHA-256d"
    assert normalize_algorithm("pearlhash") == "PearlPow"


def test_randomx_is_cpu_only_and_does_not_claim_gpu_compatibility():
    result = evaluate_capability("RandomX", "GPU", "xmrig")
    assert result["compatible"] is False
    assert "device_class_not_supported_by_algorithm_profile" in result["reasons"]


def test_pool_algorithm_mismatch_is_a_hard_block():
    pool = {"id": "pool-x", "algorithm": "KawPoW", "stratum_protocol": "V1"}
    result = evaluate_capability("RandomX", "CPU", "xmrig", pool)
    assert result["compatible"] is False
    assert "pool_algorithm_mismatch" in result["reasons"]


def test_sha512_is_research_only_not_a_mining_pool_profile():
    result = algorithm_profile("SHA-512")
    assert result["status"] == "research_only"
    assert result["production_supported"] is False


def test_installed_backend_is_required_when_inventory_is_supplied():
    missing = evaluate_capability("RandomX", "CPU", "xmrig", installed_backends=[])
    found = evaluate_capability("RandomX", "CPU", "xmrig", installed_backends=["XMRig"])
    assert missing["compatible"] is False
    assert found["compatible"] is True
    assert found["matching_backend_detected"] is True


def test_catalog_coverage_reports_algorithms_without_claiming_live_validation(tmp_path):
    path = tmp_path / "pools.json"
    path.write_text(json.dumps({"pools": [
        {"id": "a", "algorithm": "KawPoW"},
        {"id": "b", "algorithm": "RandomX"},
        {"id": "c", "algorithm": "KawPoW"},
    ]}), encoding="utf-8")
    result = catalog_coverage(path)
    assert result["pool_profile_count"] == 3
    assert result["algorithm_count"] == 2
    assert result["catalog_is_live_validation"] is False

def test_catalog_only_algorithms_are_visible_but_fail_closed():
    for algorithm in ("Blake3", "Equihash-125-4", "X11", "Eaglesong",
                      "NexaPow", "Octopus", "Ethash", "Blake2s-Kadena",
                      "Blake2b-Sia", "zkSNARK", "XelisHash"):
        profile = algorithm_profile(algorithm)
        assert profile["status"] == "catalog_only"
        assert profile["production_supported"] is False
        result = evaluate_capability(algorithm, "GPU", "unverified-miner")
        assert result["compatible"] is False
