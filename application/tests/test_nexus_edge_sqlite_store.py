import sqlite3
import tempfile
import threading
import unittest
from contextlib import closing
from pathlib import Path

from cryptography.fernet import Fernet

from nexus_edge import EdgeManager, SQLiteEdgeStore, SQLiteReplayGuard, sign_message


class Clock:
    def __init__(self):
        self.value = 1_800_000_000.0

    def __call__(self):
        return self.value

    def advance(self, seconds):
        self.value += seconds


class SQLiteEdgeStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.database = Path(self.temp.name) / "edge.sqlite3"
        self.key = Fernet.generate_key()
        self.secret = b"nexus-edge-persistent-test-secret!!"
        self.clock = Clock()

    def manager(self):
        store = SQLiteEdgeStore(self.database, encryption_key=self.key)
        replay = SQLiteReplayGuard(self.database)
        return EdgeManager(clock=self.clock, heartbeat_ttl_s=30, lease_s=10,
                           replay_guard=replay, store=store)

    def heartbeat(self, manager, sequence):
        timestamp = self.clock()
        message = {"kind": "heartbeat", "protocol_version": 1, "node_id": "edge-c5-009",
                   "timestamp": timestamp, "sequence": sequence}
        return manager.heartbeat("edge-c5-009", timestamp, sequence,
                                 sign_message(self.secret, message))

    def test_nodes_tasks_and_active_lease_survive_restart(self):
        first = self.manager()
        first.register_node("edge-c5-009", ["math.verify"], self.secret)
        self.heartbeat(first, 1)
        task = first.submit_task("math.verify", {"input": "abc"}, ["math.verify"])
        claim = first.claim_task("edge-c5-009")
        assignment_nonce = claim["assignment_nonce"]
        first.start_task("edge-c5-009", task["task_id"])

        restarted = self.manager()
        self.assertEqual(restarted.node_status("edge-c5-009")["active_tasks"],
                         [task["task_id"]])
        self.assertEqual(restarted.task_status(task["task_id"])["state"], "RUNNING")
        self.heartbeat(restarted, 2)
        result = {"verified": True}
        message = {"kind": "task_result", "protocol_version": 1, "node_id": "edge-c5-009",
                   "task_id": task["task_id"],
                   "assignment_nonce": assignment_nonce, "result": result}
        completed = restarted.complete_task(
            "edge-c5-009", task["task_id"], result, assignment_nonce,
            sign_message(self.secret, message),
        )
        self.assertEqual(completed["state"], "SUCCEEDED")

    def test_concurrent_claims_are_serialized_within_manager_process(self):
        manager = self.manager()
        manager.register_node("edge-c5-009", ["math.verify"], self.secret)
        self.heartbeat(manager, 1)
        task = manager.submit_task(
            "math.verify", {"input": "single-claim"}, ["math.verify"]
        )
        barrier = threading.Barrier(3)
        results = []
        errors = []

        def claim():
            try:
                barrier.wait()
                results.append(manager.claim_task("edge-c5-009"))
            except Exception as exc:
                errors.append(exc)

        workers = [threading.Thread(target=claim) for _ in range(2)]
        for worker in workers:
            worker.start()
        barrier.wait()
        for worker in workers:
            worker.join(timeout=5)

        self.assertFalse(any(worker.is_alive() for worker in workers))
        self.assertEqual(errors, [])
        claimed = [item for item in results if item is not None]
        self.assertEqual(len(claimed), 1)
        self.assertEqual(claimed[0]["task_id"], task["task_id"])
        self.assertEqual(manager.node_status("edge-c5-009")["active_tasks"],
                         [task["task_id"]])

    def test_expired_lease_is_requeued_during_restart_recovery(self):
        first = self.manager()
        first.register_node("edge-c5-009", ["math.verify"], self.secret)
        self.heartbeat(first, 1)
        task = first.submit_task("math.verify", {"input": "abc"}, ["math.verify"])
        first.claim_task("edge-c5-009")
        first.start_task("edge-c5-009", task["task_id"])
        self.clock.advance(11)

        restarted = self.manager()
        recovered = restarted.task_status(task["task_id"])
        self.assertEqual(recovered["state"], "QUEUED")
        self.assertIsNone(recovered["node_id"])
        self.assertIsNone(recovered["lease_until"])
        self.assertEqual(restarted.node_status("edge-c5-009")["active_tasks"], [])

    def test_task_deadline_expires_before_lease_end_during_restart(self):
        first = self.manager()
        first.register_node("edge-c5-009", ["math.verify"], self.secret)
        self.heartbeat(first, 1)
        task = first.submit_task(
            "math.verify", {"input": "deadline"}, ["math.verify"], ttl_s=5
        )
        first.claim_task("edge-c5-009")
        first.start_task("edge-c5-009", task["task_id"])
        self.clock.advance(6)

        restarted = self.manager()
        recovered = restarted.task_status(task["task_id"])
        self.assertEqual(recovered["state"], "EXPIRED")
        self.assertIsNone(recovered["node_id"])
        self.assertIsNone(recovered["lease_until"])
        self.assertEqual(restarted.node_status("edge-c5-009")["active_tasks"], [])

    def test_heartbeat_sequence_cannot_be_replayed_after_manager_restart(self):
        first = self.manager()
        first.register_node("edge-c5-009", ["math.verify"], self.secret)
        self.heartbeat(first, 7)

        restarted = self.manager()
        timestamp = self.clock()
        message = {"kind": "heartbeat", "protocol_version": 1, "node_id": "edge-c5-009",
                   "timestamp": timestamp, "sequence": 7}
        with self.assertRaisesRegex(Exception, "replayed|out-of-order"):
            restarted.heartbeat(
                "edge-c5-009", timestamp, 7, sign_message(self.secret, message)
            )
        self.heartbeat(restarted, 8)

    def test_expired_queued_task_is_persisted_when_claim_finds_no_work(self):
        manager = self.manager()
        manager.register_node("edge-c5-009", ["math.verify"], self.secret)
        self.heartbeat(manager, 1)
        task = manager.submit_task(
            "math.verify", {"input": "expired"}, ["math.verify"], ttl_s=1
        )
        self.clock.advance(2)

        self.assertIsNone(manager.claim_task("edge-c5-009"))
        self.assertEqual(manager.task_status(task["task_id"])["state"], "EXPIRED")
        with closing(sqlite3.connect(self.database)) as connection:
            row = connection.execute(
                "SELECT state FROM edge_tasks WHERE task_id = ?",
                (task["task_id"],),
            ).fetchone()
        self.assertEqual(row[0], "EXPIRED")

    def test_node_secret_is_encrypted_at_rest(self):
        manager = self.manager()
        manager.register_node("edge-c5-009", ["math.verify"], self.secret)
        raw = self.database.read_bytes()
        self.assertNotIn(self.secret, raw)

    def test_wrong_encryption_key_fails_closed(self):
        manager = self.manager()
        manager.register_node("edge-c5-009", ["math.verify"], self.secret)
        wrong = SQLiteEdgeStore(self.database, encryption_key=Fernet.generate_key())
        with self.assertRaises(RuntimeError):
            EdgeManager(store=wrong)

    def test_snapshot_reports_persistent_mode(self):
        manager = self.manager()
        self.assertEqual(manager.snapshot()["mode"], "sqlite_persistent")


if __name__ == "__main__":
    unittest.main()
