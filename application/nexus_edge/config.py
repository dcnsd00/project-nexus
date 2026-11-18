"""Canonical configuration helpers for NEXUS EDGE persistence."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Mapping


def edge_database_path(env: Mapping[str, str] | None = None) -> Path:
    """Resolve one database path shared by MASTER and standalone EDGE adapters."""
    values = os.environ if env is None else env
    configured = values.get("NEXUS_EDGE_DATABASE")
    if configured:
        database = Path(configured).expanduser().resolve()
        database.parent.mkdir(parents=True, exist_ok=True)
        return database

    from modules.data_paths import data_path

    return data_path("db", "edge_state.sqlite3", create_parent=True)
