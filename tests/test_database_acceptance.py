"""A data graph must retain precise relations and require actual operation evidence."""

from copy import deepcopy
import json
import unittest
import sys
import tempfile
from pathlib import Path
from test_database_sync import DatabaseSyncTests
from bo_observer.data.projection import project_model
from bo_observer.data.sync import runtime_errors, synchronize
from bo_observer.data.contract import CATALOG_PATH


class AcceptanceTests(unittest.TestCase):
    setUp = DatabaseSyncTests.setUp
    write_config = DatabaseSyncTests.write_config
    model = DatabaseSyncTests.model

    def test_browser_demo_satisfies_its_actual_capture_contract(self):
        root = Path(__file__).resolve().parents[1]
        sys.path.insert(0, str(root / "tools"))
        from database_demo import Demo

        with tempfile.TemporaryDirectory(dir=root / ".validation") as directory:
            demo = Demo(Path(directory).resolve())
            try:
                committed = demo.run(False)
                rejected = demo.run(True)
                self.assertEqual(committed["mapping_status"], "pending")
                self.assertEqual(rejected["mapping_status"], "passed")
                self.assertEqual(committed["stored"], 7)
                self.assertEqual(rejected["stored"], 7)
                self.assertEqual(committed["observer_events"], 0)
                self.assertEqual(rejected["observer_events"], 0)
            finally:
                demo.close()

    def test_capture_expectations_cannot_be_silently_weakened(self):
        from bo_observer.data.acceptance import protected_errors

        previous = deepcopy(self.config)
        old = previous["operations"][0]
        old.update(requirements=["R1"], after={"count": "number"})
        mutations = [
            lambda current: current["operations"].clear(),
            lambda current: current["operations"][0].update(after={}),
            lambda current: current["operations"][0].update(failure_cases=["query-success"]),
            lambda current: current["operations"][0].update(required_cases=["another-case"]),
        ]
        for mutate in mutations:
            current = deepcopy(previous)
            mutate(current)
            self.assertTrue(protected_errors(previous, current))
            self.assertEqual(
                protected_errors(
                    previous,
                    current,
                    ["R1"],
                    {"R1": "The user changed this confirmed requirement."},
                ),
                [],
            )
        expanded = deepcopy(previous)
        expanded["operations"][0]["required_cases"].append("another-case")
        self.assertEqual(protected_errors(previous, expanded), [])

    def payload(self):
        return {
            "runs": [
                {
                    "case": "query-success",
                    "mode": "on",
                    "events": [
                        {
                            "node": "db.query",
                            "phase": "return",
                            "inputs": {"operation": "read", "statement": "SELECT * FROM images", "parameters": {}},
                            "outputs": {"status": "returned", "targets": ["table:images"],
                                        "duration_ms": 1, "unknown_targets": [], "rows_known": False,
                                        "target_source": "parsed_sql", "target_access": [{"target": "table:images", "action": "read"}]},
                        }
                    ],
                }
            ]
        }

    def test_failure_cannot_substitute_for_success(self):
        self.assertTrue(synchronize(self.root)["valid"])
        payload = self.payload()
        event = payload["runs"][0]["events"][0]
        event.update(phase="error")
        event["outputs"].update(status="failed", error_type="DatabaseError")
        self.assertTrue(runtime_errors(self.root, payload, self.model()))
        self.config["operations"][0]["failure_cases"] = ["query-success"]
        self.write_config()
        self.assertEqual(runtime_errors(self.root, payload, self.model()), [])

    def test_selected_values_are_required_beyond_an_event_name(self):
        operation = self.config["operations"][0]
        operation["parameters"] = {"limit": "number"}
        operation["after"] = {"count": "number"}
        self.write_config()
        self.assertTrue(synchronize(self.root)["valid"])
        payload = self.payload()
        self.assertTrue(runtime_errors(self.root, payload, self.model()))
        event = payload["runs"][0]["events"][0]
        event["inputs"]["parameters"] = {"limit": 5}
        event["outputs"]["result"] = {"count": 3}
        self.assertEqual(runtime_errors(self.root, payload, self.model()), [])

    def test_insert_select_records_read_source_and_write_destination(self):
        from sqlalchemy import create_engine
        from bo_observer.adapters.python.bo_probe import BOProbe
        from bo_observer.data.runtime import BODataRuntime
        from bo_observer.data.projection import resource_id

        engine = create_engine("sqlite:///" + str(self.database))
        self.addCleanup(engine.dispose)
        with engine.begin() as connection:
            connection.exec_driver_sql("CREATE TABLE archive (id INTEGER PRIMARY KEY, title TEXT)")
            connection.exec_driver_sql("INSERT INTO images VALUES (1, 'picture'), (2, 'sketch')")
        operation = self.config["operations"][0]
        operation.update(
            action="write",
            targets=["table:images", "table:archive"],
            target_actions={"table:images": "read", "table:archive": "write"},
        )
        self.write_config()
        self.assertTrue(synchronize(self.root)["valid"])
        model = self.model()
        edges = {(e["from"], e["to"], e.get("data_relation")) for e in model["edges"]}
        self.assertIn((resource_id("app", "table:images"), "db.query", "reads"), edges)
        self.assertIn(("db.query", resource_id("app", "table:archive"), "writes"), edges)
        self.assertNotIn(("db.query", resource_id("app", "table:images"), "writes"), edges)
        project = json.loads((self.root / "bo_stategraph/project.json").read_text(encoding="utf-8"))
        events = []
        probe = BOProbe(project, "mixed-query-test", sink=lambda event, kind: events.append(event))
        self.addCleanup(probe.close)
        runtime = BODataRuntime(probe, self.config)
        self.addCleanup(runtime.close)
        runtime.attach_sqlalchemy(engine)
        with runtime.operation("db.query"), engine.begin() as connection:
            connection.exec_driver_sql("INSERT INTO archive SELECT * FROM images")
        self.assertTrue(probe.flush())
        with engine.connect() as connection:
            self.assertEqual(connection.exec_driver_sql("SELECT COUNT(*) FROM archive").scalar(), 2)
        self.assertEqual(
            events[-1]["outputs"]["target_access"],
            [
                {"target": "table:archive", "action": "write"},
                {"target": "table:images", "action": "read"},
            ],
        )
        payload = {"runs": [{"case": "query-success", "mode": "on", "events": events}]}
        self.assertEqual(runtime_errors(self.root, payload, model), [])
        operation["target_actions"] = {"table:images": "write", "table:archive": "read"}
        self.write_config()
        self.assertTrue(
            any(
                "unexpected_database_target_access" in error
                for error in runtime_errors(self.root, payload, model)
            )
        )

    def test_same_table_read_write_has_both_relations(self):
        from bo_observer.data.projection import resource_id

        operation = self.config["operations"][0]
        operation.update(action="write", target_actions={"table:images": "read_write"})
        self.write_config()
        self.assertTrue(synchronize(self.root)["valid"])
        edges = {(e["from"], e["to"], e.get("data_relation")) for e in self.model()["edges"]}
        self.assertIn((resource_id("app", "table:images"), "db.query", "reads"), edges)
        self.assertIn(("db.query", resource_id("app", "table:images"), "writes"), edges)

    def test_multi_target_write_requires_complete_explicit_roles(self):
        operation = self.config["operations"][0]
        operation.update(action="write", targets=["table:images", "table:archive"])
        for mapping in (
            None,
            {"table:images": "write"},
            {"table:images": "read", "table:archive": "read"},
            {"table:images": "write", "table:archive": "guessed"},
        ):
            operation.pop("target_actions", None)
            if mapping is not None:
                operation["target_actions"] = mapping
            self.write_config()
            with self.subTest(mapping=mapping):
                self.assertFalse(synchronize(self.root)["valid"])

    def test_postgres_suffix_must_be_unambiguous(self):
        synchronize(self.root)
        model = self.model()
        operation = self.config["operations"][0]
        operation["targets"] = ["table:public.images"]
        self.write_config()
        dataset = next(n for n in model["nodes"] if n.get("data_key") == "table:images")
        dataset["data_key"] = "table:public.images"
        self.assertEqual(runtime_errors(self.root, self.payload(), model), [])
        model["nodes"].append({**dataset, "id": "another", "data_key": "table:other.images"})
        self.assertTrue(runtime_errors(self.root, self.payload(), model))

    def test_removed_managed_model_file_is_not_retained_forever(self):
        synchronize(self.root)
        model = self.model()
        self.assertIn("models.py", model["database"]["managed_source_files"])
        config = deepcopy(self.config)
        config["stores"][0]["source_files"] = ["new_models.py"]
        bundle = json.loads((self.root / CATALOG_PATH).read_text(encoding="utf-8"))
        updated = project_model(model, config, bundle)
        self.assertNotIn("models.py", updated["source_files"])
        self.assertIn("worker.py", updated["source_files"])

    def test_application_relationships_keep_origin_and_each_field_pair(self):
        synchronize(self.root)
        bundle = json.loads((self.root / CATALOG_PATH).read_text(encoding="utf-8"))
        declaration = deepcopy(bundle["catalogs"][0])
        declaration.update(origin="declaration", validation_scope="application")
        resource = declaration["resources"][0]
        resource["fields"] += [
            {"name": "created_by", "native_type": "INTEGER", "nullable": True},
            {"name": "reviewed_by", "native_type": "INTEGER", "nullable": True},
        ]
        resource["constraints"] += [
            {
                "kind": "foreign_key",
                "name": name,
                "fields": [name],
                "target": resource["key"],
                "target_fields": ["id"],
            }
            for name in ("created_by", "reviewed_by")
        ]
        bundle["declarations"] = [declaration]
        model = project_model(self.model(), self.config, bundle)
        refs = [e for e in model["edges"] if e.get("data_relation") == "references"]
        self.assertEqual(len(refs), 1)
        self.assertEqual(len(refs[0]["data_constraints"]), 2)
        self.assertEqual(refs[0]["data_origin"], "declaration")
        self.assertEqual(len([e for e in model["edges"] if e.get("data_relation") == "maps"]), 2)


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(AcceptanceTests)
    raise SystemExit(not unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful())
