import os, sys
from pathlib import Path
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
os.environ["NEXUS_WALLET_DB"] = "/tmp/nexus-final-36u7x9dk/wallet.db"
os.environ["NEXUS_DB"] = "/tmp/nexus-final-36u7x9dk/core.db"
sys.path.insert(0, str(ROOT))
from nexus_master import app

def test_master_manifest_lists_all_modules():
    with TestClient(app) as c:
        r=c.get("/api/nexus/master")
        assert r.status_code == 200
        d=r.json()
        assert d["version"] == "0.10.25"
        assert all(d["modules"][k]["present"] for k in ("core","wallet_lab","blockchain_regtest","multiminer_x","fieldstation","crypto_engine"))
        assert d["provider_connectors_live"] == 0
        assert d["modules"]["integrations"]["present"] is True
        assert d["modules"]["sha2_research_package"]["present"] is True
        modules = c.get("/api/nexus/modules").json()
        assert "sha2_research" in modules

def test_mining_profiles_do_not_mix_units():
    with TestClient(app) as c:
        d=c.get("/api/mining/profiles").json()
        assert d["profiles"][0]["unit"] == "H/s"
        assert d["profiles"][3]["unit"] == "MiB/s"
        assert d["requested_targets"]["gpu"]["value"] == 5_000_000_000_000

def test_readiness_does_not_enable_public_writes():
    with TestClient(app) as c:
        d=c.get("/api/nexus/readiness").json()
        assert d["public_chain_writes_enabled"] is False
        assert "docker" in d["tools"] and "anvil" in d["tools"]

def test_hardware_endpoint_is_observational_only():
    with TestClient(app) as c:
        d=c.get("/api/mining/hardware").json()
        assert "cpu" in d and "gpu" in d
        assert "No miner is started" in d["warning"]

def test_original_core_health_remains_available():
    with TestClient(app) as c:
        d=c.get("/api/health").json()
        assert d["status"] == "ok"

def test_wallet_and_chain_sources_are_included():
    assert (ROOT/"modules"/"wallet_benchmark"/"nexus_wallet_benchmark.py").is_file()
    assert (ROOT/"modules"/"blockchain_regtest"/"nexus_v05_integration.py").is_file()
