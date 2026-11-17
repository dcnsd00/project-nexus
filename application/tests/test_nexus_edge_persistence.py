import sqlite3
import tempfile
import unittest
from pathlib import Path

from nexus_edge import EdgeError, EdgeManager, sign_message
from nexus_edge.persistence import (
    EdgeStorageError, InMemoryEdgeKeyProvider, SQLiteEdgeStore,
)


class Clock:
    def __init__(self, value=1_800_000_000.0):
        self.value = value

    def __call__(self):
        return self.value


class EdgePersistenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp.name) / "edge.sqlite3"
        self.clock = Clock()
        self.provider = InMemoryEdgeKeyProvider()
        self.secret = b"nexus-edge-persist-key-32-bytes!!"

    def tearDown(self):
        self.temp.cleanup()

    def manager(self, provider=None):
        store = SQLiteEdgeStore(self.db_path)
        return EdgeManager(
            clock=self.clock, heartbeat_ttl_s=60, lease_s=20,
            store=store, key_provider=provider or self.provider,
        )

    def heartbeat(self, manager, sequence=1):
        timestamp = self.clock()
        message = {
            "protocol_version": 1, "kind": "heartbeat",
            "node_id": "edge-c5-persist", "timestamp": timestamp,
            "sequence": sequence,
        }
        return manager.heartbeat(
            "edge-c5-persist", timestamp, sequence,
            sign_message(self.secret, message),
        )

    def test_persistent_store_requires_external_key_provider(self):
        store = SQLiteEdgeStore(self.db_path)
        try:
            with self.assertRaisesRegex(EdgeError, "external key provider"):
                EdgeManager(store=store)
        finally:
            store.close()

    def test_restores_nodes_tasks_sequences_and_active_leases_after_store_reopen(self):
        first = self.manager()
        first.register_node("edge-c5-persist", ["telemetry"], self.secret)
        self.heartbeat(first, sequence=4)
        task = first.submit_task(
            "telemetry.collect", {"sensor": "temp"}, ["telemetry"]
        )
        claimed = first.claim_task("edge-c5-persist")
        first.start_task("edge-c5-persist", task["task_id"])
        first.close()

        second = self.manager()
        try:
            node = second.node_status("edge-c5-persist")
            restored = second.task_status(task["task_id"])
            self.assertEqual(node["last_heartbeat_sequence"], 4)
            self.assertTrue(node["online"])
            self.assertIn(task["task_id"], node["active_tasks"])
            self.assertEqual(restored["state"], "RUNNING")
            self.assertEqual(restored["assignment_nonce"], claimed["assignment_nonce"])
            self.assertTrue(second.snapshot()["persistence_enabled"])
        finally:
            second.close()

    def test_result_sequence_survives_store_reopen(self):
        first = self.manager()
        first.register_node("edge-c5-persist", ["telemetry"], self.secret)
        self.heartbeat(first)
        task_one = first.submit_task(
            "telemetry.collect", {"n": 1}, ["telemetry"]
        )
        claim_one = first.claim_task("edge-c5-persist")
        first.start_task("edge-c5-persist", task_one["task_id"])
        result = {"ok": True}
        message = {
            "protocol_version": 1, "kind": "task_result",
            "node_id": "edge-c5-persist", "task_id": task_one["task_id"],
            "assignment_nonce": claim_one["assignment_nonce"],
            "sequence": 7, "result": result,
        }
        first.complete_task(
            "edge-c5-persist", task_one["task_id"], result, 7,
            claim_one["assignment_nonce"], sign_message(self.secret, message),
        )
        first.close()

        second = self.manager()
        try:
            task_two = second.submit_task(
                "telemetry.collect", {"n": 2}, ["telemetry"]
            )
            claim_two = second.claim_task("edge-c5-persist")
            second.start_task("edge-c5-persist", task_two["task_id"])
            replay = {
                "protocol_version": 1, "kind": "task_result",
                "node_id": "edge-c5-persist", "task_id": task_two["task_id"],
                "assignment_nonce": claim_two["assignment_nonce"],
                "sequence": 7, "result": result,
            }
            with self.assertRaisesRegex(EdgeError, "replayed"):
                second.complete_task(
                    "edge-c5-persist", task_two["task_id"], result, 7,
                    claim_two["assignment_nonce"],
                    sign_message(self.secret, replay),
                )
        finally:
            second.close()

    def test_database_schema_never_contains_node_key_columns(self):
        manager = self.manager()
        manager.register_node("edge-c5-persist", ["telemetry"], self.secret)
        manager.close()
        connection = sqlite3.connect(self.db_path)
        try:
            columns = {
                row[1] for row in connection.execute("PRAGMA table_info(edge_nodes)")
            }
            self.assertNotIn("secret", columns)
            self.assertNotIn("private_key", columns)
            self.assertIn("last_heartbeat_sequence", columns)
        finally:
            connection.close()

    def test_missing_key_fails_closed_on_restore(self):
        first = self.manager()
        first.register_node("edge-c5-persist", ["telemetry"], self.secret)
        first.close()
        store = SQLiteEdgeStore(self.db_path)
        try:
            with self.assertRaisesRegex(EdgeError, "secure key unavailable"):
                EdgeManager(
                    store=store, key_provider=InMemoryEdgeKeyProvider()
                )
        finally:
            store.close()

    def test_future_schema_is_rejected(self):
        connection = sqlite3.connect(self.db_path)
        try:
            connection.execute("PRAGMA user_version=99")
        finally:
            connection.close()
        with self.assertRaisesRegex(EdgeStorageError, "newer than supported"):
            SQLiteEdgeStore(self.db_path)


if __name__ == "__main__":
    unittest.main()
