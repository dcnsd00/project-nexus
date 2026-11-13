import unittest

from nexus_edge.service import EdgeService


class EdgeServiceTests(unittest.TestCase):
    def test_lifecycle_and_read_only_health(self):
        service = EdgeService()
        self.assertFalse(service.health_check()["ok"])
        service.initialize()
        service.start()
        status = service.health_check()
        self.assertTrue(status["ok"])
        self.assertEqual(status["module"], "nexus_edge")
        self.assertEqual(status["mode"], "local_control_plane_no_transport")
        self.assertFalse(status["details"]["network_io_enabled"])
        self.assertFalse(status["details"]["wallet_access_enabled"])
        self.assertFalse(status["details"]["miner_autostart_enabled"])
        service.stop()
        self.assertFalse(service.health_check()["ok"])
        service.shutdown()
        self.assertFalse(service.health_check()["ok"])

    def test_start_requires_initialize(self):
        service = EdgeService()
        with self.assertRaises(RuntimeError):
            service.start()


if __name__ == "__main__":
    unittest.main()
