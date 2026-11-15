import math
import unittest
from core.mining_math import (expected_blocks, probability_at_least_one_block,
    expected_wait_seconds, monte_carlo_block_probability, energy_kwh,
    electricity_cost, amdahl_speedup, split_cpu_threads)
from core.physics_engine import joules_per_hash, thermal_rc_temperature, monte_carlo_thermal_risk
from core.optimizer import cpu_thread_plan

class MiningMathTests(unittest.TestCase):
    def test_poisson_expected_blocks(self):
        self.assertAlmostEqual(expected_blocks(1, 100, 10, 100), 0.1)
    def test_poisson_probability(self):
        self.assertAlmostEqual(probability_at_least_one_block(1, 100, 10, 100), 1-math.exp(-0.1))
    def test_wait(self):
        self.assertEqual(expected_wait_seconds(1, 100, 10), 1000)
    def test_mc_reproducible_and_near_analytic(self):
        a = monte_carlo_block_probability(1, 100, 10, 100, trials=100_000, seed=5)
        b = monte_carlo_block_probability(1, 100, 10, 100, trials=100_000, seed=5)
        self.assertEqual(a, b)
        self.assertLess(abs(a['estimate'] - a['analytic_probability']), .01)
    def test_energy(self):
        self.assertAlmostEqual(energy_kwh(100, 10), 1)
        self.assertAlmostEqual(electricity_cost(100, 10, 2), 2)
    def test_amdahl_and_threads(self):
        self.assertEqual(split_cpu_threads(8, 50), 4)
        self.assertEqual(amdahl_speedup(1, 4), 4)
        self.assertEqual(cpu_thread_plan(8)['worker_threads'], 4)
    def test_physics(self):
        self.assertAlmostEqual(joules_per_hash(10, 5), 2)
        self.assertGreater(thermal_rc_temperature(22, 40, .5, 100, 100), 22)
        risk = monte_carlo_thermal_risk(22, (30, 40), (.2, .3), (100, 200), 100, 80, 1000, 1)
        self.assertIn('probability_at_or_above_limit', risk)

if __name__ == '__main__':
    unittest.main()
