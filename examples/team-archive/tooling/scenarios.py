"""Real execution fixtures. No imports or reads of expected acceptance values."""
from copy import deepcopy
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
import uuid
from archive_app.policy import is_direct_manager, candidate_allowed
from archive_app.service import ArchiveService
from archive_app.storage import ArchiveStore
from archive_app.workflow import TERMINAL
from integrations.bo_observer import BOObserver

ROOT = Path(__file__).absolute().parents[1]
CASES = (
    "scope_direct_manager","scope_ancestor_only","scope_child_direct_manager",
    "approval_target_exact","approval_target_other_project","approval_target_other_operator",
    "approval_target_other_document","approval_target_other_version","approval_at_deadline",
    "approval_self","approval_not_reviewer","archive_snapshot","edit_after_archive",
    "archive_same_version_twice","revoke_with_alternative","no_approval","secret_content",
    "missing_index","capacity_one","capacity_two","join_pending","loss_and_resume",
    "edit_overlap","cancel_running","cancel_one_of_two","move_before_commit",
    "expire_before_commit","edit_before_commit","concurrent_same_version","restart_interrupted",
)


class Clock:
    def __init__(self):
        self.value = 1000.0

    def __call__(self):
        return self.value


class Gates:
    def __init__(self):
        self.lock = threading.Lock()
        self.started = set()
        self.start_counts = {}
        self.releases = {}
        self.open_all = False

    def __call__(self, run_id, activity):
        key = (run_id,activity)
        with self.lock:
            self.started.add(key)
            self.start_counts[key] = self.start_counts.get(key,0)+1
            release = self.releases.setdefault(key,threading.Event())
            if self.open_all:
                release.set()
        if not release.wait(8):
            raise TimeoutError("test worker was not released")

    def release(self, run_id=None, activity=None):
        with self.lock:
            if run_id is None:
                self.open_all = True
            for (rid,aid),event in self.releases.items():
                if run_id is None or (rid==run_id and (activity is None or aid==activity)):
                    event.set()


class Fixture:
    def __init__(self, mode, model, build_id):
        self.path = ROOT/"review"/"runtime"/uuid.uuid4().hex
        self.path.mkdir(parents=True)
        self.store = ArchiveStore(str(self.path/"authority.sqlite3"))
        self.store.seed()
        self.observer = BOObserver(model,build_id,mode)
        self.clock,self.gates = Clock(),Gates()
        self.service = ArchiveService(self.store,self.observer.trace,self.clock,self.gates,
                                      execution_version=build_id)

    def approve(self, reviewer="bob", deadline=2000.0):
        return self.service.add_approval("DOC-001","alice",reviewer,deadline)

    def run(self, capacity=2):
        return self.service.create_run("DOC-001","alice",capacity)

    def get(self, ident):
        return next(r for r in self.store.snapshot()["runs"] if r["id"]==ident)

    def until(self, condition, label):
        end=time.monotonic()+5
        while time.monotonic()<end:
            self.service.tick()
            if condition():
                return
            time.sleep(.003)
        raise AssertionError("Timed out: "+label+"; "+str([(r["id"],r["phase"],r["configuration"]["activities"]) for r in self.store.snapshot()["runs"]]))

    def started(self, rid, *activities):
        self.until(lambda:all((rid,a) in self.gates.started for a in activities),"actual workers started")

    def finish(self, rid):
        self.gates.release()
        self.until(lambda:self.get(rid)["phase"] in TERMINAL,"run terminal")

    def result(self, observations):
        state=self.store.snapshot()
        configurations=[]
        for run in state["runs"]:
            config=deepcopy(run["configuration"])
            config.update(phase=run["phase"],disposition=run["phase"] if run["phase"] in ("superseded","interrupted","cancelled") else "current")
            configurations.append(config)
        return {"observations":observations,"events":self.observer.snapshot(),
                "configurations":configurations,"authority_snapshot":state}

    def close(self):
        self.gates.release()
        self.service.close()
        self.observer.close()


def max_running(run):
    return max([0]+[sum(v=="running" for v in e["after"]["activities"].values())
                    for e in run["configuration"]["journal"]])


def execute(case: str, mode: str, model: dict, build_id: str) -> dict:
    f=Fixture(mode,model,build_id)
    try:
        observed={}
        if case.startswith("scope_"):
            actor,folder=("dana","F3") if case=="scope_child_direct_manager" else ("alice","F3" if case=="scope_ancestor_only" else "F2")
            snapshot=f.store.snapshot()
            trace=f.observer.trace("DOC-001","policy-"+uuid.uuid4().hex[:8])
            observed["scope_allowed"]=is_direct_manager("P1",actor,folder,snapshot["assignments"],
                trace,{"param_version":1,"epoch":snapshot["epoch"],"clock":f.clock()})
        elif case.startswith("approval_"):
            grant_id=f.approve()
            with f.store.connect() as db:
                field={"approval_target_other_project":"project_id","approval_target_other_operator":"operator_id",
                       "approval_target_other_document":"document_id","approval_target_other_version":"content_version",
                       "approval_self":"reviewer_id","approval_not_reviewer":"reviewer_id"}.get(case)
                value=2 if field=="content_version" else "alice" if field=="reviewer_id" else "DIFFERENT"
                if field:
                    db.execute("UPDATE grants SET "+field+"=? WHERE id=?",(value,grant_id))
                if case=="approval_at_deadline":
                    db.execute("UPDATE grants SET deadline=? WHERE id=?",(f.clock(),grant_id))
                grant=dict(db.execute("SELECT * FROM grants WHERE id=?",(grant_id,)).fetchone())
            reviewers=["bob","carol","alice"] if case=="approval_self" else ["bob","carol"]
            request=dict(project_id="P1",operator_id="alice",document_id="DOC-001",content_version=1)
            result=candidate_allowed(grant,request,f.clock(),reviewers,
                f.observer.trace("DOC-001","policy-"+uuid.uuid4().hex[:8]),
                {"param_version":1,"epoch":1,"clock":f.clock()})
            observed={"candidate_target_matches":result["target_matches"],"candidate_allowed":result["allowed"]}
        elif case=="no_approval":
            rid=f.run()
            observed={"phase":f.get(rid)["phase"]}
        elif case in ("secret_content","missing_index"):
            f.service.edit_document("DOC-001","" if case=="missing_index" else "标题","RD-001",
                                    "有 SECRET: 标记" if case=="secret_content" else "正常内容")
            f.approve()
            rid=f.run()
            f.finish(rid)
            observed={"archive_count":len(f.store.snapshot()["archives"]),"phase":f.get(rid)["phase"]}
        elif case in ("capacity_one","capacity_two","join_pending"):
            f.approve()
            rid=f.run(1 if case=="capacity_one" else 2)
            f.started(rid,"content_check")
            if case=="capacity_one":
                before=f.get(rid)
                f.gates.release(rid,"content_check")
                f.started(rid,"index_check")
                observed["resource_wait_observed"]=any(e["event"]=="wait" for e in before["configuration"]["journal"])
            else:
                f.started(rid,"index_check")
                if case=="join_pending":
                    f.gates.release(rid,"content_check")
                    f.until(lambda:f.get(rid)["configuration"]["activities"]["content_check"]=="succeeded","one actual result")
                    observed["before_completion_archives"]=len(f.store.snapshot()["archives"])
            f.finish(rid)
            observed["max_running"]=max_running(f.get(rid))
        elif case=="loss_and_resume":
            grant=f.approve()
            rid=f.run(1)
            f.started(rid,"content_check")
            f.service.revoke_approval(grant)
            f.gates.release(rid,"content_check")
            f.until(lambda:f.get(rid)["configuration"]["activities"]["content_check"]=="succeeded","running check finishes without approval")
            f.approve()
            f.service.tick()
            observed["pending_did_not_start"]=(rid,"index_check") not in f.gates.started
            observed["before_resume_archives"]=len(f.store.snapshot()["archives"])
            f.service.resume_run(rid)
            f.started(rid,"index_check")
            f.finish(rid)
            observed["completed"]=f.get(rid)["phase"]=="completed"
        elif case=="edit_overlap":
            f.approve()
            old=f.run(1)
            f.started(old,"content_check")
            f.service.edit_document("DOC-001","新版标题","RD-001","版本二的内容")
            f.approve()
            new=f.run(2)
            f.started(new,"content_check","index_check")
            state=f.store.snapshot()
            observed["old_new_visible_while_running"]=(len(state["runs"])==2 and
                f.get(old)["configuration"]["activities"]["content_check"]=="running" and
                f.get(new)["configuration"]["activities"]["content_check"]=="running")
            f.gates.release()
            f.until(lambda:all(r["phase"] in TERMINAL for r in f.store.snapshot()["runs"]),"old/new settle")
            observed["old_archive_count"]=sum(a["content_version"]==1 for a in f.store.snapshot()["archives"])
            observed["new_completed"]=f.get(new)["phase"]=="completed"
        elif case in ("cancel_running","cancel_one_of_two"):
            f.approve()
            rid=f.run(1)
            f.started(rid,"content_check")
            other=f.run(1) if case=="cancel_one_of_two" else None
            if other:
                f.started(other,"content_check")
            f.service.cancel_run(rid)
            observed["held_after_request"]=len(f.get(rid)["configuration"]["resources"]["processing_slots"]["holders"])
            f.finish(rid)
            if other:
                f.until(lambda:f.get(other)["phase"] in TERMINAL,"other run unaffected")
                observed["other_completed"]=f.get(other)["phase"]=="completed"
            observed.update(available_after_end=f.get(rid)["configuration"]["resources"]["processing_slots"]["available"],
                archive_count=len(f.store.snapshot()["archives"]),source_document_exists=bool(f.store.snapshot()["documents"]))
        elif case in ("move_before_commit","expire_before_commit","edit_before_commit"):
            f.approve(deadline=1010)
            f.service.commit_enabled=False
            rid=f.run()
            f.gates.release()
            f.until(lambda:f.get(rid)["phase"]=="ready","checks ready before protected commit")
            if case=="move_before_commit":
                f.service.move_document("DOC-001","F3")
            elif case=="expire_before_commit":
                f.clock.value=1010.0
            else:
                f.service.edit_document("DOC-001","标题","RD-001","changed just before commit")
            f.service.commit_enabled=True
            f.service.tick()
            observed["archive_count"]=len(f.store.snapshot()["archives"])
        elif case=="restart_interrupted":
            code=("import os,sys; from archive_app.storage import ArchiveStore; from archive_app.service import ArchiveService; "
                  "s=ArchiveStore(sys.argv[1]); a=ArchiveService(s,delay=60); a.add_approval('DOC-001','alice','bob',9999999999); "
                  "r=a.create_run('DOC-001','alice',2); print(r,flush=True); os._exit(0)")
            cp=subprocess.run([sys.executable,"-X","utf8","-B","-c",code,f.store.path],
                              cwd=ROOT,capture_output=True,text=True,encoding="utf-8",timeout=10)
            if cp.returncode:
                raise AssertionError(cp.stderr)
            rid=cp.stdout.strip()
            recovered=ArchiveService(f.store,clock=f.clock)
            observed["phase"]=f.get(rid)["phase"]
            recovered.close()
        else:
            grant=f.approve()
            if case=="revoke_with_alternative":
                f.approve("carol")
            rid=f.run()
            f.started(rid,"content_check","index_check")
            if case=="revoke_with_alternative":
                f.service.revoke_approval(grant)
            second=f.run() if case=="concurrent_same_version" else None
            if second:
                f.started(second,"content_check","index_check")
            f.finish(rid)
            if second:
                f.until(lambda:f.get(second)["phase"] in TERMINAL,"concurrent duplicate finishes")
            if case=="archive_same_version_twice":
                second=f.run()
                f.finish(second)
            if case=="edit_after_archive":
                f.service.edit_document("DOC-001","新标题","RD-001","后来的内容")
            state=f.store.snapshot()
            archive=state["archives"][0] if state["archives"] else {}
            observed={"archive":archive,"archive_count":len(state["archives"]),
                "archive_count_for_version":sum(a["document_id"]=="DOC-001" and a["content_version"]==1 for a in state["archives"]),
                "source_document_exists":any(d["id"]=="DOC-001" for d in state["documents"]),
                "source_folder_unchanged":state["documents"][0]["folder_id"]=="F2",
                "completed":f.get(rid)["phase"]=="completed"}
        return {"case":case,"mode":mode,**f.result(observed)}
    finally:
        f.close()
