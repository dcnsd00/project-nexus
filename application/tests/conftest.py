"""Keep root-level tests away from packaged and shared SQLite databases."""
from __future__ import annotations

import sys
import pytest


@pytest.fixture(autouse=True)
def isolate_nexus_databases(tmp_path, monkeypatch):
    isolated = {
        ("nexus_wallet_manager", "DB"): tmp_path / "nexus_wallets_test.db",
        ("app.main", "DB"): tmp_path / "nexus_core_test.db",
        ("modules.earnings_intelligence", "DB_PATH"): tmp_path / "nexus_intelligence_test.db",
    }
    for (module_name, attribute), path in isolated.items():
        module = sys.modules.get(module_name)
        if module is not None and hasattr(module, attribute):
            monkeypatch.setattr(module, attribute, path)
    yield
