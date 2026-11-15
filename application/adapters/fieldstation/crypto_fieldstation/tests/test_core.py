import hashlib
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import app

class CoreTests(unittest.TestCase):
    def test_sha256_known_example(self):
        self.assertEqual(app.digest_bytes(b"abc", "sha256").hex(), "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad")

    def test_double_sha256_known_definition(self):
        expected = hashlib.sha256(hashlib.sha256(b"abc").digest()).hexdigest()
        self.assertEqual(app.digest_bytes(b"abc", "double_sha256").hex(), expected)

    def test_text_transforms(self):
        self.assertEqual(app.transform_candidate(" AbC ", "strip"), "AbC")
        self.assertEqual(app.transform_candidate("AbC", "lower"), "abc")
        self.assertEqual(app.transform_candidate("abc", "sha256_hex"), hashlib.sha256(b"abc").hexdigest())
        self.assertEqual(app.transform_candidate("abc", "newline_lf"), "abc\n")

    def test_hash_batch_exact_target(self):
        target = hashlib.sha256(b"exact candidate").hexdigest()
        out = app.hash_batch([("wrong", "exact"), ("exact candidate", "exact")], "sha256", target)
        self.assertEqual(out["tested"], 2)
        self.assertEqual(len(out["matches"]), 1)
        self.assertEqual(out["matches"][0]["candidate"], "exact candidate")

    def test_toy_pow_match_and_counter(self):
        out = app.pow_batch("test", 0, 200000, 8)
        self.assertGreater(out["tested"], 0)
        self.assertIsNotNone(out["found"])
        raw = bytes.fromhex(out["found"]["hash"])
        self.assertTrue(app.has_leading_zero_bits(raw, 8))

    def test_evp_output_size(self):
        keyiv = app.openssl_evp_bytes_to_key(b"pass", b"12345678", "md5", 48)
        self.assertEqual(len(keyiv), 48)
        self.assertNotEqual(keyiv[:32], keyiv[32:])

    def test_miner_battery_guard_allows_cool_unplugged_phone(self):
        battery = {"temperature": 28.0, "cpu_temperature": 42.0, "percentage": 75, "health": "GOOD", "plugged": "UNPLUGGED"}
        self.assertIsNone(app.battery_safety_reason(battery, starting=True))
        self.assertIsNone(app.battery_safety_reason(battery, starting=False))

    def test_miner_guard_blocks_hot_battery_and_charging(self):
        hot = {"temperature": 37.0, "cpu_temperature": 42.0, "percentage": 75, "health": "GOOD", "plugged": "UNPLUGGED"}
        self.assertIn("37.0°C", app.battery_safety_reason(hot, starting=True))
        charging = {"temperature": 28.0, "cpu_temperature": 42.0, "percentage": 75, "health": "GOOD", "plugged": "PLUGGED_AC"}
        self.assertIn("alimentare", app.battery_safety_reason(charging, starting=True))

    def test_miner_guard_stops_on_runtime_temperature_or_low_battery(self):
        hot = {"temperature": 39.0, "cpu_temperature": 42.0, "percentage": 50, "health": "GOOD", "plugged": "UNPLUGGED"}
        self.assertIn("Oprire termică", app.battery_safety_reason(hot, starting=False))
        low = {"temperature": 28.0, "cpu_temperature": 42.0, "percentage": 20, "health": "GOOD", "plugged": "UNPLUGGED"}
        self.assertIn("bateria", app.battery_safety_reason(low, starting=False))

    def test_miner_guard_stops_on_cpu_temperature_if_sensor_available(self):
        hot_cpu = {"temperature": 28.0, "cpu_temperature": 75.0, "percentage": 50, "health": "GOOD", "plugged": "UNPLUGGED"}
        self.assertIn("CPU/SoC", app.battery_safety_reason(hot_cpu, starting=False))

    def test_public_addresses_do_not_include_secrets(self):
        self.assertTrue(all("private_key" not in a and "seed" not in a for a in app.ADDRESSES))
        self.assertEqual({a["kind"] for a in app.ADDRESSES}, {"public_target"})

    def test_handoff_excludes_watch_only_addresses_and_balances(self):
        watch = {"id":"test-private-watch","label":"private watch test","chain":"ethereum","address":"0x" + "1"*40,"kind":"watch_only"}
        public = {"id":"test-public-target","label":"public puzzle target","chain":"bitcoin","address":"1BoatSLRHtKNngkdXEeobR76b53LETtpyT","kind":"public_target"}
        app.ADDRESSES.extend([watch, public])
        original_balances = dict(app.STATE.get("balances", {}))
        original_journal = app.JOURNALS.get("PUBLIC-ADDRESS-MONITOR")
        app.STATE["balances"][watch["id"]] = {"id":watch["id"],"address":watch["address"],"balance":10}
        app.STATE["balances"][public["id"]] = {"id":public["id"],"address":public["address"],"balance":1}
        app.JOURNALS["PUBLIC-ADDRESS-MONITOR"] = [{"timestamp":"test","results":[{"id":watch["id"],"address":watch["address"],"balance":10},{"id":public["id"],"address":public["address"],"balance":1}]}]
        try:
            bundle = app.build_handoff(False)
            self.assertNotIn(watch["address"], json_dumps(bundle))
            self.assertNotIn(watch["id"], bundle["public_target_balance_snapshots"])
            self.assertIn(public["id"], bundle["public_target_balance_snapshots"])
            monitor = bundle["journals"]["PUBLIC-ADDRESS-MONITOR"][0]
            self.assertEqual([r["id"] for r in monitor["results"]], [public["id"]])
        finally:
            app.ADDRESSES[:] = [a for a in app.ADDRESSES if a["id"] not in (watch["id"], public["id"])]
            app.STATE["balances"] = original_balances
            if original_journal is None: app.JOURNALS.pop("PUBLIC-ADDRESS-MONITOR",None)
            else: app.JOURNALS["PUBLIC-ADDRESS-MONITOR"] = original_journal


def json_dumps(obj):
    import json
    return json.dumps(obj, ensure_ascii=False)

if __name__ == "__main__":
    unittest.main()
