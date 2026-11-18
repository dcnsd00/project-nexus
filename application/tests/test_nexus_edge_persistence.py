"""Additional EDGE durability invariants not covered by the store contract suite."""
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from cryptography.fernet import Fernet

from nexus_edge import (
    EdgeError,
    EdgeManager,
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
        restored = restarted.task_status(task["task_id"])
        self.assertEqual(restored["state"], "SUCCEEDED")
        self.assertEqual(restored["result"], result)
        self.assertEqual(restored["result_sha256"], completed["result_sha256"])

    def test_rotated_node_secret_and_sequence_survive_restart(self):
        first = self.manager()
        self.register_online_node(first)
        new_secret = b"nexus-edge-rotated-node-secret-32-bytes"
        first.rotate_node_secret(self.node_id, new_secret)
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
