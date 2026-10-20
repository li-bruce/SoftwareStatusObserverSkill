"""Read-only checks of live authority, saved runs, frozen sources and review evidence."""
from collections import Counter
import hashlib
import json
from pathlib import Path
from urllib.request import urlopen

ROOT=Path(__file__).absolute().parents[2]
OUT=ROOT/"review/v2"
def read(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))
def get(route):
    with urlopen("http://127.0.0.1:8824"+route,timeout=10) as response:
        return json.load(response)

accepted=read(OUT/"accepted.json")
state=get("/api/state")
view=get("/api/view?case=size_commit_fresh")
old=get("/api/view?version=v1")
old_source=get("/api/source?version=v1&path=archive_app/policy.py")
initial=read(OUT/"live-completed.json")
manual=read(OUT/"final-restored-before-continue.json")
run=state["runs"][-1]
assert state["binding"]["status"]=="current"
assert state["build_id"]==run["execution_version"]==accepted["build_id"]
assert state["projects"][0]["archive_limit_bytes"]==8192
assert run["phase"]=="completed" and run["reused_archive"]
assert manual["runs"][-1]["phase"]=="waiting" and manual["runs"][-1]["qualification"]["allowed"]
counts=Counter(e["activity"] for e in run["configuration"]["journal"] if e["event"]=="start")
assert counts=={"content_check":1,"index_check":1}
assert state["archives"]==initial["archives"] and len(state["archives"])==1
assert state["documents"][0]["version"]==1
assert view["binding_status"]["status"]=="current"
saved=view["machine"]["configurations"][0]
assert saved["phase"]=="waiting" and saved["join"]["state"]=="passed"
assert saved["qualification"]["size"]["limit_bytes"]==1 and not saved["qualification"]["allowed"]
assert not view["authority"]["effects"]
assert old["binding_status"]["status"]=="current"
assert old_source["build_id"]==old["manifest"]["build_id"]
assert old_source["build_id"]!=state["build_id"] and "def check_size" not in old_source["source"]
v1_hash=hashlib.sha256((ROOT/"review/v1/project-v1.zip").read_bytes()).hexdigest()
assert v1_hash=="a9b9b706e1c26b517d67f90780165c5c5c0af62c8493b37dd49e9101a1c4d869"
white=read(OUT/"whitebox-results.json")
observed=read(OUT/"observations.json")
assert white["valid"] and len(white["checks"])==11
assert len(observed["runs"])==120
report={"passed":True,"candidate_id":accepted["candidate_id"],"build_id":state["build_id"],
    "scenarios":40,"mode_executions":120,"business_checks":63,"model_checks":9,
    "whitebox_rules":6,"whitebox_event_checks":11,"python_tests":13,
    "live_run":run["id"],"actual_worker_starts":dict(counts),"manual_resume_required":True,
    "content_version":1,"archive_id":state["archives"][0]["id"],"archive_count":1,
    "existing_snapshot_unchanged":True,"final_project_limit":8192,
    "commit_fresh_saved_case":{"all_checks_passed":True,"limit_bytes":1,"allowed":False,"effects":0},
    "source_binding":{"live":view["binding_status"]["status"],"v1":old["binding_status"]["status"],
        "v1_build":old_source["build_id"],"v1_source_has_size_function":False},
    "v1_zip_sha256_unchanged":v1_hash,
    "browser_evidence":["final-build-running-limit.png","final-manual-continue.png",
        "after-fix-current-vs-history.png","layout-v1-same-view.png","layout-v2-same-view.png",
        "preserved-annotation.png","frozen-v1-source.png","graph-final.png","application-final.png"],
    "scope":"Agent-executed synthetic development and browser simulation, not human user research."}
(OUT/"final-audit.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8",newline="\n")
(OUT/"authoritative-final.json").write_text(json.dumps(state,ensure_ascii=False,indent=2),encoding="utf-8",newline="\n")
print(json.dumps(report,ensure_ascii=False))
