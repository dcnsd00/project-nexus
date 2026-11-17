import tempfile
import unittest
from pathlib import Path

from cryptography.fernet import Fernet

from nexus_edge import SQLiteEdgeStore, SQLiteReplayGuard
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

    def test_service_wires_durable_store_into_manager(self):
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "edge.sqlite3"
            key = Fernet.generate_key()
            store = SQLiteEdgeStore(database, encryption_key=key)
            replay = SQLiteReplayGuard(database)
            service = EdgeService(replay_guard=replay, store=store)
            service.initialize()
            service.start()
            self.assertEqual(service.health_check()["details"]["mode"], "sqlite_persistent")

    def test_start_requires_initialize(self):
        service = EdgeService()
        with self.assertRaises(RuntimeError):
            service.start()


if __name__ == "__main__":
    unittest.main()
