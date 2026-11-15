import importlib
from modules import data_paths


def test_blockchain_regtest_import_does_not_create_output_directories(tmp_path, monkeypatch):
    monkeypatch.setattr(data_paths, "DATA_DIR", tmp_path / "nexus-data")
    module = importlib.import_module("modules.blockchain_regtest.nexus_v05_integration")
    module = importlib.reload(module)
    assert module.OUT == tmp_path / "nexus-data" / "blockchain" / "regtest"
    assert not module.OUT.exists()
