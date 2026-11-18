"""Durability, replay recovery and SQLite transaction tests for NEXUS EDGE."""
import sqlite3
import tempfile
import unittest
from pathlib import Path

from cryptography.fernet import Fernet

from nexus_edge import EdgeError, EdgeManager, SQLiteEdgeStore, SQLiteReplayGuard, sign_message


class Clock:
    def __init__(self, value=1_800_000_000.0):
        self.value = value

    def __call__(self):
        return self.value

    def advance(self, seconds):
        self.value += seconds


class EdgePersistenceTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.database = Path(self.temp_dir.name) / "edge.sqlite3"
        self.key = Fernet.generate_key()
        self.clock = Clock()
        self.secret = b"nexus-edge-persistence-test-secret"
        self.node_id = "edge-c5-persist-01"

    def manager(self):
        store = SQLiteEdgeStore(self.database, encryption_key=self.key)
        replay = SQLiteReplayGuard(self.database)
        return EdgeManager(
            clock=self.clock,
            heartbeat_ttl_s=30,
            lease_s=10,
            replay_guard=replay,
            store=store,
        )

    def heartbeat(self, manager, sequence=1):
        timestamp = self.clock()
        message = {
            "kind": "heartbeat",
            "node_id": self.node_id,
            "timestamp": timestamp,
            "sequence": sequence,
        }
        return manager.heartbeat(
            self.node_id, timestamp, sequence,
            sign_message(self.secret, message),
        )

    def register_online_node(self, manager):
        manager.register_node(
            self.node_id, ["telemetry", "math.verify"], self.secret
        )
        self.heartbeat(manager)

    def test_node_and_completed_task_survive_manager_restart(self):
        first = self.manager()
        self.register_online_node(first)
        task = first.submit_task(
            "math.verify", {"input": "NEXUS"}, ["math.verify"]
        )
        first.claim_task(self.node_id)
        first.start_task(self.node_id, task["task_id"])
        result = {"verified": True, "digest": "abc123"}
        signed_result = {
            "kind": "task_result",
            "node_id": self.node_id,
            "task_id": task["task_id"],
            "result": result,
        }
        completed = first.complete_task(
            self.node_id,
            task["task_id"],
            result,
            sign_message(self.secret, signed_result),
        )

        restarted = self.manager()
        self.assertEqual(restarted.snapshot()["mode"], "sqlite_persistent")
        self.assertTrue(restarted.node_status(self.node_id)["online"])
        restored = restarted.task_status(task["task_id"])
        self.assertEqual(restored["state"], "SUCCEEDED")
        self.assertEqual(restored["result"], result)
        self.assertEqual(restored["result_sha256"], completed["result_sha256"])

    def test_replay_sequence_is_rejected_after_manager_restart(self):
        first = self.manager()
        self.register_online_node(first)

        restarted = self.manager()
        timestamp = self.clock()
        replayed_message = {
            "kind": "heartbeat",
            "node_id": self.node_id,
            "timestamp": timestamp,
            "sequence": 1,
        }
        with self.assertRaisesRegex(EdgeError, "replayed or out-of-order"):
            restarted.heartbeat(
                self.node_id,
                timestamp,
                1,
                sign_message(self.secret, replayed_message),
            )

    def test_expired_worker_lease_is_requeued_during_restart(self):
        first = self.manager()
        self.register_online_node(first)
        task = first.submit_task(
            "telemetry.collect", {"sensor": "temperature"},
            ["telemetry"], ttl_s=120,
        )
        first.claim_task(self.node_id)
        first.start_task(self.node_id, task["task_id"])
        self.clock.advance(11)

        restarted = self.manager()
        self.assertEqual(
            restarted.task_status(task["task_id"])["state"], "QUEUED"
        )
        self.assertEqual(
            restarted.node_status(self.node_id)["active_tasks"], []
        )

    def test_node_secret_is_encrypted_at_rest(self):
        manager = self.manager()
        manager.register_node(self.node_id, ["telemetry"], self.secret)

        with sqlite3.connect(self.database) as connection:
            ciphertext = connection.execute(
                "SELECT secret_ciphertext FROM edge_nodes WHERE node_id = ?",
                (self.node_id,),
            ).fetchone()[0]

        self.assertIsInstance(ciphertext, bytes)
        self.assertNotIn(self.secret, ciphertext)

    def test_wrong_encryption_key_fails_closed_on_state_restore(self):
        first = self.manager()
        first.register_node(self.node_id, ["telemetry"], self.secret)

        wrong_store = SQLiteEdgeStore(
            self.database, encryption_key=Fernet.generate_key()
        )
        with self.assertRaisesRegex(RuntimeError, "cannot decrypt EDGE credential"):
            EdgeManager(
                clock=self.clock,
                replay_guard=SQLiteReplayGuard(self.database),
                store=wrong_store,
            )

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
            manager.register_node(
                self.node_id, ["telemetry"], self.secret
            )

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
