"""Real commands and independent assertions for both implementation choices."""
import ast
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from app import Job, OwnLogic
from run import ROOT, bo_session
from bo_stategraph.binding import bo_check_sources


class ModeTests(unittest.TestCase):
    def test_both_modes_run_same_wait_resume_commit_and_export(self):
        exports = []
        for mode in ("observe", "drive"):
            job, graph, binding = bo_session(mode)
            states = [job.logic.state]
            for event, slots in (("start", 0), ("resume", 1), ("finish", 1)):
                job.run(event, slots)
                actual = graph.bo_instances()[0]
                self.assertEqual(actual["status"], "observed")
                self.assertEqual(actual["observed"]["state"], job.logic.state)
                self.assertEqual(actual["observed"]["context"]["effects"], job.effects)
                states.append(job.logic.state)
            self.assertEqual(states, ["pending", "waiting", "running", "done"])
            self.assertEqual(job.effects, 1)
            with self.assertRaises(Exception): job.run("finish", 1)
            self.assertEqual(job.effects, 1)
            exports.append(graph.bo_export(binding=binding))
        for key in ("model", "instances", "definition_sha256"):
            self.assertEqual(exports[0][key], exports[1][key])

    def test_unavailable_resume_does_not_claim_running(self):
        for mode in ("observe", "drive"):
            job, graph, _ = bo_session(mode)
            job.run("start", 0)
            before = graph.bo_instances()
            with self.assertRaises(Exception): job.run("resume", 0)
            self.assertEqual(job.logic.state, "waiting")
            self.assertEqual(graph.bo_instances(), before)

    def test_noop_and_broken_observer_do_not_change_business_effects(self):
        def broken(*args): raise OSError("collector unavailable")
        for callback in (None, broken):
            job = Job(OwnLogic(), callback)
            job.run("start", 1); job.run("finish", 1)
            self.assertEqual((job.logic.state, job.effects), ("done", 1))
            self.assertEqual(job.bo_errors, 0 if callback is None else 2)

    def test_plain_python_logic_has_no_observer_import(self):
        tree = ast.parse((ROOT / "app.py").read_text(encoding="utf-8"))
        modules = [n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)]
        self.assertFalse(any(n and "bo_stategraph" in n for n in modules))

    def test_source_edits_are_stale_until_review_and_rebuild(self):
        self.assertEqual(bo_check_sources(ROOT)["status"], "current")
        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            other = Path(directory)
            manifest = json.loads((ROOT / "bo_stategraph/sources.json").read_text(encoding="utf-8"))
            for name in [*manifest["files"], "bo_stategraph/sources.json"]:
                (other / name).parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(ROOT / name, other / name)
            (other / "app.py").write_text("# deliberate unaccepted change\n", encoding="utf-8")
            result = bo_check_sources(other)
            self.assertEqual(result["status"], "stale")
            self.assertEqual(result["changed"], ["app.py"])
            # Editing the application does not erase the independent model.
            self.assertTrue(json.loads((other / "bo_stategraph/model.json").read_text(encoding="utf-8"))["machine"]["states"])


if __name__ == "__main__": unittest.main()
