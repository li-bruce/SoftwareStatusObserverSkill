"""Executed with -I and only the extracted core package on the import path."""
import json
from pathlib import Path
import sys
import threading
import time

ROOT=Path(sys.argv[1]).absolute()
sys.path.insert(0,str(ROOT))
from archive_app.storage import ArchiveStore
from archive_app.service import ArchiveService
from archive_app.policy import check_content

store=ArchiveStore(str(ROOT/"smoke.sqlite3"))
store.seed()
service=ArchiveService(store)


def until(predicate):
    deadline=time.monotonic()+5
    while time.monotonic()<deadline:
        service.tick()
        if predicate():
            return
        time.sleep(.005)
    raise AssertionError("core package did not reach expected state")


service.add_approval("DOC-001","alice","bob",time.time()+60)
rid=service.create_run("DOC-001","alice",2)
until(lambda:len(store.snapshot()["archives"])==1)
saved=dict(store.snapshot()["archives"][0])
service.edit_document("DOC-001","改后标题","RD-001","changed content")
assert store.snapshot()["archives"][0]==saved
assert not check_content("SECRET: simulated")["passed"]
entered,release=threading.Event(),threading.Event()
def gate(*args):
    entered.set()
    if not release.wait(5):
        raise TimeoutError("smoke worker not released")
service.worker_hook=gate
service.add_approval("DOC-001","alice","carol",time.time()+60)
cancelled=service.create_run("DOC-001","alice",1)
assert entered.wait(2)
service.cancel_run(cancelled)
run=next(r for r in store.snapshot()["runs"] if r["id"]==cancelled)
assert run["configuration"]["resources"]["processing_slots"]["available"]==0
assert "index_check" in run["configuration"]["discarded"]
release.set()
until(lambda:next(r for r in store.snapshot()["runs"] if r["id"]==cancelled)["phase"]=="cancelled")
assert len(store.snapshot()["archives"])==1
service.close()
assert not any(name.startswith(("observer_runtime","integrations")) for name in sys.modules)
print(json.dumps({"passed":True,"normal_archive":True,"immutable_snapshot":True,
                  "content_rejection":True,"cancel_natural_completion":True,
                  "observer_modules_loaded":False,"package_root":str(ROOT)}))
