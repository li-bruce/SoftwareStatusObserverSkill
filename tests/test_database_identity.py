"""Database identity changes invalidate evidence without persisting credentials."""

import os
from pathlib import Path
import shutil
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))
sys.path.insert(0, str(ROOT / "skills/vibelens/scripts"))

import test_database_sync as database_fixture
from bo_observer.data.contract import source_identity
from bo_observer.data.sync import synchronize


class DatabaseIdentityTests(unittest.TestCase):
    write_config = database_fixture.DatabaseSyncTests.write_config

    def setUp(self):
        database_fixture.DatabaseSyncTests.setUp(self)

    def identity(self, url):
        with patch.dict(os.environ, {"BO_TEST_SYNC_URL": url}):
            return source_identity(self.root, self.config)

    def test_password_rotation_keeps_identity_but_database_or_namespace_changes_it(self):
        first = self.identity("postgresql+pg8000://user:first-password@localhost:5432/application")
        changed_password = self.identity(
            "postgresql+pg8000://user:second-password@localhost:5432/application"
        )
        changed_database = self.identity(
            "postgresql+pg8000://user:second-password@localhost:5432/another"
        )
        self.assertEqual(first, changed_password)
        self.assertNotEqual(first, changed_database)
        self.assertNotIn("password", first)
        self.config["stores"][0]["namespace"] = "another_schema"
        self.assertNotEqual(
            first,
            self.identity("postgresql+pg8000://user:first-password@localhost:5432/application"),
        )

    def test_redis_query_database_selector_is_part_of_effective_identity(self):
        self.config["stores"][0]["engine"] = "redis"
        first = self.identity("redis://localhost:6379/?db=1")
        second = self.identity("redis://localhost:6379/?db=2")
        self.assertNotEqual(first, second)

    def test_different_sqlite_file_with_identical_schema_requires_new_projection(self):
        first = synchronize(self.root)
        self.assertTrue(first["valid"], first)
        shutil.copyfile(self.database, self.root / "another.db")
        with patch.dict(os.environ, {"BO_TEST_SYNC_URL": "sqlite:///another.db"}):
            stale = synchronize(self.root, update=False)
            self.assertFalse(stale["valid"])
            second = synchronize(self.root)
            self.assertTrue(second["valid"], second)
            self.assertNotEqual(first["source_id"], second["source_id"])
            self.assertEqual(first["catalog_id"], second["catalog_id"])

    def test_exporter_source_change_invalidates_export_even_outside_explicit_source_list(self):
        exporter = self.root / "export_model.py"
        exporter.write_text("print('{}')\n", encoding="utf-8")
        self.config["exporters"] = [
            {
                "store": "app",
                "command": ["{python}", "export_model.py"],
                "output": "bo_stategraph/declared.json",
            }
        ]
        before = source_identity(self.root, self.config)
        exporter.write_text("# Updated exporter\nprint('{}')\n", encoding="utf-8")
        self.assertNotEqual(before, source_identity(self.root, self.config))


if __name__ == "__main__":
    unittest.main()
