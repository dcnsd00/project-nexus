import importlib
from modules import data_paths


def test_fieldstation_loads_and_seeds_state_only_on_explicit_startup(tmp_path, monkeypatch):
    monkeypatch.setattr(data_paths, "DATA_DIR", tmp_path / "nexus-data")
    module = importlib.import_module("adapters.fieldstation.crypto_fieldstation.app")
    module = importlib.reload(module)

    assert not module.DATA_DIR.exists()
    module.ensure_data_loaded()

    assert module.DATA_DIR.is_dir()
    assert module.JOURNAL_FILE.is_file()
    assert "Aoi-RBB-077-S2" in module.JOURNALS
    assert module.ADDRESSES
    assert module.LEADS


def test_fieldstation_corrupt_state_is_preserved_before_recovery(tmp_path, monkeypatch):
    monkeypatch.setattr(data_paths, "DATA_DIR", tmp_path / "nexus-data")
    module = importlib.import_module("adapters.fieldstation.crypto_fieldstation.app")
    module = importlib.reload(module)
    module.DATA_DIR.mkdir(parents=True)
    module.JOURNAL_FILE.write_text("{broken json", encoding="utf-8")

    module.ensure_data_loaded()

    backup = module.JOURNAL_FILE.with_suffix(module.JOURNAL_FILE.suffix + ".corrupt-backup")
    assert backup.read_text(encoding="utf-8") == "{broken json"
    assert module.JOURNAL_FILE.is_file()
    assert "Aoi-RBB-077-S2" in module.JOURNALS
