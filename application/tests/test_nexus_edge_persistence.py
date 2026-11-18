"""Additional EDGE durability invariants not covered by the store contract suite."""
import sqlite3
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from cryptography.fernet import Fernet

from nexus_edge import (
    EdgeError,
    EdgeManager,
    EdgePersistenceError,
    ReplayError,
    SQLiteEdgeStore,
    SQLiteReplayGuard,
    sign_message,
)


class Clock:
    def __init__(self, value=1_800_000_000.0):
        self.value = value

    def __call__(self):
        return self.value


class EdgePersistenceInvariantTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.database = Path(self.temp_dir.name) / "edge.sqlite3"
        self.key = Fernet.generate_key()
        self.clock = Clock()
        self.secret = b"nexus-edge-persistence-test-secret"
        self.node_id = "edge-c5-persist-01"

    def manager(self):
        return EdgeManager(
            clock=self.clock,
            heartbeat_ttl_s=30,
            lease_s=10,
            replay_guard=SQLiteReplayGuard(self.database),
            store=SQLiteEdgeStore(self.database, encryption_key=self.key),
        )

    def register_online_node(self, manager):
        manager.register_node(self.node_id, ["math.verify"], self.secret)
        timestamp = self.clock()
        message = {
            "kind": "heartbeat",
            "node_id": self.node_id,
            "timestamp": timestamp,
            "sequence": 1,
        }
        manager.heartbeat(
            self.node_id, timestamp, 1, sign_message(self.secret, message)
        )

    def test_completed_task_and_result_survive_manager_restart(self):
        first = self.manager()
        self.register_online_node(first)
        task = first.submit_task(
            "math.verify", {"input": "NEXUS"}, ["math.verify"]
        )
        claim = first.claim_task(self.node_id)
        assignment_nonce = claim["assignment_nonce"]
        first.start_task(self.node_id, task["task_id"])

        # The worker's lease token must remain valid across a MASTER restart.
        restarted = self.manager()
        self.assertEqual(restarted.snapshot()["mode"], "sqlite_persistent")
        self.assertEqual(restarted.task_status(task["task_id"])["state"], "RUNNING")
        result = {"verified": True, "digest": "abc123"}
        signed_result = {
            "kind": "task_result",
            "node_id": self.node_id,
            "task_id": task["task_id"],
            "assignment_nonce": assignment_nonce,
            "result": result,
        }
        completed = restarted.complete_task(
            self.node_id,
            task["task_id"],
            result,
            assignment_nonce,
            sign_message(self.secret, signed_result),
        )

        restored = self.manager().task_status(task["task_id"])
        self.assertEqual(restored["state"], "SUCCEEDED")
        self.assertEqual(restored["result"], result)
        self.assertEqual(restored["result_sha256"], completed["result_sha256"])
        node_rows = restarted.list_nodes()
        task_rows = restarted.list_tasks()
        self.assertNotIn(self.secret.decode("ascii"), str(node_rows))
        self.assertNotIn("payload", task_rows[0])
        self.assertNotIn("result", task_rows[0])
        self.assertTrue(task_rows[0]["result_available"])

    def test_rotated_node_secret_and_sequence_survive_restart(self):
        first = self.manager()
        self.register_online_node(first)
        new_secret = b"nexus-edge-rotated-node-secret-32-bytes"
        rotated = first.rotate_node_secret(self.node_id, new_secret)
        self.assertFalse(rotated["online"])
        self.assertEqual(first.next_node_sequence(self.node_id), 2)

        restarted = self.manager()
        self.assertEqual(restarted.next_node_sequence(self.node_id), 2)
        timestamp = self.clock()
        new_message = {
            "kind": "heartbeat",
            "node_id": self.node_id,
            "timestamp": timestamp,
            "sequence": 2,
        }
        restarted.heartbeat(
            self.node_id, timestamp, 2,
            sign_message(new_secret, new_message),
        )

        old_message = dict(new_message, sequence=3)
        with self.assertRaisesRegex(EdgeError, "invalid heartbeat signature"):
            restarted.heartbeat(
                self.node_id, timestamp, 3,
                sign_message(self.secret, old_message),
            )

    def test_store_migrates_existing_schema_version_one_to_four(self):
        store = SQLiteEdgeStore(self.database, encryption_key=self.key)
        with sqlite3.connect(self.database) as connection:
            connection.execute(
                "UPDATE nexus_edge_schema SET version = 1 WHERE component = 'edge_store'"
            )
            connection.execute("DROP TABLE edge_telemetry")

        migrated = SQLiteEdgeStore(self.database, encryption_key=self.key)
        self.assertEqual(migrated.telemetry_count(), 0)
        with sqlite3.connect(self.database) as connection:
            version = connection.execute(
                "SELECT version FROM nexus_edge_schema WHERE component = 'edge_store'"
            ).fetchone()[0]
            tables = {
                row[0] for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                )
            }
        self.assertEqual(version, 4)
        self.assertIn("edge_telemetry", tables)

    def test_store_migrates_schema_version_two_to_four(self):
        SQLiteEdgeStore(self.database, encryption_key=self.key)
        with sqlite3.connect(self.database) as connection:
            connection.execute("DROP TABLE edge_telemetry")
            connection.execute("""
                CREATE TABLE edge_telemetry (
                    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    node_id TEXT NOT NULL,
                    received_at REAL NOT NULL,
                    transport TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    payload_sha256 TEXT NOT NULL
                )
            """)
            connection.execute(
                "UPDATE nexus_edge_schema SET version = 2 WHERE component = 'edge_store'"
            )

        migrated = SQLiteEdgeStore(self.database, encryption_key=self.key)
        self.assertEqual(migrated.telemetry_count(), 0)
        with sqlite3.connect(self.database) as connection:
            version = connection.execute(
                "SELECT version FROM nexus_edge_schema WHERE component = 'edge_store'"
            ).fetchone()[0]
            columns = {
                row[1] for row in connection.execute(
                    "PRAGMA table_info(edge_telemetry)"
                )
            }
        self.assertEqual(version, 4)
        self.assertIn("sequence", columns)

    def test_v3_running_task_without_lease_token_is_requeued_after_migration(self):
        first = self.manager()
        self.register_online_node(first)
        task = first.submit_task(
            "math.verify", {"input": "legacy-v3"}, ["math.verify"]
        )
        first.claim_task(self.node_id)
        first.start_task(self.node_id, task["task_id"])

        # Simulate a database created by schema v3, before lease tokens existed.
        with sqlite3.connect(self.database) as connection:
            connection.execute("ALTER TABLE edge_tasks DROP COLUMN assignment_nonce")
            connection.execute(
                "UPDATE nexus_edge_schema SET version = 3 WHERE component = 'edge_store'"
            )

        restarted = self.manager()
        recovered = restarted.task_status(task["task_id"])
        self.assertEqual(recovered["state"], "QUEUED")
        self.assertIsNone(recovered["node_id"])
        self.assertIsNone(recovered["lease_until"])
        with sqlite3.connect(self.database) as connection:
            version = connection.execute(
                "SELECT version FROM nexus_edge_schema WHERE component = 'edge_store'"
            ).fetchone()[0]
        self.assertEqual(version, 4)

        fresh_claim = restarted.claim_task(self.node_id)
        self.assertTrue(fresh_claim["assignment_nonce"])

    def test_authenticated_telemetry_is_persisted_and_survives_restart(self):
        first = self.manager()
        self.register_online_node(first)
        payload = {"temperature_c": 21.75, "battery_pct": 94}
        timestamp = self.clock()
        message = {
            "kind": "node_request",
            "action": "https.uplink",
            "node_id": self.node_id,
            "timestamp": timestamp,
            "sequence": 2,
            "payload": payload,
        }
        event = first.authenticate_and_record_telemetry(
            self.node_id, "https.uplink", timestamp, 2, payload,
            sign_message(self.secret, message), transport="https",
        )
        self.assertEqual(event["transport"], "https")
        self.assertEqual(len(event["payload_sha256"]), 64)
        self.assertEqual(first.snapshot()["telemetry_total"], 1)

        duplicate = first.authenticate_and_record_telemetry(
            self.node_id, "https.uplink", timestamp, 2, payload,
            sign_message(self.secret, message), transport="https",
        )
        self.assertTrue(duplicate["duplicate"])
        self.assertEqual(first.snapshot()["telemetry_total"], 1)

        restarted = self.manager()
        history = restarted.telemetry(limit=10)
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["event_id"], event["event_id"])
        self.assertEqual(history[0]["payload"], payload)
        self.assertEqual(restarted.snapshot()["telemetry_total"], 1)

    def test_telemetry_ledger_prunes_oldest_events_at_configured_bound(self):
        manager = self.manager()
        manager.register_node(self.node_id, ["telemetry"], self.secret)
        store = manager._store
        store.MAX_TELEMETRY_EVENTS = 3
        store.TELEMETRY_PRUNE_INTERVAL = 1
        for sequence in range(1, 6):
            store.accept_and_append_telemetry(
                node_id=self.node_id,
                sequence=sequence,
                received_at=self.clock() + sequence,
                transport="https",
                payload={"sample": sequence},
            )
        history = store.list_telemetry(limit=10)
        self.assertEqual([row["sequence"] for row in history], [5, 4, 3])
        self.assertEqual(store.telemetry_count(), 3)
        self.assertIsNone(store.get_telemetry_event(self.node_id, 1))

    def test_failed_telemetry_commit_does_not_consume_sequence_and_can_retry(self):
        manager = self.manager()
        self.register_online_node(manager)
        store = manager._store
        original = store.accept_and_append_telemetry

        def fail_commit(**kwargs):
            raise OSError("simulated SQLite write failure")

        store.accept_and_append_telemetry = fail_commit
        timestamp = self.clock()
        payload = {"temperature_c": 19.5}
        message = {
            "kind": "node_request",
            "action": "mqtt.uplink",
            "node_id": self.node_id,
            "timestamp": timestamp,
            "sequence": 2,
            "payload": payload,
        }
        signature = sign_message(self.secret, message)
        with self.assertRaises(EdgePersistenceError):
            manager.authenticate_and_record_telemetry(
                self.node_id, "mqtt.uplink", timestamp, 2, payload,
                signature, transport="mqtts",
            )
        self.assertEqual(manager.next_node_sequence(self.node_id), 2)

        store.accept_and_append_telemetry = original
        accepted = manager.authenticate_and_record_telemetry(
            self.node_id, "mqtt.uplink", timestamp, 2, payload,
            signature, transport="mqtts",
        )
        self.assertFalse(accepted["duplicate"])
        self.assertEqual(manager.next_node_sequence(self.node_id), 3)

    def test_authenticated_telemetry_refreshes_node_liveness_durably(self):
        manager = self.manager()
        manager.register_node(self.node_id, ["telemetry"], self.secret)
        timestamp = self.clock()
        payload = {"temperature_c": 20.0}
        message = {
            "kind": "node_request",
            "action": "https.uplink",
            "node_id": self.node_id,
            "timestamp": timestamp,
            "sequence": 1,
            "payload": payload,
        }
        manager.authenticate_and_record_telemetry(
            self.node_id, "https.uplink", timestamp, 1, payload,
            sign_message(self.secret, message), transport="https",
        )
        self.assertTrue(manager.node_status(self.node_id)["online"])

        restarted = self.manager()
        self.assertTrue(restarted.node_status(self.node_id)["online"])

    def test_telemetry_rejects_unknown_nodes_invalid_transport_and_oversized_payload(self):
        manager = self.manager()
        self.register_online_node(manager)
        timestamp = self.clock()
        with self.assertRaisesRegex(EdgeError, "unknown node"):
            manager.authenticate_and_record_telemetry(
                "edge-c5-unknown", "https.uplink", timestamp, 2,
                {"value": 1}, "bad", transport="https",
            )
        with self.assertRaisesRegex(EdgeError, "unsupported telemetry transport"):
            manager.authenticate_and_record_telemetry(
                self.node_id, "https.uplink", timestamp, 2,
                {"value": 1}, "bad", transport="raw",
            )
        tiny = EdgeManager(
            clock=self.clock,
            max_payload_bytes=128,
            replay_guard=SQLiteReplayGuard(self.database),
            store=SQLiteEdgeStore(self.database, encryption_key=self.key),
        )
        with self.assertRaisesRegex(EdgeError, "payload exceeds configured size limit"):
            tiny.authenticate_and_record_telemetry(
                self.node_id, "https.uplink", timestamp, 2,
                {"data": "x" * 256}, "bad", transport="https",
            )

    def test_concurrent_replay_acceptance_is_atomic(self):
        guard = SQLiteReplayGuard(self.database)

        def attempt_acceptance():
            try:
                guard.accept(self.node_id, 7)
                return True
            except ReplayError:
                return False

        with ThreadPoolExecutor(max_workers=8) as executor:
            accepted = list(executor.map(
                lambda _: attempt_acceptance(), range(16)
            ))

        self.assertEqual(sum(accepted), 1)

    def test_storage_key_rotation_reencrypts_node_secrets(self):
        old_key = self.key
        new_key = Fernet.generate_key()
        store = SQLiteEdgeStore(self.database, encryption_key=old_key)
        manager = EdgeManager(
            clock=self.clock,
            replay_guard=SQLiteReplayGuard(self.database),
            store=store,
        )
        manager.register_node(self.node_id, ["telemetry"], self.secret)

        result = store.rotate_encryption_key(new_key)
        self.assertEqual(result, {"nodes_reencrypted": 1})
        restored = SQLiteEdgeStore(
            self.database, encryption_key=new_key
        ).load_state()
        self.assertEqual(restored["nodes"][0]["secret"], self.secret)

        with self.assertRaisesRegex(RuntimeError, "cannot decrypt EDGE credential"):
            SQLiteEdgeStore(
                self.database, encryption_key=old_key
            ).load_state()

    def test_failed_storage_key_rotation_leaves_database_unchanged(self):
        old_key = self.key
        store = SQLiteEdgeStore(self.database, encryption_key=old_key)
        store.save_state(nodes=[{
            "node_id": self.node_id,
            "capabilities": ["telemetry"],
            "secret": self.secret,
            "max_parallel": 1,
            "last_seen": None,
        }], tasks=[])

        wrong_store = SQLiteEdgeStore(
            self.database, encryption_key=Fernet.generate_key()
        )
        with self.assertRaisesRegex(RuntimeError, "current key is incorrect"):
            wrong_store.rotate_encryption_key(Fernet.generate_key())

        restored = SQLiteEdgeStore(
            self.database, encryption_key=old_key
        ).load_state()
        self.assertEqual(restored["nodes"][0]["secret"], self.secret)

    def test_manager_reconciles_memory_after_persistence_failure(self):
        store = SQLiteEdgeStore(self.database, encryption_key=self.key)
        manager = EdgeManager(
            clock=self.clock,
            replay_guard=SQLiteReplayGuard(self.database),
            store=store,
        )

        def fail_save(**kwargs):
            raise OSError("simulated disk write failure")

        store.save_state = fail_save
        with self.assertRaisesRegex(OSError, "simulated disk write failure"):
            manager.register_node(self.node_id, ["telemetry"], self.secret)

        self.assertEqual(manager.snapshot()["nodes_total"], 0)
        self.assertEqual(store.load_state()["nodes"], [])

    def test_failed_snapshot_write_rolls_back_previous_state(self):
        store = SQLiteEdgeStore(self.database, encryption_key=self.key)
        original_node = {
            "node_id": self.node_id,
            "capabilities": ["telemetry"],
            "secret": self.secret,
            "max_parallel": 1,
            "last_seen": None,
        }
        store.save_state(nodes=[original_node], tasks=[])
        invalid_task = {
            "task_id": "task-invalid",
            "task_type": "math.verify",
            "payload": {"not_json": {1, 2, 3}},
            "required_capabilities": ["math.verify"],
            "created_at": self.clock(),
            "deadline": self.clock() + 30,
            "state": "QUEUED",
            "node_id": None,
            "lease_until": None,
            "result": None,
            "result_sha256": None,
            "error": None,
        }

        with self.assertRaises(TypeError):
            store.save_state(nodes=[], tasks=[invalid_task])

        restored = store.load_state()
        self.assertEqual(len(restored["nodes"]), 1)
        self.assertEqual(restored["nodes"][0]["node_id"], self.node_id)
        self.assertEqual(restored["nodes"][0]["secret"], self.secret)
        self.assertEqual(restored["tasks"], [])


if __name__ == "__main__":
    unittest.main()
