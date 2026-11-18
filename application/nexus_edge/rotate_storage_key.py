"""Offline NEXUS EDGE node-secret encryption-key rotation utility.

Stop NEXUS MASTER and every standalone EDGE process before running this tool.
"""
from __future__ import annotations

import argparse
import getpass
import os
import sqlite3
from contextlib import closing
from pathlib import Path

from .config import edge_database_path
from .sqlite_store import SQLiteEdgeStore


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Offline atomic rotation of the NEXUS EDGE SQLite encryption key"
    )
    parser.add_argument(
        "--database",
        help="EDGE SQLite database path (defaults to NEXUS_EDGE_DATABASE / NEXUS data path)",
    )
    args = parser.parse_args(argv)

    database = (
        Path(args.database).expanduser().resolve()
        if args.database
        else edge_database_path(dict(os.environ))
    )
    if not database.is_file():
        parser.error(f"EDGE database does not exist: {database}")
    with closing(sqlite3.connect(str(database))) as connection:
        tables = {
            row[0] for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
    required_tables = {
        "edge_nodes", "edge_tasks", "edge_protocol_sequences",
        "nexus_edge_schema", "edge_telemetry",
    }
    if not required_tables.issubset(tables):
        parser.error("database does not contain the complete NEXUS EDGE schema")

    print("WARNING: Stop NEXUS MASTER and all standalone EDGE processes first.")
    print("Create and verify a database backup before continuing.")
    old_key = getpass.getpass("Current NEXUS_EDGE_STORAGE_KEY: ").encode("ascii")
    new_key = getpass.getpass("New NEXUS_EDGE_STORAGE_KEY: ").encode("ascii")
    confirmation = getpass.getpass("Confirm new NEXUS_EDGE_STORAGE_KEY: ").encode("ascii")
    if new_key != confirmation:
        parser.error("new key confirmation does not match")
    if old_key == new_key:
        parser.error("new key must differ from current key")

    store = SQLiteEdgeStore(database, encryption_key=old_key)
    result = store.rotate_encryption_key(new_key)
    print(
        f"Rotation complete: {result['nodes_reencrypted']} node credentials re-encrypted."
    )
    print("Update NEXUS_EDGE_STORAGE_KEY in the protected service environment.")
    print("Do not restart NEXUS until the new key has been installed and verified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
