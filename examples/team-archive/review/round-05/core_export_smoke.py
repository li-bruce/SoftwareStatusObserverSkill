"""Run with -I and only the extracted business package on sys.path."""
import json
from pathlib import Path
import sys
import time
import zipfile

root=Path(sys.argv[1]).absolute()
if root.exists():
    raise RuntimeError("Use a fresh isolated directory")
root.mkdir(parents=True)
package=Path(sys.argv[2]).absolute()
with zipfile.ZipFile(package) as archive:
    for name in archive.namelist():
        (root/name).resolve().relative_to(root.resolve())
    archive.extractall(root)
sys.path.insert(0,str(root))
from archive_app.storage import ArchiveStore
from archive_app.service import ArchiveService
from archive_app.policy import check_size

store=ArchiveStore(str(root/"smoke.sqlite3"))
store.seed()
service=ArchiveService(store)
service.set_archive_limit("P1",1)
service.add_approval("DOC-001","alice","bob",time.time()+60)
rid=service.create_run("DOC-001","alice",1)
assert store.snapshot()["runs"][0]["phase"]=="waiting"
assert not service.threads
service.set_archive_limit("P1",8192)
service.tick()
assert store.snapshot()["runs"][0]["phase"]=="waiting"
service.resume_run(rid)
deadline=time.monotonic()+5
while time.monotonic()<deadline:
    service.tick()
    if store.snapshot()["runs"][0]["phase"]=="completed":
        break
    time.sleep(.005)
assert store.snapshot()["runs"][0]["phase"]=="completed"
saved=store.snapshot()["archives"]
assert len(saved)==1
service.set_archive_limit("P1",1)
assert saved==store.snapshot()["archives"]
assert check_size("中"*2730+"ab",8192,"P1",1)["allowed"]
assert not check_size("中"*2731,8192,"P1",1)["allowed"]
try:
    service.set_archive_limit("P1",1.5)
    raise AssertionError("fraction accepted")
except ValueError:
    pass
service.close()
assert not any(name.startswith(("observer_runtime","integrations")) for name in sys.modules)
print(json.dumps({"passed":True,"size_wait":True,"manual_resume":True,
    "snapshot_unchanged":True,"utf8_boundary":True,"fraction_rejected":True,
    "observer_modules_loaded":False,"root":str(root)}))
