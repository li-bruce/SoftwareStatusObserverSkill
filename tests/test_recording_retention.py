"""Live history eviction must not invent gaps in a streamed recording."""

from pathlib import Path
from types import SimpleNamespace
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "skills/business-observer/scripts"), str(ROOT / "tools")]
from bo_observer.service import GraphSession
from bo_observer.observation import bo_retention
from test_multilanguage import project_fixture


class RecordingRetentionTests(unittest.TestCase):
    def setUp(self):
        (ROOT / ".validation").mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=ROOT / ".validation")
        self.root = Path(self.temp.name)
        self.project = project_fixture(self.root)
        self.clock = 100.0
        self.timer = patch.object(
            bo_retention, "time", SimpleNamespace(monotonic=lambda: self.clock)
        )
        self.timer.start()
        self.session = GraphSession(self.root)

    def tearDown(self):
        self.session.recordings.close()
        self.timer.stop()
        self.temp.cleanup()

    def event(self, sequence):
        identity = f"test:producer:{sequence}"
        self.session.event({
            "protocol": "bo-event/v1", "schema_version": 3,
            "project_id": self.project["project_id"],
            "model_revision": self.project["model"]["revision"],
            "build_id": self.session.manifest["build_id"],
            "run_id": "test", "producer_id": "producer", "seq": sequence,
            "id": identity, "node": "advance", "phase": "change",
            "entity": "job", "attempt": "one", "scope": "application",
            "call_id": identity, "parent_call_id": None, "basis": {},
            "inputs": {"state": "pending", "event": "start", "slots": 0},
            "outputs": {"state": "waiting"}, "depends": [],
            "observed_at": "2026-10-24T00:00:00+00:00",
        })

    def test_count_and_time_eviction_preserve_recorded_interval(self):
        self.session.history.limits.update(memory_events=2, memory_seconds=3)
        self.event(1)  # Outside the requested recording interval.
        self.session.recordings.start("Across live history eviction")
        for sequence in range(2, 6):
            self.event(sequence)
        self.assertEqual(len(self.session.view()["events"]), 2)
        self.clock += 4
        current = self.session.view()
        self.assertEqual(current["events"], [])
        self.assertEqual(current["health"]["evicted_events"], 5)
        self.assertEqual(current["health"]["dropped"], 0)
        stopped = self.session.recordings.stop()
        saved = self.session.recordings.get(stopped["id"])
        self.assertEqual([event["source_seq"] for event in saved["events"]], [2, 3, 4, 5])
        self.assertEqual(saved["gaps"], [])

    def test_actual_sequence_gap_stays_visible_after_history_expires(self):
        self.session.history.limits["memory_seconds"] = 3
        self.event(1)
        self.session.recordings.start("Missing producer event")
        self.event(3)  # Event 2 genuinely never reached the collector.
        self.clock += 4
        health = self.session.view()["health"]
        self.assertEqual(health["evicted_events"], 2)
        self.assertEqual(health["dropped"], 1)
        stopped = self.session.recordings.stop()
        saved = self.session.recordings.get(stopped["id"])
        self.assertEqual([event["source_seq"] for event in saved["events"]], [3])
        self.assertTrue(any("lost events" in gap for gap in saved["gaps"]))


if __name__ == "__main__":
    unittest.main()
