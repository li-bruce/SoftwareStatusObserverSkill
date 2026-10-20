"""Dynamic-limit executions, independent of acceptance.json expected values."""
from archive_app.storage import ArchiveStore
from tooling.scenarios import Fixture

CASES = ("size_default","size_equal","size_utf8_over","size_invalid",
         "size_project_isolation","size_running_restore","size_commit_fresh",
         "size_resume_over","size_snapshot_stable","size_persist")


def execute(case: str, mode: str, model: dict, build_id: str) -> dict:
    f = Fixture(mode,model,build_id)
    try:
        observed = {}
        if case == "size_default":
            observed["limit_bytes"] = f.store.snapshot()["projects"][0]["archive_limit_bytes"]
        elif case in ("size_equal","size_utf8_over"):
            body = "中"*2730+"ab" if case=="size_equal" else "中"*2731
            f.service.edit_document("DOC-001","边界资料","BYTES-001",body)
            f.approve()
            rid = f.run()
            if case=="size_equal":
                f.finish(rid)
            run = f.get(rid)
            observed = {"archive_count":len(f.store.snapshot()["archives"]),
                        "content_bytes":run["qualification"]["size"]["content_bytes"],
                        "phase":run["phase"],"workers_started":len(f.gates.started)}
        elif case == "size_invalid":
            before = f.store.snapshot()
            rejected = []
            for value in (0,-1,1.5,1.0,True,"1024",None):
                try:
                    f.service.set_archive_limit("P1",value)
                    rejected.append(False)
                except ValueError:
                    rejected.append(True)
            after = f.store.snapshot()
            observed = {"all_rejected":all(rejected),"unchanged":before==after}
        elif case == "size_project_isolation":
            f.service.set_archive_limit("P1",1)
            with f.store.connect() as db:
                db.execute("INSERT INTO documents VALUES(?,?,?,?,?,?,?)",
                           ("DOC-002","P2","F4","另一项目","P2-001","中"*100,1))
            f.service.add_approval("DOC-002","dana","bob",2000.)
            rid = f.service.create_run("DOC-002","dana",2)
            f.finish(rid)
            project = next(p for p in f.store.snapshot()["projects"] if p["id"]=="P2")
            observed = {"other_project_limit":project["archive_limit_bytes"],
                        "other_completed":f.get(rid)["phase"]=="completed"}
        elif case == "size_running_restore":
            grant = f.approve()
            rid = f.run(1)
            f.started(rid,"content_check")
            original_version = f.get(rid)["input"]["content_version"]
            f.service.set_archive_limit("P1",1)
            observed["index_waited"] = ((rid,"index_check") not in f.gates.started
                                        and f.get(rid)["phase"]=="waiting")
            f.gates.release(rid,"content_check")
            f.until(lambda:f.get(rid)["configuration"]["activities"]["content_check"]=="succeeded",
                    "started content finishes while oversized")
            observed["running_finished"] = not f.store.snapshot()["archives"]
            f.service.set_archive_limit("P1",8192)
            for _ in range(3):
                f.service.tick()
            observed["no_auto_resume"] = (f.get(rid)["phase"]=="waiting"
                and (rid,"index_check") not in f.gates.started and not f.store.snapshot()["archives"])
            f.service.resume_run(rid)
            f.started(rid,"index_check")
            f.finish(rid)
            state = f.store.snapshot()
            observed.update(
                content_started_once=f.gates.start_counts.get((rid,"content_check"))==1,
                archive_count=len(state["archives"]),
                content_version_unchanged=state["documents"][0]["version"]==original_version,
                approval_survived=any(g["id"]==grant and not g["revoked"] for g in state["grants"])
                                  and f.get(rid)["qualification"]["approval_allowed"])
        elif case == "size_commit_fresh":
            f.service.commit_enabled = False
            f.approve()
            rid = f.run()
            f.started(rid,"content_check","index_check")
            f.gates.release()
            f.until(lambda:f.get(rid)["phase"]=="ready","both checks ready before config change")
            # A separately committed config writer, before the final submission transaction.
            # No scheduler evaluation occurs between this update and try_commit.
            with f.store.connect() as db:
                db.execute("BEGIN IMMEDIATE")
                db.execute("UPDATE projects SET archive_limit_bytes=1,limit_revision=limit_revision+1 WHERE id='P1'")
                f.store.bump(db)
                db.commit()
            with f.store.connect() as db:
                db.execute("BEGIN IMMEDIATE")
                run = f.store.get_run(db,rid)
                f.service.try_commit(db,run,f.service.trace(run))
            observed = {"archive_count":len(f.store.snapshot()["archives"]),
                        "limit_bytes":f.get(rid)["qualification"]["size"]["limit_bytes"]}
        elif case == "size_resume_over":
            f.service.set_archive_limit("P1",1)
            f.approve()
            rid = f.run()
            f.service.resume_run(rid)
            observed = {"still_waiting":f.get(rid)["phase"]=="waiting",
                        "workers_started":len(f.gates.started)}
        elif case == "size_snapshot_stable":
            f.approve()
            rid = f.run()
            f.finish(rid)
            before = f.store.snapshot()["archives"]
            f.service.set_archive_limit("P1",1)
            observed["snapshot_unchanged"] = bool(before) and before==f.store.snapshot()["archives"]
        elif case == "size_persist":
            f.service.set_archive_limit("P1",1234)
            reopened = ArchiveStore(f.store.path)
            reopened.seed()
            observed["limit_bytes"] = reopened.snapshot()["projects"][0]["archive_limit_bytes"]
        else:
            raise ValueError(case)
        return {"case":case,"mode":mode,**f.result(observed)}
    finally:
        f.close()
