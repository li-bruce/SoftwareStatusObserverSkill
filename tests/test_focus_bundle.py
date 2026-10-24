"""Local graph boundaries and portable export integrity, without executing imports."""
from copy import deepcopy
import json
from pathlib import Path
import sys
import subprocess
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/"skills/vibelens/scripts"))
from focus_graph import extract, markdown
from project_bundle import export, inspect, MANIFEST


class FocusTests(unittest.TestCase):
    def setUp(self):
        self.model = {"revision": "r1", "nodes": [{"id": n, "label": n, "kind": "data"} for n in "ABC"],
                      "edges": [{"id": a+b, "from": a, "to": b, "type": "parent", "label": "Direct parent-child"}
                                for a, b in [("A", "B"), ("B", "C")]], "scope": {"unknowns": []}}

    def test_deterministic_readonly_boundaries_no_shortcut(self):
        original = deepcopy(self.model)
        view = extract(self.model, ["A", "C"], depth=0)
        self.assertEqual(view["edges"], [])
        self.assertEqual({b["edge_id"] for b in view["boundaries"]}, {"AB", "BC"})
        self.assertFalse(view["coverage"]["complete"])
        self.assertEqual(self.model, original)
        self.assertEqual(view, extract(self.model, ["C", "A"], depth=0))
        self.assertIn("outside scope", markdown(view))

    def test_all_selected_keeps_original_relations(self):
        view = extract(self.model, ["B"])
        self.assertEqual({e["id"] for e in view["edges"]}, {"AB", "BC"})
        self.assertTrue(view["coverage"]["complete"])

    def test_edge_node_budget_and_filter_report_gaps(self):
        view = extract(self.model, ["B"], max_nodes=1, max_edges=1)
        self.assertEqual(view["coverage"]["crossing_or_omitted_edges"], 2)
        self.assertIn("boundaries", view["coverage"]["limits_hit"])
        filtered = extract(self.model, ["A", "B"], depth=0, relations=["calls"])
        self.assertFalse(filtered["edges"])
        self.assertEqual(filtered["boundaries"][0]["reason"], "relation_filter")

    def test_runtime_does_not_cross_versions_or_runs(self):
        events = [{"id": "e1", "node": "A", "run_id": "run1", "model_revision": "old", "build_id": "b"},
                  {"id": "e2", "node": "A", "run_id": "run2", "model_revision": "r1", "build_id": "b"}]
        view = extract(self.model, ["A"], events=events, run_id="run1", build_id="b")
        self.assertEqual(view["events"], [])
        self.assertTrue(view["coverage"]["evidence_gaps"])
        self.assertEqual(extract(self.model, ["A"], events=events)["events"], [])
        with self.assertRaisesRegex(ValueError, "build_id"):
            extract(self.model, ["A"], events=events, run_id="run1")

    def test_authorization_operators_inheritance_and_cycles_keep_meaning(self):
        """Projection checks only: the extractor never evaluates these policies."""
        for operator in ("direct", "userset", "role", "inherit", "union",
                         "intersection", "exclusion", "context", "tenant", "public"):
            with self.subTest(operator=operator):
                model = {"revision": "policy-1", "nodes": [
                    {"id": "rule", "label": operator, "kind": "decision",
                     "operator": operator, "scope": "tenant-1"},
                    {"id": "first", "label": "First item", "kind": "data"},
                    {"id": "second", "label": "Second item", "kind": "data"}],
                    "edges": [
                        {"id": "one", "from": "first", "to": "rule", "type": "condition",
                         "operand": "base", "rule_ref": "r1"},
                        {"id": "two", "from": "second", "to": "rule", "type": "condition",
                         "operand": "excluded" if operator == "exclusion" else "required",
                         "rule_ref": "r1"}]}
                full = extract(model, ["rule"])
                self.assertEqual(full["nodes"], sorted(model["nodes"], key=lambda n: n["id"]))
                self.assertEqual(full["edges"], model["edges"])
                partial = extract(model, ["rule", "first"], depth=0)
                self.assertEqual(partial["boundaries"][0]["edge_id"], "two")
                self.assertEqual(partial["boundaries"][0]["relation"], model["edges"][1])
                self.assertFalse(partial["coverage"]["complete"])
                self.assertNotIn("allowed", partial)
        # A recursive declaration is not flattened into a direct fact or rejected.
        recursive = deepcopy(self.model)
        recursive["edges"].append(
            {"id": "CA", "from": "C", "to": "A", "type": "inherits", "rule_ref": "recursive-view"})
        view = extract(recursive, ["A"], depth=12)
        self.assertEqual({e["id"]: e for e in view["edges"]},
                         {e["id"]: e for e in recursive["edges"]})

    def test_all_incident_relations_have_edges_or_explicit_boundaries(self):
        # Shared inputs and parallel edges are distinct; a condition cannot vanish.
        model = deepcopy(self.model)
        model["edges"] += [
            {"id": "extra", "from": "A", "to": "B", "type": "excludes", "label": "Exclude"},
            {"id": "self", "from": "B", "to": "B", "type": "refers", "label": "Recursive reference"}]
        for depth in (0, 1, 2):
            view = extract(model, ["B"], depth=depth, max_edges=10)
            accounted = {e["id"] for e in view["edges"]} | {
                b["edge_id"] for b in view["boundaries"]}
            self.assertEqual(accounted, {e["id"] for e in model["edges"]})


class BundleTests(unittest.TestCase):
    def test_cli_relative_root_in_separate_working_directory(self):
        with tempfile.TemporaryDirectory(dir=ROOT/".validation") as tmp:
            root = Path(tmp)
            model = {"revision": "r1", "nodes": [{"id": "n", "kind": "data", "label": "Document"}], "edges": []}
            (root/"model.json").write_text(json.dumps(model), encoding="utf-8")
            (root/"whitebox.json").write_bytes((ROOT/"skills/vibelens/assets/whitebox.example.json").read_bytes())
            (root/"bundle.json").write_text(json.dumps({
                "schema_version": 1, "project_id": "cli-test", "kind": "review",
                "data_policy": "synthetic-only", "files": ["model.json"]}), encoding="utf-8")
            commands = [
                ["focus_graph.py", "--model", "model.json", "--nodes", "n", "--out", "focus.json"],
                ["whitebox_contract.py", "plan"],
                ["project_bundle.py", "export", "--config", "bundle.json", "--out", "review.zip"],
                ["project_bundle.py", "inspect", "--archive", "review.zip"]]
            for script, *args in commands:
                with self.subTest(script=script, args=args):
                    result = subprocess.run([sys.executable, "-X", "utf8", str(
                        ROOT/"skills/vibelens/scripts"/script), *args, "--root", "."],
                        cwd=root, capture_output=True, text=True, encoding="utf-8")
                    self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                    self.assertTrue(json.loads(result.stdout)["valid"])

    def test_roundtrip_scope_and_tamper(self):
        with tempfile.TemporaryDirectory(dir=ROOT/".validation") as tmp:
            root = Path(tmp)
            (root/"app.py").write_text("print('synthetic')", encoding="utf-8")
            config = {"schema_version": 1, "project_id": "trial", "kind": "project",
                      "data_policy": "synthetic-only", "files": ["app.py"], "commands": ["python app.py"]}
            export(root, config, "out.zip")
            self.assertFalse(inspect(root/"out.zip")["executed"])
            with zipfile.ZipFile(root/"out.zip") as archive:
                manifest = archive.read(MANIFEST)
            with zipfile.ZipFile(root/"changed.zip", "w") as archive:
                archive.writestr(MANIFEST, manifest); archive.writestr("app.py", "changed")
            with self.assertRaisesRegex(ValueError, "differs"):
                inspect(root/"changed.zip")
            for file in ["../app.py", ".env", "data.sqlite3", "C:/private", "x\\a.py"]:
                with self.subTest(file=file), self.assertRaises(ValueError):
                    export(root, {**config, "files": [file]}, "bad.zip")
            with self.assertRaises(ValueError):
                export(root, config, "out.zip")


if __name__ == "__main__":
    (ROOT/".validation").mkdir(exist_ok=True)
    unittest.main()
