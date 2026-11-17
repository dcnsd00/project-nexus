import tempfile
import unittest
from pathlib import Path

from nexus_edge.replay_guard import (
    MemoryReplayGuard,
    ReplayError,
    SQLiteReplayGuard,
)


class ReplayGuardTests(unittest.TestCase):
    def test_memory_guard_accepts_increasing_sequence(self):
        guard = MemoryReplayGuard()
        guard.accept("edge-c5-001", 1)
        guard.accept("edge-c5-001", 2)
        with self.assertRaises(ReplayError):
            guard.accept("edge-c5-001", 2)

    def test_memory_guard_rejects_out_of_order_sequence(self):
        guard = MemoryReplayGuard()
        guard.accept("edge-c5-001", 9)
        with self.assertRaises(ReplayError):
            guard.accept("edge-c5-001", 8)

    def test_sqlite_guard_persists_sequence_across_instances(self):
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "edge-state.sqlite3"
            SQLiteReplayGuard(database).accept("edge-c5-001", 41)
            restarted = SQLiteReplayGuard(database)
            restarted.accept("edge-c5-001", 42)
            with self.assertRaises(ReplayError):
                SQLiteReplayGuard(database).accept("edge-c5-001", 41)

    def test_sequences_are_scoped_per_node(self):
        with tempfile.TemporaryDirectory() as directory:
            guard = SQLiteReplayGuard(Path(directory) / "edge.sqlite3")
            guard.accept("edge-c5-001", 10)
            guard.accept("edge-c5-002", 1)

    def test_rejects_invalid_sequences(self):
        guard = MemoryReplayGuard()
        for value in (0, -1, True, 1.5, "2"):
            with self.subTest(value=value):
                with self.assertRaises(ReplayError):
                    guard.accept("edge-c5-001", value)

    def test_rejects_empty_node_id(self):
        with self.assertRaises(ReplayError):
            MemoryReplayGuard().accept("", 1)


if __name__ == "__main__":
    unittest.main()
