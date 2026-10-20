"""Field-level, source, evidence and semantic mutation checks."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/"skills/business-observer/scripts"))
sys.path.insert(0, str(ROOT/"examples/delivery"))
from whitebox_contract import assess, static_errors, schema_errors, assertion_errors
from code_structure import scan
from app.service import eligible_grant
from app.ports import Events


class WhiteboxTests(unittest.TestCase):
    def setUp(self):
        self.contract = json.loads((ROOT/"skills/business-observer/assets/whitebox.example.json").read_text(encoding="utf-8"))
        self.model = {"revision": "v1", "nodes": [{"id": "permission", "source": {"path": "app/policy.py", "symbol": "allowed"}}]}
        self.event = {"id": "e1", "run_id": "run1", "attempt": "a1", "call_id": "c1", "entity": "job1",
                      "build_id": "b1", "model_revision": "v1", "node": "permission", "phase": "decision",
                      "inputs": {"version": 1, "grant_version": 1}, "outputs": {"allowed": True}}
        self.payload = {"build_id": "b1", "runs": [{"case": "allowed", "mode": "on", "events": [self.event]}]}

    def test_matching_runtime_passes(self):
        self.assertTrue(assess(self.contract, self.model, self.payload, "b1")["valid"])

    def test_missing_mismatched_stale_or_duplicate_evidence_fails(self):
        changes = [
            lambda p: p["runs"][0].update(events=[]),
            lambda p: p["runs"][0]["events"][0]["inputs"].update(version=2),
            lambda p: p["runs"][0]["events"][0]["inputs"].update(version=True),
            lambda p: p["runs"][0]["events"][0].update(build_id="old"),
            lambda p: p["runs"][0]["events"][0].pop("call_id"),
            lambda p: p["runs"][0]["events"].append(deepcopy(p["runs"][0]["events"][0])),
            lambda p: p["runs"].append(deepcopy(p["runs"][0])),
        ]
        for change in changes:
            with self.subTest(change=change):
                payload = deepcopy(self.payload); change(payload)
                self.assertFalse(assess(self.contract, self.model, payload, "b1")["valid"])

    def test_plan_cannot_disable_evidence(self):
        self.contract["checks"][0]["count"]["min"] = 0
        self.assertTrue(schema_errors(self.contract))

    def test_call_identity_and_parent_are_bound_to_same_execution(self):
        for mismatch in ("run_id", "attempt", "entity"):
            payload = deepcopy(self.payload)
            peer = {**deepcopy(self.event), "id": "e2", mismatch: "different", "phase": "exit"}
            payload["runs"][0]["events"].append(peer)
            self.assertFalse(assess(self.contract, self.model, payload, "b1")["valid"])
        payload = deepcopy(self.payload)
        payload["runs"][0]["events"][0]["parent_call_id"] = "parent"
        self.assertFalse(assess(self.contract, self.model, payload, "b1")["valid"])
        parent = {**deepcopy(self.event), "id": "e2", "node": "request", "call_id": "parent"}
        payload["runs"][0]["events"].append(parent)
        self.assertTrue(assess(self.contract, self.model, payload, "b1")["valid"])
        parent["run_id"] = "other"
        self.assertFalse(assess(self.contract, self.model, payload, "b1")["valid"])

    def test_membership_does_not_confuse_boolean_and_integer(self):
        fields = [{"path": ["value"], "compare": {"path": ["choices"], "op": "in"}}]
        self.assertTrue(assertion_errors({"value": True, "choices": [1]}, fields))
        self.assertFalse(assertion_errors({"value": 1, "choices": [1]}, fields))

    def test_source_signature_must_match(self):
        with tempfile.TemporaryDirectory(dir=ROOT/".validation") as tmp:
            root = Path(tmp); (root/"app").mkdir()
            (root/"app/policy.py").write_text("def allowed(request: str) -> bool:\n    return True\n", encoding="utf-8")
            self.assertTrue(static_errors(self.contract, self.model, scan(root, ["app/policy.py"]), {"R1"}))
            (root/"app/policy.py").write_text("def allowed(request: dict) -> bool:\n    return True\n", encoding="utf-8")
            self.assertEqual(static_errors(self.contract, self.model, scan(root, ["app/policy.py"]), {"R1"}), [])

    def test_real_condition_values_and_short_circuit(self):
        job = {"project": "P", "actor": "A", "param_version": 7, "clock": 10, "epoch": 1, "attempt": "a"}
        grant = {"id": "G", "project": "P", "actor": "A", "version": 6, "revoked": False, "expires": 20}
        events = []
        self.assertFalse(eligible_grant(grant, job, Events(lambda n, p, data: events.append(data))))
        self.assertEqual(events[0]["outputs"]["evaluated"], ["project", "actor", "version"])
        self.assertFalse(events[0]["outputs"]["conditions"]["version"])
        self.assertNotIn("not_expired", events[0]["outputs"]["conditions"])
        self.assertEqual(events[0]["inputs"]["param_version"], 7)

    def test_targeted_mutations_fail_by_business_result(self):
        source = (ROOT/"examples/delivery/app/service.py").read_text(encoding="utf-8")
        job = {"project": "P", "actor": "A", "param_version": 7, "clock": 20, "epoch": 1, "attempt": "a"}
        grant = {"id": "G", "project": "P", "actor": "A", "version": 7, "revoked": False, "expires": 20}
        variants = [
            ("job['clock'] < grant['expires']", "job['clock'] <= grant['expires']", grant),
            ("grant['version'] == job['param_version']", "True", {**grant, "version": 6, "expires": 21}),
        ]
        for i, (before, after, data) in enumerate(variants):
            self.assertFalse(eligible_grant(data, job))
            with tempfile.TemporaryDirectory(dir=ROOT/".validation") as tmp:
                path = Path(tmp)/"mutant.py"; path.write_text(source.replace(before, after, 1), encoding="utf-8")
                spec = importlib.util.spec_from_file_location("mutant"+str(i), path)
                module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
                self.assertTrue(module.eligible_grant(data, job), "mutation must cause actual policy error")
                observed = []
                module.eligible_grant(data, job, Events(lambda n, p, payload: observed.append(payload)))
                event = {**deepcopy(self.event), **observed[0]}
                contract = deepcopy(self.contract)
                contract["checks"][0]["fields"] = [{"path": ["outputs", "allowed"], "type": "boolean", "equals": False}]
                payload = {**self.payload, "runs": [{"case": "allowed", "mode": "on", "events": [event]}]}
                report = assess(contract, self.model, payload, "b1")
                self.assertFalse(report["valid"], "actual mutant decision must fail the independent expected result")
                self.assertTrue(any(error.get("path") == ["outputs", "allowed"]
                                    for error in report["checks"][0]["errors"] if isinstance(error, dict)))


if __name__ == "__main__":
    (ROOT/".validation").mkdir(exist_ok=True)
    unittest.main()
