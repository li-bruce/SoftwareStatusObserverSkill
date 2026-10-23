"""Database changes must update the graph and fail independent stale checks."""

from contextlib import closing
from copy import deepcopy
import json
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "skills/business-observer/scripts"
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(ROOT / "tools"))

from test_multilanguage import project_fixture
from bo_observer.data.catalog import collect
from bo_observer.data.contract import CONFIG_PATH, CATALOG_PATH, load_config, validate_catalog
from bo_observer.data.projection import field_id, resource_id, structure_differences
from bo_observer.data.sync import runtime_errors, synchronize


class DatabaseSyncTests(unittest.TestCase):
    def setUp(self):
        scratch = ROOT / ".validation"
        scratch.mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=scratch)
        self.root = Path(self.temp.name)
        self.addCleanup(self.temp.cleanup)
        self.project = project_fixture(self.root)
        self.database = self.root / "application.db"
        with closing(sqlite3.connect(self.database)) as connection, connection:
            connection.execute(
                "CREATE TABLE images (id INTEGER PRIMARY KEY NOT NULL, title VARCHAR(40) NOT NULL)"
            )
        self.model_source = "from sqlalchemy import MetaData, Table, Column, Integer, String\nmetadata = MetaData()\nimages = Table('images', metadata, Column('id', Integer, primary_key=True), Column('title', String(40), nullable=False))\n"
        (self.root / "models.py").write_text(self.model_source, encoding="utf-8")
        self.config = {
            "protocol": "bo-databases/v1",
            "stores": [
                {
                    "id": "app",
                    "label": "Application data",
                    "engine": "sqlalchemy",
                    "url_env": "BO_TEST_SYNC_URL",
                    "parent": "advance",
                    "selection": {
                        "source": "user",
                        "answer": "Use SQLite with SQLAlchemy",
                        "locator": "synthetic conversation 1",
                    },
                    "model_layer": "SQLAlchemy",
                    "source_files": ["models.py"],
                }
            ],
            "operations": [
                {
                    "id": "db.query",
                    "label": "Load images",
                    "parent": "advance",
                    "source": {"path": "worker.py", "symbol": "advance"},
                    "store": "app",
                    "action": "read",
                    "targets": ["table:images"],
                    "parameters": {},
                    "before": {},
                    "after": {},
                    "required_cases": ["query-success"],
                }
            ],
        }
        self.write_config()
        self.environment = patch.dict(os.environ, {"BO_TEST_SYNC_URL": "sqlite:///application.db"})
        self.environment.start()
        self.addCleanup(self.environment.stop)

    def write_config(self):
        (self.root / CONFIG_PATH).write_text(json.dumps(self.config), encoding="utf-8")

    def model(self):
        return json.loads((self.root / "bo_stategraph/project.json").read_text(encoding="utf-8"))[
            "model"
        ]

    def enable_exporter(self):
        script = (
            "import sys, json\nsys.path.insert(0, "
            + repr(str(SCRIPTS))
            + ")\nfrom models import metadata\nfrom bo_observer.data.catalog import export_sqlalchemy_metadata\nprint(json.dumps(export_sqlalchemy_metadata(metadata, 'app')))\n"
        )
        (self.root / "export_model.py").write_text(script, encoding="utf-8")
        self.config["stores"][0].update(
            declaration="bo_stategraph/declaration.json",
            source_files=["models.py", "export_model.py"],
        )
        self.config["exporters"] = [
            {
                "store": "app",
                "command": ["{python}", "-B", "export_model.py"],
                "output": "bo_stategraph/declaration.json",
            }
        ]
        self.write_config()

    def assert_valid(self, result):
        self.assertTrue(result["valid"], result)

    def test_sync_check_and_ddl_refresh_preserve_authored_graph_and_personal_preferences(self):
        view = self.root / "bo_stategraph/preferences/personal.json"
        view.parent.mkdir()
        original = '{"positions":{"advance":{"x":30,"y":40}},"hiddenNodeIds":["db.query"],"expanded":["advance"]}\n'
        view.write_text(original, encoding="utf-8")
        before_authored = deepcopy(self.project["model"]["nodes"])
        self.assert_valid(synchronize(self.root))
        initial = self.model()
        initial_ids = {node["id"] for node in initial["nodes"]}
        self.assert_valid(synchronize(self.root, update=False))
        unchanged = synchronize(self.root)
        self.assertFalse(unchanged["changed"])
        with closing(sqlite3.connect(self.database)) as connection, connection:
            connection.execute("ALTER TABLE images ADD COLUMN reviewed BOOLEAN")
            connection.execute("ALTER TABLE images RENAME COLUMN title TO caption")
        stale = synchronize(self.root, update=False)
        self.assertFalse(stale["valid"])
        self.assertTrue(stale["changed"])
        self.assertEqual(initial, self.model(), "check mode must not repair the graph")
        self.assert_valid(synchronize(self.root))
        updated = self.model()
        updated_ids = {node["id"] for node in updated["nodes"]}
        self.assertIn(resource_id("app", "table:images"), initial_ids & updated_ids)
        self.assertIn(field_id("app", "table:images", "id"), initial_ids & updated_ids)
        self.assertIn(field_id("app", "table:images", "caption"), updated_ids)
        self.assertNotIn(field_id("app", "table:images", "title"), updated_ids)
        self.assertEqual(
            [node for node in updated["nodes"] if "managed_by" not in node], before_authored
        )
        self.assertEqual(view.read_text(encoding="utf-8"), original)
        self.assert_valid(synchronize(self.root, update=False))

    def test_source_change_runs_native_model_export_and_missing_migration_fails(self):
        self.enable_exporter()
        self.assert_valid(synchronize(self.root))
        declaration = self.root / "bo_stategraph/declaration.json"
        first = json.loads(declaration.read_text(encoding="utf-8"))
        changed_source = self.model_source.replace(
            "nullable=False))", "nullable=False), Column('reviewed', Integer))"
        )
        (self.root / "models.py").write_text(changed_source, encoding="utf-8")
        check = synchronize(self.root, update=False)
        self.assertFalse(check["valid"])
        self.assertTrue(
            any(
                isinstance(error, dict)
                and error.get("schema_difference", {}).get("field") == "reviewed"
                for error in check["errors"]
            ),
            check,
        )
        self.assertEqual(json.loads(declaration.read_text(encoding="utf-8")), first)
        update = synchronize(self.root)
        self.assertFalse(
            update["valid"], "a refreshed graph cannot make an unapplied migration valid"
        )
        column = next(
            node
            for node in self.model()["nodes"]
            if node["id"] == field_id("app", "table:images", "reviewed")
        )
        self.assertEqual(column["data_metadata"]["status"], "declared_only")
        with closing(sqlite3.connect(self.database)) as connection, connection:
            connection.execute("ALTER TABLE images ADD COLUMN reviewed INTEGER")
        self.assert_valid(synchronize(self.root))
        self.assert_valid(synchronize(self.root, update=False))

    def test_failed_database_collection_keeps_last_valid_files_and_returns_failure(self):
        self.assert_valid(synchronize(self.root))
        paths = [self.root / CATALOG_PATH, self.root / "bo_stategraph/project.json"]
        before = {path: path.read_bytes() for path in paths}
        with patch.dict(os.environ, {"BO_TEST_SYNC_URL": "sqlite:///missing.db"}):
            result = synchronize(self.root)
        self.assertFalse(result["valid"])
        self.assertFalse(result["changed"])
        self.assertEqual(before, {path: path.read_bytes() for path in paths})
        self.assertFalse((self.root / "missing.db").exists())

    def test_failed_native_export_does_not_replace_last_valid_files(self):
        self.enable_exporter()
        self.assert_valid(synchronize(self.root))
        paths = [
            self.root / CATALOG_PATH,
            self.root / "bo_stategraph/project.json",
            self.root / "bo_stategraph/declaration.json",
        ]
        before = {path: path.read_bytes() for path in paths}
        (self.root / "export_model.py").write_text(
            "raise RuntimeError('private exporter diagnostic')\n", encoding="utf-8"
        )
        result = synchronize(self.root)
        self.assertFalse(result["valid"])
        self.assertNotIn("private exporter diagnostic", json.dumps(result))
        self.assertEqual(before, {path: path.read_bytes() for path in paths})

    def test_invalid_config_and_unsafe_export_destinations_fail_strictly(self):
        original = deepcopy(self.config)
        mutations = [
            lambda config: config["stores"][0].pop("selection"),
            lambda config: config["stores"][0].update(engine="unknown"),
            lambda config: config["stores"].append(deepcopy(config["stores"][0])),
            lambda config: config["operations"][0].update(store="missing"),
            lambda config: config["operations"][0].update(required_cases=[]),
            lambda config: config["operations"][0].update(
                parameters={"password": "capture-everything"}
            ),
            lambda config: config["stores"][0].update(source_files=["../outside.py"]),
            lambda config: config["stores"][0].update(url_env="postgresql://user:password@host/db"),
        ]
        for index, mutate in enumerate(mutations):
            with self.subTest(mutation=index):
                self.config = deepcopy(original)
                mutate(self.config)
                self.write_config()
                with self.assertRaises((ValueError, KeyError)):
                    load_config(self.root)
        self.config = original
        self.enable_exporter()
        self.config["stores"][0]["declaration"] = "models.py"
        self.config["exporters"][0]["output"] = "models.py"
        self.write_config()
        with self.assertRaisesRegex(ValueError, "overwrite"):
            load_config(self.root)

    def test_catalog_duplicates_and_incorrect_store_identity_are_rejected(self):
        actual = collect(self.config["stores"][0], root=self.root)
        for mutate in (
            lambda item: item.update(store_id="different"),
            lambda item: item["resources"].append(deepcopy(item["resources"][0])),
            lambda item: item["resources"][0]["fields"].append(
                deepcopy(item["resources"][0]["fields"][0])
            ),
        ):
            value = deepcopy(actual)
            mutate(value)
            with self.assertRaises(ValueError):
                validate_catalog(value, self.config["stores"][0])

    def test_runtime_cases_require_execution_and_resolved_actual_targets(self):
        self.assert_valid(synchronize(self.root))
        model = self.model()
        self.assertTrue(runtime_errors(self.root, {"runs": []}, model))
        run = {
            "case": "query-success",
            "mode": "on",
            "events": [
                {
                    "node": "db.query",
                    "phase": "return",
                    "inputs": {"operation": "read", "statement": "SELECT * FROM images", "parameters": {}},
                    "outputs": {"status": "succeeded", "targets": ["table:images"],
                                "duration_ms": 1, "unknown_targets": [], "rows_known": False,
                                "target_source": "parsed_sql", "target_access": [{"target": "table:images", "action": "read"}]},
                }
            ],
        }
        self.assertEqual(runtime_errors(self.root, {"runs": [run]}, model), [])
        unresolved = deepcopy(run)
        unresolved["events"][0]["outputs"]["unknown_targets"] = ["dynamic_table"]
        self.assertTrue(runtime_errors(self.root, {"runs": [unresolved]}, model))
        wrong = deepcopy(run)
        wrong["events"][0]["outputs"]["targets"] = ["table:not_configured"]
        self.assertTrue(runtime_errors(self.root, {"runs": [wrong]}, model))
        absent = deepcopy(run)
        absent["events"][0]["outputs"].pop("targets")
        self.assertTrue(runtime_errors(self.root, {"runs": [absent]}, model))

    def recorded_data(self):
        """Run real query, transformation and commit through the public probe API."""
        import sqlalchemy as sa
        from bo_observer.adapters.python.bo_probe import BOProbe
        from bo_observer.data.runtime import BODataRuntime

        query = self.config["operations"][0]
        query.update(parameters={"limit": "number"}, after={"count": "number"})
        for name, action in [("transform", "transform"), ("transaction", "transaction")]:
            operation = {**deepcopy(query), "id": "db." + name, "action": action,
                         "targets": [], "parameters": {}, "after": {}}
            if action == "transform":
                operation.update(before={"count": "number"}, after={"count": "number"})
            self.config["operations"].append(operation)
        self.write_config()
        self.assert_valid(synchronize(self.root))
        model, events = self.model(), []
        engine = sa.create_engine("sqlite:///" + str(self.database))
        probe = BOProbe({"project_id": "data-gate", "model": model}, "build",
                        sink=lambda body, kind: events.append(body))
        runtime = BODataRuntime(probe, self.config)
        try:
            with engine.connect() as connection:
                runtime.execute("db.query", lambda: connection.exec_driver_sql("SELECT * FROM images").all(),
                                statement="SELECT * FROM images", language="sql", parameters={"limit": 2},
                                summarize=lambda rows: {"rows": len(rows), "result": {"count": len(rows)}})
            runtime.transform("db.transform", list, [], before=lambda rows: {"count": len(rows)},
                              after=lambda rows: {"count": len(rows)})
            with runtime.transaction("db.transaction", engine.begin()):
                pass
            self.assertTrue(probe.flush())
            self.assertEqual(probe.bo_errors + runtime.bo_errors, 0)
        finally:
            runtime.close()
            probe.close()
            engine.dispose()
        ids = [operation["id"] for operation in self.config["operations"]]
        cases = [{"case": "query-success", "node": node,
                  "phase": {"db.query": "return", "db.transform": "change", "db.transaction": "commit"}[node]}
                 for node in ids]
        plan = {"features": [{"id": "data", "nodes": ids, "parameters": [], "cases": cases}]}
        return plan, model, {"build_id": "build", "runs": [{"case": "query-success", "mode": "on", "events": events}]}

    def test_data_capture_presence_uses_actual_operation_outcomes(self):
        from bo_observer.workflow.implementation_coverage import runtime_errors as coverage
        plan, model, payload = self.recorded_data()
        self.assertEqual(coverage(plan, model, payload, root=self.root)["errors"], [])
        # A generated marker alone cannot opt a node out of ordinary capture checks.
        self.assertTrue(coverage(plan, model, payload)["errors"])
        for node, field in [("db.query", "result"), ("db.query", "rows"),
                            ("db.transform", "before"), ("db.transaction", "committed")]:
            with self.subTest(node=node, field=field):
                changed = deepcopy(payload)
                for event in changed["runs"][0]["events"]:
                    if event["node"] == node:
                        event.get("outputs", {}).pop(field, None)
                self.assertTrue(coverage(plan, model, changed, root=self.root)["errors"])
        changed = deepcopy(payload)
        next(e for e in changed["runs"][0]["events"] if e["phase"] == "return")["outputs"]["rows"] = "bad"
        self.assertTrue(coverage(plan, model, changed, root=self.root)["errors"])
        changed_model = deepcopy(model)
        next(n for n in changed_model["nodes"] if n["id"] == "db.query")["capture"]["out"]["required_extra"] = "string"
        self.assertTrue(coverage(plan, changed_model, payload, root=self.root)["errors"])

    def test_data_gate_requires_failed_case_error_and_rollback(self):
        from bo_observer.workflow.implementation_coverage import runtime_errors as coverage
        plan, model, payload = self.recorded_data()
        operation = self.config["operations"][2]
        operation["failure_cases"] = ["query-success"]
        self.write_config()
        event = next(e for e in payload["runs"][0]["events"] if e["phase"] == "commit")
        event.update(phase="error")
        plan["features"][0]["cases"][2]["phase"] = "error"
        event["outputs"].update(status="rolled_back", committed=False, error_type="ValueError")
        self.assertEqual(coverage(plan, model, payload, root=self.root)["errors"], [])
        for field in ["error_type", "committed"]:
            changed = deepcopy(payload)
            next(e for e in changed["runs"][0]["events"] if e["phase"] == "error")["outputs"].pop(field)
            self.assertTrue(coverage(plan, model, changed, root=self.root)["errors"])

    def test_database_refresh_and_source_enrichment_reach_one_stable_graph(self):
        from bo_observer.sources import scan
        from bo_observer.graph.code_structure import enrich

        self.assert_valid(synchronize(self.root))
        path = self.root / "bo_stategraph/project.json"
        project = json.loads(path.read_text(encoding="utf-8"))
        project["model"] = enrich(project["model"], scan(self.root, ["worker.py", "models.py"]))
        before = deepcopy(project["model"])
        self.assertIn("code_evidence", next(n for n in before["nodes"] if n["id"] == "db.query"))
        path.write_text(json.dumps(project), encoding="utf-8")
        self.assert_valid(synchronize(self.root, update=False))
        self.assertFalse(synchronize(self.root)["changed"])
        self.assertEqual(self.model(), before)
        project["model"]["nodes"][-1]["label"] = "Tampered generated node"
        data_node = next(n for n in project["model"]["nodes"] if n["id"] == "db.query")
        data_node["capture"]["out"].pop("status")
        path.write_text(json.dumps(project), encoding="utf-8")
        self.assertFalse(synchronize(self.root, update=False)["valid"])

    def test_declared_default_mismatch_cannot_pass(self):
        actual = collect(self.config["stores"][0], root=self.root)
        expected = deepcopy(actual)
        expected["origin"] = "declaration"
        expected["resources"][0]["fields"][1]["default"] = "'Untitled'"
        self.assertTrue(
            structure_differences(actual, expected), "a required server default must be compared"
        )

    def test_declared_unique_constraint_mismatch_cannot_pass(self):
        actual = collect(self.config["stores"][0], root=self.root)
        expected = deepcopy(actual)
        expected["origin"] = "declaration"
        expected["resources"][0]["constraints"].append(
            {"kind": "unique", "name": "title_unique", "fields": ["title"]}
        )
        self.assertTrue(
            structure_differences(actual, expected), "declared uniqueness must be verified"
        )

    def test_foreign_key_actions_pairing_and_generated_names_are_compared(self):
        actual = collect(self.config["stores"][0], root=self.root)
        actual["resources"][0]["constraints"].append(
            {
                "kind": "foreign_key",
                "name": "server_generated_fk",
                "fields": ["id"],
                "target": "table:other",
                "target_fields": ["id"],
                "description": '{"ondelete":"CASCADE"}',
            }
        )
        expected = deepcopy(actual)
        expected["origin"] = "declaration"
        expected["resources"][0]["constraints"][-1]["name"] = ""
        self.assertEqual(structure_differences(actual, expected), [])
        expected["resources"][0]["constraints"][-1]["description"] = "{}"
        self.assertTrue(structure_differences(actual, expected))
        expected = deepcopy(actual)
        expected["resources"][0]["constraints"][-1]["target_fields"] = ["different_id"]
        self.assertTrue(structure_differences(actual, expected))

    def test_constraint_field_references_and_foreign_key_arity_are_strict(self):
        actual = collect(self.config["stores"][0], root=self.root)
        bad_constraints = [
            {"kind": "unique", "name": "wrong", "fields": ["absent"]},
            {"kind": "primary_key", "name": "empty", "fields": []},
            {
                "kind": "foreign_key",
                "name": "wrong",
                "fields": ["id"],
                "target": "table:other",
                "target_fields": [],
            },
            {
                "kind": "foreign_key",
                "name": "wrong",
                "fields": ["id"],
                "target": "table:images",
                "target_fields": ["absent"],
            },
        ]
        for constraint in bad_constraints:
            with self.subTest(constraint=constraint):
                candidate = deepcopy(actual)
                candidate["resources"][0]["constraints"].append(constraint)
                with self.assertRaises(ValueError):
                    validate_catalog(candidate)

    def test_application_validation_is_not_misreported_as_database_enforcement(self):
        actual = collect(self.config["stores"][0], root=self.root)
        declared = deepcopy(actual)
        declared.update(origin="declaration", validation_scope="application")
        declared["resources"][0]["fields"].append(
            {"name": "computed_in_application", "native_type": "string", "nullable": False}
        )
        validate_catalog(declared)
        self.assertEqual(structure_differences(actual, declared), [])
        declared["validation_scope"] = "database"
        self.assertTrue(structure_differences(actual, declared))
        actual["validation_scope"] = "application"
        with self.assertRaisesRegex(ValueError, "provenance"):
            validate_catalog(actual)


if __name__ == "__main__":
    unittest.main()
