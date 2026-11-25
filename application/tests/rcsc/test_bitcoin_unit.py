import unittest

from nexus_rcsc.bitcoin import (
    decode_compact_target, parse_header, sha256d, subsidy_sats,
    verify_coinbase_reward,
)

GENESIS_HEADER = (
    "01000000"
    "0000000000000000000000000000000000000000000000000000000000000000"
    "3ba3edfd7a7b12b27ac72c3e67768f617fc81bc3888a51323a9fb8aa4b1e5e4a"
    "29ab5f49ffff001d1dac2b7c"
)
GENESIS_HASH = "000000000019d6689c085ae165831e934ff763ae46a2a6c172b3f1b60a8ce26f"


class BitcoinPrimitiveTests(unittest.TestCase):
    def test_genesis_header_hash_and_pow(self):
        parsed = parse_header(GENESIS_HEADER)
        self.assertEqual(parsed["block_hash"], GENESIS_HASH)
        self.assertTrue(parsed["pow_valid"])
        self.assertEqual(parsed["nonce"], 2083236893)
        self.assertEqual(parsed["height"] if "height" in parsed else 0, 0)

    def test_double_sha256_raw_digest(self):
        self.assertEqual(len(sha256d(bytes.fromhex(GENESIS_HEADER))), 32)

    def test_compact_target(self):
        self.assertGreater(decode_compact_target(0x1D00FFFF), 0)

    def test_subsidy_schedule(self):
        self.assertEqual(subsidy_sats(0), 5_000_000_000)
        self.assertEqual(subsidy_sats(210_000), 2_500_000_000)
        self.assertEqual(subsidy_sats(840_000), 312_500_000)

    def test_coinbase_split(self):
        result = verify_coinbase_reward(840_000, [{"value": 312_600_000}])
        self.assertEqual(result["scheduled_subsidy_sats"], 312_500_000)
        self.assertEqual(result["claimed_above_subsidy_sats"], 100_000)
        self.assertEqual(result["subsidy_underclaim_sats"], 0)


if __name__ == "__main__":
    unittest.main()
