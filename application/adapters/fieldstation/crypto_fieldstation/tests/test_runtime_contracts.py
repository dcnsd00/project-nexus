"""Runtime-boundary tests for Crypto Fieldstation."""
import importlib.util
from pathlib import Path
from unittest.mock import patch


def test_import_does_not_create_miner_directory_or_start_server():
    app_file = Path(__file__).resolve().parents[1] / "app.py"
    application_root = Path(__file__).resolve().parents[4]
    import sys
    if str(application_root) not in sys.path:
        sys.path.insert(0, str(application_root))

    original_mkdir = Path.mkdir
    miner_directory_calls = []

    def tracked_mkdir(path, *args, **kwargs):
        if path.name == "miners" and path.parent == app_file.parent:
            miner_directory_calls.append(path)
        return original_mkdir(path, *args, **kwargs)

    spec = importlib.util.spec_from_file_location("fieldstation_import_probe", app_file)
    module = importlib.util.module_from_spec(spec)
    with patch.object(Path, "mkdir", tracked_mkdir):
        spec.loader.exec_module(module)

    assert miner_directory_calls == []
    assert module.SERVER is None
    assert module.STATE["running"] is False


def test_fieldstation_binds_only_to_loopback_by_default():
    app_file = Path(__file__).resolve().parents[1] / "app.py"
    application_root = Path(__file__).resolve().parents[4]
    import sys
    if str(application_root) not in sys.path:
        sys.path.insert(0, str(application_root))
    spec = importlib.util.spec_from_file_location("fieldstation_loopback_probe", app_file)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.HOST == "127.0.0.1"
    assert module.SERVER is None
