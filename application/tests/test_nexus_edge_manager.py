import unittest

from nexus_edge import EdgeError, EdgeManager, sign_message


class Clock:
    def __init__(self, value=1_800_000_000.0):
        self.value = value

    def __call__(self):
        return self.value

    def advance(self, seconds):
        self.value += seconds


class EdgeManagerTests(unittest.TestCase):
    def setUp(self):
        self.clock = Clock()
        self.manager = EdgeManager(clock=self.clock, heartbeat_ttl_s=30, lease_s=10)
        self.secret = b"nexus-edge-test-secret-32-bytes!!"
        self.manager.register_node("edge-c5-001", ["telemetry", "math.verify"], self.secret)
        self.beat()

    def beat(self):
        ts = self.clock()
        msg = {"kind": "heartbeat", "node_id": "edge-c5-001", "timestamp": ts}
        return self.manager.heartbeat("edge-c5-001", ts, sign_message(self.secret, msg))

    def test_authenticated_node_registration_and_heartbeat(self):
        self.assertTrue(self.manager.node_status("edge-c5-001")["online"])

    def test_rejects_weak_secret(self):
        with self.assertRaises(EdgeError):
            self.manager.register_node("edge-c5-002", ["telemetry"], b"short")

    def test_rejects_duplicate_node(self):
        with self.assertRaises(EdgeError):
            self.manager.register_node("edge-c5-001", ["telemetry"], self.secret)

    def test_rejects_invalid_heartbeat_signature(self):
        with self.assertRaises(EdgeError):
            self.manager.heartbeat("edge-c5-001", self.clock(), "0" * 64)

    def test_rejects_stale_heartbeat(self):
        old = self.clock() - 60
        msg = {"kind": "heartbeat", "node_id": "edge-c5-001", "timestamp": old}
        with self.assertRaises(EdgeError):
            self.manager.heartbeat("edge-c5-001", old, sign_message(self.secret, msg))

    def test_capability_scheduling_and_signed_result(self):
        task = self.manager.submit_task("math.verify", {"input": "abc"}, ["math.verify"])
        claimed = self.manager.claim_task("edge-c5-001")
        self.assertEqual(claimed["task_id"], task["task_id"])
        self.manager.start_task("edge-c5-001", task["task_id"])
        result = {"digest": "ba7816bf"}
        msg = {"kind": "task_result", "node_id": "edge-c5-001",
               "task_id": task["task_id"], "result": result}
        completed = self.manager.complete_task(
            "edge-c5-001", task["task_id"], result, sign_message(self.secret, msg)
        )
        self.assertEqual(completed["state"], "SUCCEEDED")
        self.assertEqual(len(completed["result_sha256"]), 64)

    def test_rejects_forged_result(self):
        task = self.manager.submit_task("math.verify", {"input": "x"}, ["math.verify"])
        self.manager.claim_task("edge-c5-001")
        self.manager.start_task("edge-c5-001", task["task_id"])
        with self.assertRaises(EdgeError):
            self.manager.complete_task("edge-c5-001", task["task_id"], {"ok": True}, "bad")

    def test_task_is_not_assigned_without_capability(self):
        self.manager.register_node("edge-data-002", ["telemetry"], b"x" * 32)
        ts = self.clock()
        msg = {"kind": "heartbeat", "node_id": "edge-data-002", "timestamp": ts}
        self.manager.heartbeat("edge-data-002", ts, sign_message(b"x" * 32, msg))
        self.manager.submit_task("math.verify", {"input": "x"}, ["math.verify"])
        self.assertIsNone(self.manager.claim_task("edge-data-002"))

    def test_expired_lease_requeues_task(self):
        task = self.manager.submit_task("telemetry.collect", {"sensor": "temp"}, ["telemetry"])
        self.manager.claim_task("edge-c5-001")
        self.manager.start_task("edge-c5-001", task["task_id"])
        self.clock.advance(11)
        self.assertEqual(self.manager.reap_expired(), {"expired": 0, "requeued": 1})
        self.assertEqual(self.manager.task_status(task["task_id"])["state"], "QUEUED")

    def test_deadline_expires_task(self):
        task = self.manager.submit_task("telemetry.collect", {}, ["telemetry"], ttl_s=2)
        self.clock.advance(3)
        self.assertEqual(self.manager.reap_expired(), {"expired": 1, "requeued": 0})
        self.assertEqual(self.manager.task_status(task["task_id"])["state"], "EXPIRED")

    def test_payload_size_limit(self):
        tiny = EdgeManager(max_payload_bytes=128, clock=self.clock)
        with self.assertRaises(EdgeError):
            tiny.submit_task("math.verify", {"data": "x" * 256}, ["math.verify"])

    def test_snapshot_discloses_pilot_limits(self):
        snap = self.manager.snapshot()
        self.assertEqual(snap["mode"], "in_memory_pilot")
        self.assertFalse(snap["network_io_enabled"])
        self.assertFalse(snap["wallet_access_enabled"])
        self.assertFalse(snap["miner_autostart_enabled"])


if __name__ == "__main__":
    unittest.main()
