import importlib

import pytest

from modules import data_paths


def test_data_path_uses_single_central_root(tmp_path, monkeypatch):
    monkeypatch.setattr(data_paths, "DATA_DIR", tmp_path.resolve())
    target = data_paths.data_path("research", "sha2", "runs", "result.json")
    assert target == tmp_path / "research" / "sha2" / "runs" / "result.json"
    assert not target.parent.exists()
    data_paths.data_path("research", "sha2", "runs", "result.json", create_parent=True)
    assert not target.parent.exists()
    data_paths.data_path("research", "sha2", "runs", "result.json", create_parent=True)
    assert target.parent.is_dir()


@pytest.mark.parametrize("parts", [("../escape",), ("/absolute/path",), ("safe", "..", "escape")])
def test_data_path_rejects_paths_outside_central_root(parts, tmp_path, monkeypatch):
    monkeypatch.setattr(data_paths, "DATA_DIR", tmp_path.resolve())
    with pytest.raises(ValueError):
        data_paths.data_path(*parts)


def test_default_data_dir_honors_nexus_data_dir_override(monkeypatch, tmp_path):
    monkeypatch.setenv("NEXUS_DATA_DIR", str(tmp_path / "nexus-data"))
    assert data_paths.default_data_dir() == (tmp_path / "nexus-data").resolve()
