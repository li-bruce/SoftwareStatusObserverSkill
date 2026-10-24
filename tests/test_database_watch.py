"""Real watcher refresh, HTTP graph replacement, and version-bound observations."""

from contextlib import closing
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
import sys
import threading
import time
import unittest
from unittest.mock import patch
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))
sys.path.insert(0, str(ROOT / "skills/vibelens/scripts"))

import test_database_sync as database_fixture
from bo_observer.data.sync import synchronize
from bo_observer.data.watcher import DataWatch
from bo_observer.data.projection import field_id
from bo_observer.service import GraphSession, make_server


class DatabaseWatchTests(unittest.TestCase):
    write_config = database_fixture.DatabaseSyncTests.write_config

    def setUp(self):
        database_fixture.DatabaseSyncTests.setUp(self)
        report = synchronize(self.root)
        self.assertTrue(report["valid"], report)
        self.session = GraphSession(self.root)
        self.server = make_server(self.session, 0, token="local-watcher-test")
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.watcher = DataWatch(self.server)
        self.base = f"http://127.0.0.1:{self.server.server_port}"
        self.addCleanup(self.close_server)

    def close_server(self):
        self.watcher.close()
        self.server.shutdown()
        self.thread.join(3)
        self.server.server_close()
        self.server.bo_session.close()

    def view(self):
        with self.open(self.base + "/api/view") as response:
            return json.load(response)

    def open(self, request):
        """Retry only Windows client-port allocation collisions, never server errors."""
        for attempt in range(5):
            try:
                return urlopen(request, timeout=5)
            except URLError as error:
                if getattr(error.reason, "winerror", None) != 10048 or attempt == 4:
                    raise
                time.sleep(0.05)

    def event(self, sequence=1):
        session = self.server.bo_session
        return {
            "protocol": "bo-event/v1",
            "schema_version": 3,
            "project_id": session.project["project_id"],
            "model_revision": session.model["revision"],
            "build_id": session.manifest["build_id"],
            "run_id": "watch-run",
            "producer_id": "application",
            "seq": sequence,
            "id": f"watch-run:application:{sequence}",
            "node": "db.query",
            "phase": "return",
            "entity": "images",
            "attempt": "load",
            "scope": "application",
            "basis": {},
            "call_id": f"query-{sequence}",
            "parent_call_id": None,
            "depends": [],
            "inputs": {"operation": "read", "statement": "SELECT id FROM images", "parameters": {}},
            "outputs": {
                "status": "returned",
                "rows": 1,
                "rows_known": True,
                "targets": ["table:images"],
            },
            "observed_at": datetime.now(timezone.utc).isoformat(),
        }

    def post_event(self, event):
        request = Request(
            self.base + "/api/bo/events",
            data=json.dumps(event).encode("utf-8"),
            headers={"Content-Type": "application/json", "X-BO-Token": "local-watcher-test"},
        )
        with self.open(request) as response:
            return json.load(response)

    def test_ddl_refresh_replaces_http_graph_and_excludes_old_recordings_events(self):
        before = self.view()
        preferences = self.session.preferences.read()
        preferences["entries"]["business-observer.layout.v2:fixture:custom"] = json.dumps(
            {
                "positions": {"advance": {"x": 120, "y": 80}},
                "expanded": ["advance"],
                "hiddenNodeIds": ["db.query"],
            }
        )
        saved = self.session.preferences.save(preferences)
        old_event = self.event()
        self.session.recordings.start("Before migration")
        self.assertTrue(self.post_event(old_event)["accepted"])
        recording = self.session.recordings.stop()
        self.assertTrue(self.session.recordings.list()["recordings"])
        self.assertEqual(len(self.view()["events"]), 1)
        with closing(sqlite3.connect(self.database)) as connection, connection:
            connection.execute("ALTER TABLE images ADD COLUMN reviewed BOOLEAN")
        self.assertTrue(self.watcher.tick()["valid"])
        after = self.view()
        self.assertNotEqual(before["manifest"]["build_id"], after["manifest"]["build_id"])
        self.assertIn(
            field_id("app", "table:images", "reviewed"),
            {node["id"] for node in after["model"]["nodes"]},
        )
        self.assertEqual(after["events"], [])
        self.assertEqual(self.server.bo_session.recordings.list()["recordings"], [])
        with self.assertRaises((ValueError, KeyError)):
            self.server.bo_session.recordings.get(recording["id"])
        self.assertEqual(self.server.bo_session.preferences.read(), saved)
        with self.assertRaises(HTTPError) as rejected:
            self.post_event(old_event)
        self.assertEqual(rejected.exception.code, 400)
        settings = json.loads(
            (self.root / ".stategraph/collector.json").read_text(encoding="utf-8")
        )
        self.assertEqual(settings["build_id"], after["manifest"]["build_id"])
        self.assertTrue(self.post_event(self.event())["accepted"])

    def test_source_update_refreshes_build_and_unchanged_tick_keeps_current_run(self):
        self.assertTrue(self.post_event(self.event())["accepted"])
        initial = self.server.bo_session
        self.assertTrue(self.watcher.tick()["valid"])
        self.assertIs(self.server.bo_session, initial)
        self.assertEqual(len(self.view()["events"]), 1)
        source = self.root / "worker.py"
        source.write_text(
            source.read_text(encoding="utf-8") + "\n# New application revision\n", encoding="utf-8"
        )
        self.assertTrue(self.watcher.tick()["valid"])
        self.assertIsNot(self.server.bo_session, initial)
        self.assertEqual(self.view()["events"], [])
        self.assertEqual(self.view()["binding_status"]["status"], "current")

    def test_failed_metadata_refresh_retains_session_and_recovers_after_connection_returns(self):
        before = self.view()
        old_session = self.server.bo_session
        with closing(sqlite3.connect(self.database)) as connection, connection:
            connection.execute("ALTER TABLE images ADD COLUMN reviewed BOOLEAN")
        with patch.dict("os.environ", {"BO_TEST_SYNC_URL": "sqlite:///missing.db"}):
            report = self.watcher.tick()
        self.assertFalse(report["valid"])
        self.assertIs(self.server.bo_session, old_session)
        failed = self.view()
        self.assertEqual(failed["manifest"]["build_id"], before["manifest"]["build_id"])
        self.assertEqual(failed["model"], before["model"])
        self.assertFalse(failed["database_status"]["valid"])
        self.assertTrue(self.watcher.tick()["valid"])
        recovered = self.view()
        self.assertNotEqual(recovered["manifest"]["build_id"], before["manifest"]["build_id"])
        self.assertTrue(recovered["database_status"]["valid"])


if __name__ == "__main__":
    unittest.main()
