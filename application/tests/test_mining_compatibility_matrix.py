from pathlib import Path

from modules.mining_capability_registry import compatibility_matrix
from mining.backend_adapters import backend_catalog


def test_matrix_covers_all_pool_profiles_without_claiming_live_status():
    root = Path(__file__).resolve().parents[1]
    result = compatibility_matrix(root / "mining" / "pools.json", backend_catalog())
    assert result["pool_profile_count"] == len(result["entries"])
    assert result["pool_profile_count"] >= 70
    assert result["is_static_profile_matrix"] is True
    assert result["live_pool_checks_performed"] is False
    assert result["execution_enabled"] is False


def test_matrix_separates_catalog_only_algorithms_from_backend_profile_matches():
    root = Path(__file__).resolve().parents[1]
    result = compatibility_matrix(root / "mining" / "pools.json", backend_catalog())
    catalog_only = [x for x in result["entries"] if x["algorithm"] == "Blake3"]
    assert catalog_only
    assert all(x["status"] == "catalog_only" for x in catalog_only)
    randomx = [x for x in result["entries"] if x["algorithm"] == "RandomX"]
    assert randomx
    assert all(any(b["backend_id"] in ("xmrig", "srbminer") for b in x["backend_matches"]) for x in randomx)


def test_matrix_never_invents_runtime_pool_state():
    root = Path(__file__).resolve().parents[1]
    result = compatibility_matrix(root / "mining" / "pools.json", backend_catalog())
    for row in result["entries"]:
        assert row["pool_reachable"] is None
        assert row["authorized"] is None
        assert row["job_received"] is None
        assert row["share_accepted"] is None
        assert row["payout_verified"] is None
