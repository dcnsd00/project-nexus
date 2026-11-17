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

    def heartbeat_message(self, timestamp, sequence, version=1):
        return {
            "protocol_version": version, "kind": "heartbeat",
            "node_id": "edge-c5-001", "timestamp": timestamp, "sequence": sequence,
        }

    def beat(self, sequence=1):
        timestamp = self.clock()
        message = self.heartbeat_message(timestamp, sequence)
        return self.manager.heartbeat(
            "edge-c5-001", timestamp, sequence, sign_message(self.secret, message)
        )

    def result_signature(self, task_id, result, sequence, nonce):
        message = {
            "protocol_version": 1, "kind": "task_result",
            "node_id": "edge-c5-001", "task_id": task_id,
            "assignment_nonce": nonce, "sequence": sequence, "result": result,
        }
        return sign_message(self.secret, message)

    def test_authenticated_node_registration_and_heartbeat(self):
        status = self.manager.node_status("edge-c5-001")
        self.assertTrue(status["online"])
        self.assertEqual(status["protocol_version"], 1)
        self.assertEqual(status["last_heartbeat_sequence"], 1)

    def test_rejects_weak_secret(self):
        with self.assertRaises(EdgeError):
            self.manager.register_node("edge-c5-002", ["telemetry"], b"short")

    def test_rejects_duplicate_node(self):
        with self.assertRaises(EdgeError):
            self.manager.register_node("edge-c5-001", ["telemetry"], self.secret)

    def test_rejects_invalid_heartbeat_signature(self):
        with self.assertRaises(EdgeError):
            self.manager.heartbeat("edge-c5-001", self.clock(), 2, "0" * 64)

    def test_rejects_stale_heartbeat(self):
        old = self.clock() - 60
        message = self.heartbeat_message(old, 2)
        with self.assertRaisesRegex(EdgeError, "clock-skew"):
            self.manager.heartbeat(
                "edge-c5-001", old, 2, sign_message(self.secret, message)
            )

    def test_rejects_replayed_heartbeat_sequence(self):
        self.beat(sequence=3)
        timestamp = self.clock()
        message = self.heartbeat_message(timestamp, 2)
        with self.assertRaisesRegex(EdgeError, "replayed"):
            self.manager.heartbeat(
                "edge-c5-001", timestamp, 2, sign_message(self.secret, message)
            )

    def test_rejects_wrong_protocol_version_signature(self):
        timestamp = self.clock()
        message = self.heartbeat_message(timestamp, 2, version=2)
        with self.assertRaises(EdgeError):
            self.manager.heartbeat(
                "edge-c5-001", timestamp, 2, sign_message(self.secret, message)
            )

    def test_capability_scheduling_and_signed_result(self):
        task = self.manager.submit_task("math.verify", {"input": "abc"}, ["math.verify"])
        claimed = self.manager.claim_task("edge-c5-001")
        self.assertEqual(claimed["task_id"], task["task_id"])
        self.assertTrue(claimed["assignment_nonce"])
        self.manager.start_task("edge-c5-001", task["task_id"])
        result = {"digest": "ba7816bf"}
        signature = self.result_signature(
            task["task_id"], result, 1, claimed["assignment_nonce"]
        )
        completed = self.manager.complete_task(
            "edge-c5-001", task["task_id"], result, 1,
            claimed["assignment_nonce"], signature,
        )
        self.assertEqual(completed["state"], "SUCCEEDED")
        self.assertEqual(len(completed["result_sha256"]), 64)
        self.assertIsNone(completed["assignment_nonce"])

    def test_rejects_forged_result(self):
        task = self.manager.submit_task("math.verify", {"input": "x"}, ["math.verify"])
        claimed = self.manager.claim_task("edge-c5-001")
        self.manager.start_task("edge-c5-001", task["task_id"])
        with self.assertRaises(EdgeError):
            self.manager.complete_task(
                "edge-c5-001", task["task_id"], {"ok": True}, 1,
                claimed["assignment_nonce"], "bad",
            )

    def test_rejects_replayed_result_sequence(self):
        first = self.manager.submit_task("math.verify", {"input": "one"}, ["math.verify"])
        first_claim = self.manager.claim_task("edge-c5-001")
        self.manager.start_task("edge-c5-001", first["task_id"])
        result = {"ok": True}
        self.manager.complete_task(
            "edge-c5-001", first["task_id"], result, 1,
            first_claim["assignment_nonce"],
            self.result_signature(first["task_id"], result, 1, first_claim["assignment_nonce"]),
        )
        second = self.manager.submit_task("math.verify", {"input": "two"}, ["math.verify"])
        second_claim = self.manager.claim_task("edge-c5-001")
        self.manager.start_task("edge-c5-001", second["task_id"])
        replay = self.result_signature(
            second["task_id"], result, 1, second_claim["assignment_nonce"]
        )
        with self.assertRaisesRegex(EdgeError, "replayed"):
            self.manager.complete_task(
                "edge-c5-001", second["task_id"], result, 1,
                second_claim["assignment_nonce"], replay,
            )

    def test_assignment_nonce_rejects_stale_worker_result_after_requeue(self):
        task = self.manager.submit_task(
            "telemetry.collect", {"sensor": "temp"}, ["telemetry"]
        )
        old_claim = self.manager.claim_task("edge-c5-001")
        self.manager.start_task("edge-c5-001", task["task_id"])
        self.clock.advance(11)
        self.assertEqual(self.manager.reap_expired(), {"expired": 0, "requeued": 1})
        new_claim = self.manager.claim_task("edge-c5-001")
        self.assertNotEqual(old_claim["assignment_nonce"], new_claim["assignment_nonce"])
        self.manager.start_task("edge-c5-001", task["task_id"])
        result = {"temperature": 22}
        old_signature = self.result_signature(
            task["task_id"], result, 2, old_claim["assignment_nonce"]
        )
        with self.assertRaisesRegex(EdgeError, "nonce mismatch"):
            self.manager.complete_task(
                "edge-c5-001", task["task_id"], result, 2,
                old_claim["assignment_nonce"], old_signature,
            )
        new_signature = self.result_signature(
            task["task_id"], result, 2, new_claim["assignment_nonce"]
        )
        completed = self.manager.complete_task(
            "edge-c5-001", task["task_id"], result, 2,
            new_claim["assignment_nonce"], new_signature,
        )
        self.assertEqual(completed["state"], "SUCCEEDED")

    def test_task_is_not_assigned_without_capability(self):
        secret = b"x" * 32
        self.manager.register_node("edge-data-002", ["telemetry"], secret)
        timestamp = self.clock()
        message = {
            "protocol_version": 1, "kind": "heartbeat",
            "node_id": "edge-data-002", "timestamp": timestamp, "sequence": 1,
        }
        self.manager.heartbeat(
            "edge-data-002", timestamp, 1, sign_message(secret, message)
        )
        self.manager.submit_task("math.verify", {"input": "x"}, ["math.verify"])
        self.assertIsNone(self.manager.claim_task("edge-data-002"))

    def test_expired_lease_requeues_task_and_rotates_nonce(self):
        task = self.manager.submit_task(
            "telemetry.collect", {"sensor": "temp"}, ["telemetry"]
        )
        first = self.manager.claim_task("edge-c5-001")
        self.manager.start_task("edge-c5-001", task["task_id"])
        self.clock.advance(11)
        self.assertEqual(self.manager.reap_expired(), {"expired": 0, "requeued": 1})
        self.assertEqual(self.manager.task_status(task["task_id"])["state"], "QUEUED")
        second = self.manager.claim_task("edge-c5-001")
        self.assertNotEqual(first["assignment_nonce"], second["assignment_nonce"])

    def test_deadline_expires_task(self):
        task = self.manager.submit_task(
            "telemetry.collect", {}, ["telemetry"], ttl_s=2
        )
        self.clock.advance(3)
        self.assertEqual(self.manager.reap_expired(), {"expired": 1, "requeued": 0})
        self.assertEqual(self.manager.task_status(task["task_id"])["state"], "EXPIRED")

    def test_claim_reaps_expired_lease_before_checking_node_capacity(self):
        manager = EdgeManager(clock=self.clock, heartbeat_ttl_s=30, lease_s=10)
        manager.register_node("edge-cap-001", ["telemetry"], self.secret, max_parallel=1)
        timestamp = self.clock()
        beat = {
            "protocol_version": 1, "kind": "heartbeat", "node_id": "edge-cap-001",
            "timestamp": timestamp, "sequence": 1,
        }
        manager.heartbeat("edge-cap-001", timestamp, 1, sign_message(self.secret, beat))
        first = manager.submit_task("telemetry.collect", {"n": 1}, ["telemetry"])
        manager.claim_task("edge-cap-001")
        manager.start_task("edge-cap-001", first["task_id"])
        self.clock.advance(11)
        second = manager.submit_task("telemetry.collect", {"n": 2}, ["telemetry"])
        claimed = manager.claim_task("edge-cap-001")
        self.assertEqual(claimed["task_id"], first["task_id"])
        self.assertEqual(manager.task_status(second["task_id"])["state"], "QUEUED")

    def test_payload_size_limit(self):
        tiny = EdgeManager(max_payload_bytes=128, clock=self.clock)
        with self.assertRaises(EdgeError):
            tiny.submit_task("math.verify", {"data": "x" * 256}, ["math.verify"])

    def test_snapshot_discloses_pilot_limits(self):
        snapshot = self.manager.snapshot()
        self.assertEqual(snapshot["mode"], "in_memory_pilot")
        self.assertEqual(snapshot["protocol_version"], 1)
        self.assertFalse(snapshot["persistence_enabled"])
        self.assertFalse(snapshot["network_io_enabled"])
        self.assertFalse(snapshot["wallet_access_enabled"])
        self.assertFalse(snapshot["miner_autostart_enabled"])


if __name__ == "__main__":
    unittest.main()
