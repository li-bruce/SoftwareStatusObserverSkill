"""Independent targeted invariants, including observer gaps and invalid transitions."""
import json
from pathlib import Path
import sys
import threading
import sqlite3
import tempfile
import unittest
from types import SimpleNamespace
ROOT=Path(__file__).absolute().parents[1]
sys.path.insert(0,str(ROOT))
from archive_app.policy import check_index, check_content, candidate_allowed, check_size
from archive_app.storage import ArchiveStore
from archive_app.service import ArchiveService
from bo_stategraph.workflow import Workflow, initial_configuration, activity_step
from archive_app.ports import TracePort
from observer_runtime.semantic_probe import Pins, Trace


class Rules(unittest.TestCase):
    def test_utf8_bytes_and_inclusive_boundary(self):
        self.assertEqual(check_size("中🙂",7,"P",1)["content_bytes"],7)
        self.assertTrue(check_size("中🙂",7,"P",1)["allowed"])
        self.assertFalse(check_size("中🙂",6,"P",1)["allowed"])
        self.assertTrue(check_size("",1,"P",1)["allowed"])

    def test_frozen_graph_uses_frozen_sources(self):
        from integrations.bo_server import LocalApplication
        from observer_runtime.behavior_model import capture
        model=json.loads((ROOT/"behavior.json").read_text(encoding="utf-8"))
        manifest=capture(ROOT,model)
        (ROOT/"review/runtime").mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(dir=ROOT/"review/runtime") as directory:
            app=LocalApplication(ROOT,SimpleNamespace(db=str(Path(directory)/"view.sqlite3"),
                delay=0,candidate=True),model,manifest,{"archive_app/policy.py":"current-loaded-source"})
            try:
                old=app.graph_view("live","v1")
                self.assertTrue(old["historical"])
                self.assertEqual(old["binding_status"]["status"],"current")
                self.assertNotEqual(old["manifest"]["build_id"],manifest["build_id"])
                self.assertNotIn("size_guard",{n["id"] for n in old["model"]["nodes"]})
                self.assertNotIn("def check_size",app.version_sources("v1")[2]["archive_app/policy.py"])
                self.assertEqual(app.version_sources("live")[2]["archive_app/policy.py"],"current-loaded-source")
                self.assertEqual(old["machine"]["configurations"][0]["source_status"],"current")
                with self.assertRaises(ValueError):
                    app.version_sources("missing")
            finally:
                app.service.close()
                app.observer.close()

    def test_v1_migration_preserves_data_and_repeat_init_preserves_limit(self):
        (ROOT/"review/runtime").mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(dir=ROOT/"review/runtime") as directory:
            path=Path(directory)/"old.sqlite3"
            with sqlite3.connect(path) as db:
                db.execute("CREATE TABLE projects(id TEXT PRIMARY KEY,title TEXT NOT NULL)")
                db.execute("INSERT INTO projects VALUES('old','existing')")
            db.close()
            store=ArchiveStore(str(path))
            self.assertEqual(store.snapshot()["projects"][0],
                {"id":"old","title":"existing","archive_limit_bytes":8192,"limit_revision":1})
            service=ArchiveService(store)
            service.set_archive_limit("old",1234)
            before=store.snapshot()
            self.assertEqual(ArchiveStore(str(path)).snapshot(),before)
            service.set_archive_limit("old",1234)
            self.assertEqual(store.snapshot(),before)
            for value in (0,-1,1.0,1.5,True,None,"1",2**63):
                with self.assertRaises(ValueError):
                    service.set_archive_limit("old",value)
            with self.assertRaises(ValueError):
                service.set_archive_limit("missing",100)
            self.assertEqual(store.snapshot(),before)
            service.close()

    def test_each_index_condition_is_required(self):
        for args in [("","P1","D1"),("title","","D1"),("title","P1","")]:
            self.assertFalse(check_index(*args)["passed"])
        self.assertTrue(check_index("title","P1","D1")["passed"])

    def test_exact_marker_and_empty_content(self):
        self.assertFalse(check_content("prefix SECRET: suffix")["passed"])
        self.assertTrue(check_content("")["passed"])
        self.assertTrue(check_content("secret:")["passed"])

    def test_expiry_before_equal_after(self):
        request=dict(project_id="P",operator_id="a",document_id="D",content_version=1)
        grant=dict(id="g",**request,reviewer_id="b",revoked=0,deadline=10.0)
        self.assertTrue(candidate_allowed(grant,request,9.999,["b"])["allowed"])
        self.assertFalse(candidate_allowed(grant,request,10.0,["b"])["allowed"])
        self.assertFalse(candidate_allowed(grant,request,10.001,["b"])["allowed"])

    def test_cannot_advance_without_both_results(self):
        machine=Workflow("checking",{"allowed":True,"all_passed":False})
        self.assertFalse(machine.trigger("checked"))
        self.assertEqual(machine.state,"checking")

    def test_cannot_release_running_work_on_cancel_request(self):
        run={"id":"r","phase":"checking","configuration":initial_configuration("r",1,1)}
        activity_step(run,"start","content_check",1.0)
        with self.assertRaises(ValueError):
            activity_step(run,"abort","checks_join",2.0)
        self.assertEqual(run["configuration"]["resources"]["processing_slots"]["available"],0)

    def test_capacity_types_and_bounds(self):
        for capacity in (True,0,3,1.0,"1"):
            with self.assertRaises(ValueError):
                initial_configuration("r",1,capacity)

    def test_observer_off_never_builds_payload(self):
        called=[]
        TracePort().record("n","return",{},lambda:called.append(1))
        self.assertEqual(called,[])

    def test_observer_exception_is_isolated(self):
        def broken(*args,**kwargs):
            raise RuntimeError("fault")
        trace=TracePort(broken)
        self.assertIsNone(trace.record("x","read",{},lambda:{}))
        self.assertEqual(trace.errors,1)

    def test_probe_filters_secrets_and_reports_builder_gap(self):
        model={"revision":"test","nodes":[{"id":"n","capture":{"in":{"length":"number"},"out":{}}}]}
        received=[]
        pins=Pins(model,"build",sink=received.append)
        trace=Trace(pins,"D","A")
        trace.record("n","return",{"param_version":1},lambda:{"inputs":{"length":3,"secret":"credential-do-not-capture"}})
        def broken():
            raise RuntimeError("payload failed")
        trace.record("n","return",{},broken)
        pins.close()
        self.assertEqual(pins.errors,1)
        self.assertNotIn("credential",str(received))
        self.assertEqual(json.loads(received[0])["inputs"],{"length":3})

    def test_full_queue_records_loss(self):
        entered,release=threading.Event(),threading.Event()
        def slow(text):
            entered.set()
            release.wait(2)
        pins=Pins({"revision":"t","nodes":[{"id":"n","capture":{"in":{},"out":{}}}]},"b",sink=slow,capacity=1)
        trace=Trace(pins,"D","A")
        trace.record("n","return",{},lambda:{})
        entered.wait(1)
        for _ in range(10):
            trace.record("n","return",{},lambda:{})
        release.set()
        pins.close()
        self.assertGreater(pins.dropped,0)


if __name__=="__main__":
    unittest.main()
