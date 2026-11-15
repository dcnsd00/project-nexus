import unittest

from nexus_rcsc.statistics import ones_probability_upto, chi_square_upper_tail
from nexus_rcsc.associations import reward_conditioned_nonce_tests


class StatisticsTests(unittest.TestCase):
    def test_uniform_range_0_to_1_lsb(self):
        self.assertAlmostEqual(ones_probability_upto(1, 255), 0.5)

    def test_uniform_range_0_to_1_msb(self):
        self.assertAlmostEqual(ones_probability_upto(1, 0), 0.0)

    def test_all_ones_target(self):
        self.assertAlmostEqual(ones_probability_upto((1 << 256) - 1, 0), 0.5)
        self.assertAlmostEqual(ones_probability_upto((1 << 256) - 1, 255), 0.5)

    def test_chi_square_tail_reference_value(self):
        self.assertAlmostEqual(chi_square_upper_tail(5.991464547, 2), 0.05, places=8)

    def test_reward_nonce_screen_flags_insufficient_sample(self):
        result = reward_conditioned_nonce_tests([], permutations=9)
        self.assertEqual(result["status"], "insufficient_data")

    def test_reward_nonce_screen_runs_with_eligible_stratum(self):
        rows = []
        for i in range(90):
            rows.append({
                "reported_hash_matches_header": True,
                "reported_fields_match_header": True,
                "pow_valid": True,
                "in_best_chain": True,
                "height": 900_000,
                "bits": 0x17000000,
                "nonce": i * 1234567,
                "coinbase_total_sats": 312_500_000 + (i // 30) * 100_000,
            })
        result = reward_conditioned_nonce_tests(rows, permutations=19, min_stratum_size=60)
        self.assertEqual(result["status"], "exploratory_result")
        self.assertEqual(len(result["tests"]), 8)


if __name__ == "__main__":
    unittest.main()
