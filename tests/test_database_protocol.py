"""The shared JSON boundary rejects malformed data projections before ingestion."""

from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "skills/vibelens/scripts"
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(ROOT / "tools"))

from test_multilanguage import project_fixture
from bo_observer.data.projection import project_model, resource_id, field_id
from bo_observer.data.protocol import validate_data_projection, TARGET_SOURCES
from bo_observer.data.sync import synchronize
from bo_observer.protocol import validate_project, validate_event


def data_fixture(project):
    """Build the same projection as synchronization, with no database dependency."""
    fields = [
        {"name": name, "native_type": "INTEGER", "nullable": False} for name in ("id", "owner_id")
    ]
    foreign_key = {
        "kind": "foreign_key",
        "name": "owner",
        "fields": ["owner_id"],
        "target": "table:users",
        "target_fields": ["id"],
    }
    catalog = {
        "store_id": "app",
        "engine": "sqlalchemy",
        "origin": "database",
        "coverage": "partial",
        "limitations": ["Only selected tables were inspected."],
        "resources": [
            {
                "key": "table:images",
                "kind": "table",
                "name": "images",
                "fields": fields,
                "constraints": [
                    foreign_key,
                    {
                        "kind": "foreign_key",
                        "name": "archived_owner",
                        "fields": ["owner_id"],
                        "target": "table:archived_users",
                        "target_fields": ["id"],
                    },
                ],
            },
            {
                "key": "table:users",
                "kind": "table",
                "name": "users",
                "fields": fields[:1],
                "constraints": [],
            },
        ],
    }
    config = {
        "stores": [
            {
                "id": "app",
                "label": "Application data",
                "engine": "sqlalchemy",
                "parent": "advance",
                "source_files": ["models.py"],
                "model_layer": "SQLAlchemy",
            }
        ],
        "operations": [
            {
                "id": name,
                "label": name,
                "parent": "advance",
                "source": {"path": "worker.py", "symbol": "advance"},
                "store": "app",
                "action": action,
                "targets": [] if action == "transform" else ["table:images"],
                "parameters": {"id": "number"},
                "before": {},
                "after": {"count": "number"},
                "inputs": ["db.read"] if action == "transform" else [],
            }
            for name, action in (
                ("db.read", "read"),
                ("db.write", "write"),
                ("db.transform", "transform"),
            )
        ],
    }
    declaration = deepcopy(catalog)
    declaration.update(origin="declaration", validation_scope="application")
    bundle = {
        "source_id": "source-1",
        "catalog_id": "catalog-1",
        "catalogs": [catalog],
        "declarations": [declaration],
    }
    return {**project, "model": project_model(project["model"], config, bundle)}


class DatabaseProtocolTests(unittest.TestCase):
    def setUp(self):
        scratch = ROOT / ".validation"
        scratch.mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=scratch)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.base = project_fixture(self.root)
        self.project = data_fixture(self.base)

    def mutate_node(self, node_id, key, value, *, without_marker=False):
        project = deepcopy(self.project)
        node = next(n for n in project["model"]["nodes"] if n["id"] == node_id)
        node[key] = value
        if without_marker:
            node.pop("managed_by", None)
        return project

    def test_canonical_projection_accepts_partial_application_and_outside_scope_facts(self):
        validate_project(self.project)
        validate_data_projection(self.project["model"])
        nodes = self.project["model"]["nodes"]
        self.assertTrue(
            any(n.get("data_metadata", {}).get("status") == "outside_scope" for n in nodes)
        )
        self.assertTrue(
            any(n.get("data_metadata", {}).get("status") == "application_declared" for n in nodes)
        )
        project = deepcopy(self.project)
        next(n for n in project["model"]["nodes"] if n["id"] == resource_id("app", "table:images"))[
            "data_metadata"
        ]["status"] = "unverified"
        validate_project(project)

    def test_roles_origin_coverage_and_metadata_are_strict_even_without_marker(self):
        dataset = resource_id("app", "table:images")
        for key, value in (
            ("data_role", "arbitrary"),
            ("data_role", []),
            ("data_origin", "guessed"),
            ("data_coverage", "probably_complete"),
            ("data_store", "missing"),
            ("data_metadata", []),
            ("data_metadata", {"status": "matched"}),
        ):
            for without_marker in (False, True):
                with self.subTest(key=key, value=value, without_marker=without_marker):
                    with self.assertRaises(ValueError):
                        validate_project(
                            self.mutate_node(dataset, key, value, without_marker=without_marker)
                        )
        with self.assertRaises(ValueError):
            validate_data_projection(self.mutate_node(dataset, "kind", "function")["model"])

    def test_field_metadata_native_constraints_and_identity_cannot_be_forged(self):
        column = field_id("app", "table:images", "id")
        for mutation in (
            {"nullable": "false"},
            {"default": {"raw": "value"}},
            {"required": 1},
            {"status": "verified_by_ai"},
            {"declared": {"name": "different", "native_type": "INTEGER", "nullable": False}},
        ):
            project = deepcopy(self.project)
            next(n for n in project["model"]["nodes"] if n["id"] == column)["data_metadata"].update(
                mutation
            )
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                validate_project(project)
        for key, value in (("data_key", "table:images.wrong"), ("parent", "advance")):
            with self.subTest(key=key), self.assertRaises(ValueError):
                validate_project(self.mutate_node(column, key, value))
        project = deepcopy(self.project)
        dataset = next(
            n for n in project["model"]["nodes"] if n["id"] == resource_id("app", "table:images")
        )
        dataset["data_metadata"]["constraints"][0]["target_fields"] = []
        with self.assertRaises(ValueError):
            validate_project(project)

    def test_operation_source_action_and_capture_need_common_shapes(self):
        mutations = [
            ("source", {"path": "../outside.py", "symbol": "query"}),
            ("source", {"path": "absent.py", "symbol": "query"}),
            ("source", {"path": "worker.py", "symbol": ""}),
            ("data_metadata", {"action": "transform", "targets": []}),
            ("data_metadata", {"action": "read", "targets": ["table:absent"]}),
            ("data_metadata", {"action": "write", "targets": ["table:images", "table:users"]}),
            (
                "data_metadata",
                {
                    "action": "read",
                    "targets": ["table:images"],
                    "target_actions": {"table:images": "write"},
                },
            ),
            ("capture", {"in": {}, "out": {}}),
        ]
        for key, value in mutations:
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                validate_project(self.mutate_node("db.read", key, value))
        for path, value in (
            (["out", "rows"], "string"),
            (["in", "parameters"], {"x": ["number", "string"]}),
            (["out", "result"], {"x": "object"}),
        ):
            project = deepcopy(self.project)
            capture = next(n for n in project["model"]["nodes"] if n["id"] == "db.read")["capture"]
            capture[path[0]][path[1]] = value
            with self.subTest(path=path), self.assertRaises(ValueError):
                validate_project(project)

    def test_runtime_target_roles_cannot_claim_unobserved_or_unknown_targets(self):
        from bo_observer.data.protocol import validate_target_access

        for access in (
            [{"target": "table:images", "action": "guessed"}],
            [{"target": "table:absent", "action": "write"}],
            [{"target": "table:images", "action": "read"}] * 2,
        ):
            with self.subTest(access=access), self.assertRaises(ValueError):
                validate_target_access({"targets": ["table:images"], "target_access": access})

    def test_edge_type_roles_and_constraint_endpoints_are_checked_without_marker(self):
        for relation, patch in (
            ("reads", {"data_relation": "guessed"}),
            ("reads", {"data_relation": []}),
            ("reads", {"type": "flow"}),
            ("reads", {"from": "advance"}),
            ("writes", {"to": resource_id("app", "table:users")}),
            ("transforms", {"to": "advance"}),
            ("references", {"data_constraints": []}),
            ("references", {"data_origin": "guessed"}),
            ("maps", {"to": field_id("app", "table:images", "owner_id")}),
        ):
            project = deepcopy(self.project)
            edge = next(e for e in project["model"]["edges"] if e.get("data_relation") == relation)
            edge.pop("managed_by")
            edge.update(patch)
            with self.subTest(relation=relation, patch=patch), self.assertRaises(ValueError):
                validate_project(project)

    def test_managed_nodes_and_edges_cannot_hide_their_role(self):
        project = deepcopy(self.project)
        next(n for n in project["model"]["nodes"] if n["id"] == "db.read").pop("data_role")
        with self.assertRaises(ValueError):
            validate_project(project)
        project = deepcopy(self.project)
        next(e for e in project["model"]["edges"] if e.get("data_relation") == "reads").pop(
            "data_relation"
        )
        with self.assertRaises(ValueError):
            validate_project(project)
        project = deepcopy(self.project)
        next(
            e for e in project["model"]["edges"] if e.get("managed_by") and e["type"] == "contains"
        )["from"] = "done"
        with self.assertRaises(ValueError):
            validate_project(project)

    def test_registry_and_managed_source_paths_are_portable_and_complete(self):
        for key, value in (
            ("source_id", ""),
            ("catalog_id", []),
            ("protocol", "unknown"),
            ("stores", ["app", "app"]),
            ("stores", ["other"]),
            ("managed_source_files", ["../outside.py"]),
            ("managed_source_files", ["C:/outside.py"]),
            ("managed_source_files", ["/outside.py"]),
            ("managed_source_files", ["missing.py"]),
            ("managed_source_files", ["worker.py", "worker.py"]),
        ):
            project = deepcopy(self.project)
            project["model"]["database"][key] = value
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                validate_project(project)
        project = deepcopy(self.project)
        project["model"].pop("database")
        with self.assertRaises(ValueError):
            validate_project(project)

    def test_non_database_project_validation_does_not_import_optional_drivers(self):
        path = self.root / "plain.json"
        path.write_text(json.dumps(self.base), encoding="utf-8")
        code = """
import builtins, json, sys
original = builtins.__import__
def guarded(name, *args, **kwargs):
    if name.split('.')[0] in {'sqlalchemy','pymongo','redis','neo4j','sqlglot','pygments'}:
        raise AssertionError('optional dependency imported: ' + name)
    return original(name, *args, **kwargs)
builtins.__import__ = guarded
sys.path.insert(0, sys.argv[1])
from bo_observer.protocol import validate_project
validate_project(json.load(open(sys.argv[2], encoding='utf-8')))
"""
        result = subprocess.run(
            [sys.executable, "-B", "-c", code, str(SCRIPTS), str(path)],
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_removed_config_fails_even_when_old_graph_is_still_valid(self):
        path = self.root / "bo_stategraph/project.json"
        self.assertTrue(synchronize(self.root)["valid"])
        for document in (self.project, self.project["model"]):
            path.write_text(json.dumps(document), encoding="utf-8")
            result = synchronize(self.root)
            self.assertFalse(result["valid"], result)
            self.assertIn("configuration removed", result["errors"][0])

    def test_event_target_provenance_is_a_closed_enum_for_data_operations(self):
        event = {
            "protocol": "bo-event/v1",
            "schema_version": 3,
            "project_id": "fixture",
            "model_revision": "1",
            "build_id": "build-1",
            "run_id": "run-1",
            "producer_id": "producer-1",
            "id": "e1",
            "seq": 1,
            "node": "db.read",
            "phase": "return",
            "entity": "app",
            "attempt": "once",
            "scope": "application",
            "call_id": "c1",
            "parent_call_id": None,
            "basis": {},
            "inputs": {},
            "outputs": {},
            "depends": [],
            "observed_at": "2026-10-24T00:00:00Z",
        }
        for value in TARGET_SOURCES:
            event["outputs"] = {"target_source": value}
            validate_event(event, self.project, "build-1")
        for value in ("guessed", None, [], 1):
            event["outputs"] = {"target_source": value}
            with self.subTest(value=value), self.assertRaises(ValueError):
                validate_event(event, self.project, "build-1")


if __name__ == "__main__":
    unittest.main()
