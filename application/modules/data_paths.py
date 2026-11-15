"""Central, portable paths for all NEXUS mutable runtime data.

Source code remains inside the application tree. Databases, logs, caches and
research outputs are written under one user data directory, configurable with
NEXUS_DATA_DIR. This module has no filesystem side effects on import.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path


def default_data_dir() -> Path:
    override = os.environ.get("NEXUS_DATA_DIR")
    if override:
        return Path(override).expanduser().resolve()
    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA")
        return (Path(base) if base else Path.home() / "AppData" / "Local") / "NEXUS"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "NEXUS"
    base = os.environ.get("XDG_DATA_HOME")
    return (Path(base) if base else Path.home() / ".local" / "share") / "nexus"


DATA_DIR = default_data_dir()


def data_path(*parts: str, create_parent: bool = True) -> Path:
    """Return a path under the central NEXUS data directory."""
    if not parts or any(Path(part).is_absolute() or ".." in Path(part).parts for part in parts):
        raise ValueError("NEXUS data path must be a non-empty relative path")
    target = DATA_DIR.joinpath(*parts).resolve()
    if not target.is_relative_to(DATA_DIR):
        raise ValueError("NEXUS data path escapes the configured data directory")
    if create_parent:
        target.parent.mkdir(parents=True, exist_ok=True)
    return target


def data_layout() -> dict[str, str]:
    """Describe canonical mutable-data locations without creating them."""
    return {
        "root": str(DATA_DIR),
        "databases": str(DATA_DIR / "db"),
        "logs": str(DATA_DIR / "logs"),
        "research": str(DATA_DIR / "research"),
        "mining": str(DATA_DIR / "mining"),
        "cache": str(DATA_DIR / "cache"),
    }
