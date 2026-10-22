"""Independent module invariants; also runs in either shipped project's gate."""
from copy import deepcopy
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
for folder in (ROOT / "skills/business-observer/scripts", ROOT / "observer_runtime", ROOT / "observer_generated/runtime"):
    if folder.is_dir(): sys.path.insert(0, str(folder))
from bo_stategraph import BOStateGraph, bo_export_view, bo_read_export
from change_sync import config


def model():
    return {"machine": {"states": ["waiting", "running", "done"], "values": ["waiting", "running", "done"],
        "initial": "waiting", "events": {"start": {"payload": {}}, "finish": {"payload": {}}},
        "context": {"slots": {"type": "integer", "min": 0}}, "guards": {"allowed": "actual guard"},
        "transitions": [{"source": "waiting", "dest": "running", "trigger": "start", "conditions": "allowed"},
                        {"source": "running", "dest": "done", "trigger": "finish"}]},
        "nodes": [{"id": s, "kind": "state", "layer": "state", "value": s} for s in ("waiting", "running", "done")],
        "edges": [{"id": "start", "from": "waiting", "to": "running", "type": "transition"}],
        "scope": {"unknowns": ["unmapped functions"]}, "source_files": ["app.py"]}


class StateGraphTests(unittest.TestCase):
    def setUp(self): self.graph = BOStateGraph(model(), build_id="loaded")

    def observe(self, state="waiting", revision=0, **kw):
        values = dict(instance_id="a", state=state, context={"slots": 1}, revision=revision,
                      evidence_id="e:" + str(revision), build_id="loaded")
        values.update(kw)
        return self.graph.bo_observe(**values)

    def test_structure_exists_before_execution_and_is_defensive(self):
        export = self.graph.bo_export()
        self.assertEqual(export["coverage"]["runtime"], "not_observed")
        self.assertEqual(export["instances"], [])  # Never invent the declared initial state as a runtime fact.
        export["model"]["machine"]["values"].clear()
        self.assertEqual(len(self.graph.bo_definition()["values"]), 3)

    def test_transition_inspection_is_not_execution_or_authorization(self):
        result = self.graph.bo_candidates("waiting", "start")
        self.assertEqual(result["candidates"][0]["result"], "unknown")
        self.assertFalse(result["authorizes_execution"])
        self.assertEqual(self.graph.bo_instances(), [])
        self.assertEqual(self.graph.bo_candidates("waiting", "start", guards={"allowed": True})["candidates"][0]["result"], "matched")

    def test_actual_invalid_transition_and_types_are_visible(self):
        self.observe()
        result = self.observe("running", 1, event="start", guards={"allowed": False}, context={"slots": True})
        self.assertTrue(result["accepted"])
        self.assertEqual(result["status"], "mismatch")
        self.assertEqual(result["observed"]["state"], "running")
        self.assertIn("actual transition differs from declaration", result["errors"])
        self.assertTrue(any("integer" in e for e in result["errors"]))

    def test_gaps_and_missing_guard_facts_remain_unknown(self):
        self.observe()
        result = self.observe("running", 3, event="start")
        self.assertEqual(result["status"], "partial")
        self.assertIn("intermediate revisions", result["missing"])
        self.assertIn("guard evidence", result["missing"])

    def test_build_revision_and_instance_identity(self):
        self.observe()
        self.assertTrue(self.observe()["duplicate"])
        self.assertFalse(self.observe("done", 0)["accepted"])
        self.assertFalse(self.observe("done", 4, build_id="different")["accepted"])
        self.observe("running", 1, instance_id="b")
        self.assertEqual([x["observed"]["state"] for x in self.graph.bo_instances()], ["waiting", "running"])
        self.assertEqual(self.graph.bo_export()["coverage"]["rejected_observations"], 2)

    def test_loaded_definition_drift(self):
        declaration = self.graph.bo_definition()
        self.assertTrue(self.graph.bo_check_definition(declaration)["valid"])
        declaration["transitions"].pop()
        self.assertFalse(self.graph.bo_check_definition(declaration)["valid"])

    def test_full_view_export_retains_instances_evidence_and_stale_binding(self):
        view = {"model": model(), "manifest": {"build_id": "loaded"}, "binding_status": {"status": "stale"},
            "machine": {"configurations": [{"attempt": "old", "run_build_id": "old-build"}, {"attempt": "new"}]},
            "events": [{"id": "real:1", "depends": [{"id": "real:0", "type": "data"}]}],
            "authority": {"state": "waiting"}, "health": {"dropped": 2}}
        result = bo_export_view(view)
        self.assertEqual(result["model"], view["model"])
        self.assertEqual(result["runtime"]["machine"], view["machine"])
        self.assertEqual(result["runtime"]["events"], view["events"])
        self.assertEqual(result["runtime"]["health"]["dropped"], 2)
        self.assertEqual(result["binding"]["status"], "stale")
        result["model"]["nodes"].clear()
        self.assertEqual(len(view["model"]["nodes"]), 3)

    def test_round_trip_and_tampered_export(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            path = Path(directory) / "export.json"
            value = self.graph.bo_export()
            path.write_text(json.dumps(value), encoding="utf-8")
            self.assertEqual(bo_read_export(path), value)
            value["model"]["edges"].clear()
            path.write_text(json.dumps(value), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "digest mismatch"): bo_read_export(path)

    def test_missing_states_or_edges_rejected(self):
        for mutate in (lambda m: m["nodes"].pop(), lambda m: m["edges"][0].update(to="missing")):
            value = model(); mutate(value)
            with self.assertRaises(ValueError): BOStateGraph(value, build_id="b")

    def test_modes_preserve_same_model_and_observation_functions(self):
        self.observe()
        driven = BOStateGraph(model(), build_id="loaded", mode="drive")
        driven.bo_observe(**self.graph.bo_instances()[0]["observed"])
        a, b = self.graph.bo_export(), driven.bo_export()
        for key in ("model", "instances", "definition_sha256", "coverage"):
            self.assertEqual(a[key], b[key])

    def test_development_choice_cannot_disable_observation_checks(self):
        value = {"model": "model.json", "manifest": "manifest.json", "code_files": ["app.py"],
            "watch_files": ["bo_stategraph.py"], "acceptance": "acceptance.json",
            "observations_command": ["python", "observe.py"],
            "test_commands": [["python", "test.py"]],
            "required_probes": [{"node": "start"}], "required_runtime_probes": [{"node": "start"}],
            "stategraph": {"module": "bo_stategraph.py", "execution_mode": "observe",
                           "development_mode": "guided", "decision_source": "default"}}
        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            root = Path(directory)
            def load():
                (root / "sync.json").write_text(json.dumps(value), encoding="utf-8")
                return config(root, "sync.json")
            value['source_scope']={'roots':['.'],'require_symbol_classification':True}
            value['require_mapping_witnesses']=True
            self.assertEqual(load()["stategraph"]["development_mode"], "guided")
            value["stategraph"]["development_mode"] = "observe"
            with self.assertRaisesRegex(ValueError, "silence is not opt-out"): load()
            value["stategraph"].update(decision_source="user", decision="使用我的实现方式，继续维护监控和状态网。")
            self.assertEqual(load()["stategraph"]["development_mode"], "observe")
            value["required_runtime_probes"] = []
            with self.assertRaisesRegex(ValueError, "both development modes"): load()


if __name__ == "__main__": unittest.main()
