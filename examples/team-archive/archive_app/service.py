"""Archive commands, real worker threads and transaction-protected submission."""
from contextlib import closing
from copy import deepcopy
import math
import sqlite3
import threading
import time
import uuid
from .ports import TracePort, no_trace
from .policy import is_direct_manager, evaluate_approvals, check_content, check_index, check_size
from .storage import ArchiveStore
from .workflow import (ACTIVITIES, ACTIVE, TERMINAL, activity_step, change_phase,
                       initial_configuration)


class ArchiveService:
    def __init__(self, store: ArchiveStore, trace_factory=no_trace, clock=time.time,
                 worker_hook=None, delay: float = 0.0, recover: bool = True,
                 execution_version: str | None = None):
        self.store, self.trace_factory, self.clock = store, trace_factory, clock
        self.worker_hook, self.delay = worker_hook, delay
        self.execution_version = execution_version
        self.lock = threading.RLock()
        self.traces = {}
        self.threads = []
        self.tick_keys = {}
        self.commit_enabled = True
        self.stop_event = threading.Event()
        self.scheduler = None
        if recover:
            self.recover_interrupted()

    def trace(self, run: dict) -> TracePort:
        if run["id"] not in self.traces:
            try:
                self.traces[run["id"]] = self.trace_factory(run["input"]["document_id"], run["id"])
            except Exception:
                self.traces[run["id"]] = TracePort()
        return self.traces[run["id"]]

    def basis(self, db: sqlite3.Connection, run: dict) -> dict:
        return {"param_version":run["input"]["content_version"],
                "epoch":db.execute("SELECT epoch FROM meta WHERE id=1").fetchone()[0],
                "clock":float(self.clock())}

    def evaluate(self, db: sqlite3.Connection, run: dict, trace: TracePort, stage: str) -> dict:
        request = run["input"]
        docrow = db.execute("SELECT * FROM documents WHERE id=?",(request["document_id"],)).fetchone()
        if docrow is None:
            raise ValueError("原资料不存在")
        document = dict(docrow)
        assignments = [dict(r) for r in db.execute(
            "SELECT * FROM assignments WHERE project_id=? AND folder_id=?",
            (document["project_id"], document["folder_id"]))]
        # Complete candidate set for this document, including invalid alternatives.
        approvals = [dict(r) for r in db.execute(
            "SELECT * FROM grants WHERE document_id=? ORDER BY id",(document["id"],))]
        reviewers = [r["id"] for r in db.execute("SELECT id FROM users WHERE role='reviewer'")]
        basis, call = self.basis(db,run), uuid.uuid4().hex
        limit = self.store.project_limit(db,document["project_id"])
        limit_event = trace.record("project_limit","read",basis,lambda:{
            "inputs":{"project_id":document["project_id"]},"outputs":limit},
            call_id=uuid.uuid4().hex,parent_call_id=call)
        read_event = trace.record("authority_read", "read", basis, lambda: {
            "inputs":{"document_id":document["id"]},
            "outputs":{"project_id":document["project_id"],"folder_id":document["folder_id"],
                       "content_version":document["version"],"relation_epoch":basis["epoch"],
                       "approval_count":len(approvals)}}, call_id=call)
        scope = is_direct_manager(document["project_id"],request["operator_id"],
                                   document["folder_id"],assignments,trace,basis,call)
        approval = evaluate_approvals(document["project_id"],request["operator_id"],
            document["id"],request["content_version"],approvals,reviewers,basis["clock"],trace,basis,call)
        size = check_size(request["content"],limit["limit_bytes"],document["project_id"],
                          limit["limit_revision"],trace,basis,call,limit_event)
        current = (document["version"] == request["content_version"]
                   and document["project_id"] == request["project_id"])
        allowed = scope and approval["allowed"] and size["allowed"] and current and not run["stop_reason"]
        reasons = []
        if not current: reasons.append("资料内容版本或所属项目已变化")
        if not scope: reasons.append("当前不是所在文件夹的直接负责人")
        if not approval["allowed"]: reasons.append("没有仍有效的审批")
        if not size["allowed"]:
            reasons.append(f"正文 {size['content_bytes']} 字节，当前上限 {size['limit_bytes']} 字节，超出 {size['excess_bytes']} 字节")
        if run["stop_reason"]: reasons.append("本次运行已停止接收新工作")
        evaluation = {"allowed":allowed,"scope_allowed":scope,"approval_allowed":approval["allowed"],
            "version_current":current,"size_allowed":size["allowed"],"size":size,
            "reasons":reasons,"candidates":approval["candidates"],
            "basis":basis,"all_passed":run["configuration"]["join"]["state"]=="passed"}
        allowed_ids={c["id"] for c in approval["candidates"] if c["allowed"]}
        evaluation["valid_until"]=min((g["deadline"] for g in approvals if g["id"] in allowed_ids),default=None)
        trace.record("commit_guard", "decision", basis, lambda: {
            "inputs":{"stage":stage,"project_id":document["project_id"],
                "folder_id":document["folder_id"],"operator_id":request["operator_id"],
                "run_version":request["content_version"],"current_version":document["version"],
                "all_passed":evaluation["all_passed"],"content_bytes":size["content_bytes"],
                "limit_bytes":size["limit_bytes"],"limit_revision":size["limit_revision"]},
            "outputs":{"allowed":allowed,"scope_allowed":scope,
                "approval_allowed":approval["allowed"],"size_allowed":size["allowed"],
                "version_current":current,"reasons":reasons}},
            depends=[(read_event,"data")],call_id=uuid.uuid4().hex,parent_call_id=call)
        run["qualification"] = evaluation
        return evaluation

    def create_run(self, document_id: str, operator_id: str, capacity: int = 2) -> str:
        if type(capacity) is not int or capacity not in (1,2):
            raise ValueError("名额只能是 1 或 2")
        with self.lock, closing(self.store.connect()) as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT * FROM documents WHERE id=?",(document_id,)).fetchone()
            if row is None or not db.execute("SELECT 1 FROM users WHERE id=?",(operator_id,)).fetchone():
                raise ValueError("资料或操作人不存在")
            doc, ident = dict(row), uuid.uuid4().hex[:12]
            request = {"document_id":doc["id"],"project_id":doc["project_id"],
                       "operator_id":operator_id,"content_version":doc["version"],
                       "content":doc["content"],"title":doc["title"],"document_number":doc["number"]}
            run = {"id":ident,"input":request,"phase":"created","phase_journal":[],
                   "execution_version":self.execution_version,
                   "created":float(self.clock()),"stop_reason":"","resume_required":False,
                   "configuration":initial_configuration(ident,doc["version"],capacity),
                   "qualification":{},"effect_id":None}
            self.store.save_run(db,run)
            db.commit()
            trace = self.trace(run)
            trace.record("archive_request","enter",self.basis(db,run),lambda:{
                "inputs":{"document_id":document_id,"operator_id":operator_id,"capacity":capacity,
                          "content_version":doc["version"]},"outputs":{"attempt":ident}},
                call_id=uuid.uuid4().hex)
        self.advance(ident)
        return ident

    def request_stop(self, run: dict, reason: str, now: float) -> None:
        if run["phase"] in TERMINAL:
            return
        if run["phase"] != "stopping":
            change_phase(run,"stop",{},now)
        run["stop_reason"] = reason
        cfg = run["configuration"]
        cfg["discarded"] = [a for a in ACTIVITIES if cfg["activities"][a] in ("pending","waiting")]
        for a in cfg["discarded"]:
            cfg["wait_reasons"][a] = "已作废，不再启动；等待本次其他检查收尾"

    def settle(self, run: dict, now: float) -> None:
        cfg = run["configuration"]
        if run["phase"]=="stopping" and "running" not in cfg["activities"].values():
            activity_step(run,"abort","checks_join",now)
            change_phase(run,"stale_done" if run["stop_reason"]=="version_changed" else "cancel_done",
                         {"settled":True},now)

    def emit_configuration(self, run: dict, trace: TracePort, basis: dict) -> None:
        cfg = run["configuration"]
        trace.record("flow.checks","change",basis,lambda:{
            "inputs":{"attempt":run["id"],"content_version":run["input"]["content_version"]},
            "outputs":{"revision":cfg["revision"],"phase":run["phase"],
                       "available":cfg["resources"]["processing_slots"]["available"],
                       "join_state":cfg["join"]["state"]}},call_id=uuid.uuid4().hex)

    def advance(self, run_id: str) -> dict:
        launches = []
        with self.lock, closing(self.store.connect()) as db:
            db.execute("BEGIN IMMEDIATE")
            run = self.store.get_run(db,run_id)
            if run["phase"] in TERMINAL:
                db.commit()
                return run
            trace, now = self.trace(run), float(self.clock())
            evaluation = self.evaluate(db,run,trace,"schedule")
            cfg = run["configuration"]
            if not evaluation["version_current"]:
                self.request_stop(run,"version_changed",now)
            if run["phase"]=="stopping":
                self.settle(run,now)
            else:
                if cfg["join"]["state"]=="enabled":
                    activity_step(run,"join","checks_join",now)
                if cfg["join"]["state"]=="rejected":
                    change_phase(run,"reject",{"checks_failed":True},now)
                elif not evaluation["allowed"]:
                    run["resume_required"] = True
                    if run["phase"]!="waiting":
                        change_phase(run,"pause",{},now)
                    for a,s in cfg["activities"].items():
                        if s in ("pending","waiting"):
                            cfg["wait_reasons"][a] = "；".join(evaluation["reasons"])+"；条件恢复后点击继续"
                elif run["resume_required"]:
                    if run["phase"]!="waiting":
                        change_phase(run,"pause",{},now)
                    for a,s in cfg["activities"].items():
                        if s in ("pending","waiting"):
                            cfg["wait_reasons"][a] = "当前条件已恢复，等待点击继续"
                else:
                    if run["phase"] in ("created","waiting"):
                        change_phase(run,"begin",evaluation,now)
                    if cfg["join"]["state"]=="passed" and run["phase"]!="ready":
                        change_phase(run,"checked",{**evaluation,"all_passed":True},now)
                    elif cfg["join"]["state"]!="passed":
                        for activity in ACTIVITIES:
                            if cfg["activities"][activity] not in ("pending","waiting"):
                                continue
                            if cfg["resources"]["processing_slots"]["available"]:
                                cfg["wait_reasons"].pop(activity,None)
                                activity_step(run,"start",activity,now)
                                launches.append((deepcopy(run),activity,dict(evaluation["basis"])))
                            elif cfg["activities"][activity]=="pending":
                                cfg["wait_reasons"][activity] = "等待本次运行的可用名额"
                                activity_step(run,"wait",activity,now)
            if run["phase"]=="ready" and self.commit_enabled:
                self.try_commit(db,run,trace)
            else:
                self.store.save_run(db,run)
                db.commit()
            self.emit_configuration(run,trace,evaluation["basis"])
        for saved, activity, basis in launches:
            worker = threading.Thread(target=self.worker,args=(saved,activity,basis),daemon=True,
                                      name="archive-"+saved["id"]+"-"+activity)
            with self.lock:
                self.threads.append(worker)
            worker.start()
        return run

    def try_commit(self, db: sqlite3.Connection, run: dict, trace: TracePort) -> str | None:
        evaluation = self.evaluate(db,run,trace,"commit")
        cfg, request = run["configuration"], run["input"]
        same_run = cfg["attempt"]==run["id"] and cfg["param_version"]==request["content_version"]
        all_passed = (same_run and cfg["join"]["state"]=="passed"
                      and all(cfg["activities"][a]=="succeeded" and cfg["results"].get(a,{}).get("passed") is True
                              for a in ACTIVITIES))
        if not evaluation["allowed"] or not all_passed or run["resume_required"]:
            change_phase(run,"pause",{},float(self.clock()))
            run["resume_required"] = True
            self.store.save_run(db,run)
            db.commit()
            return None
        existing = self.store.find_archive(db,request["document_id"],request["content_version"])
        ident = existing["id"] if existing else uuid.uuid4().hex[:12]
        if existing is None:
            db.execute("INSERT INTO archives VALUES(?,?,?,?,?,?,?,?,?)",
                (ident,request["document_id"],request["content_version"],request["content"],
                 request["title"],request["project_id"],request["document_number"],run["id"],float(self.clock())))
        run["effect_id"] = ident
        run["reused_archive"] = existing is not None
        change_phase(run,"publish",{**evaluation,"all_passed":all_passed,"effect_saved":True},float(self.clock()))
        self.store.save_run(db,run)
        db.commit()
        # Only after the effect and completed state have committed.
        if existing is None:
            trace.record("archive_commit","commit",evaluation["basis"],lambda:{
                "inputs":{"attempt":run["id"],"document_id":request["document_id"],
                          "content_version":request["content_version"]},
                "outputs":{"effect_id":ident,"persisted":True}},call_id=uuid.uuid4().hex)
        else:
            trace.record("archive_unique","read",evaluation["basis"],lambda:{
                "inputs":{"document_id":request["document_id"],"content_version":request["content_version"]},
                "outputs":{"effect_id":ident,"reused":True}},call_id=uuid.uuid4().hex)
        return ident

    def worker(self, run: dict, activity: str, basis: dict) -> None:
        trace, call = self.trace(run), uuid.uuid4().hex
        trace.record(activity,"enter",basis,lambda:{
            "inputs":{"attempt":run["id"],"content_version":run["input"]["content_version"]},
            "outputs":{}},call_id=call)
        try:
            if self.worker_hook:
                self.worker_hook(run["id"],activity)
            if self.delay:
                time.sleep(self.delay)
            params = run["input"]
            result = (check_content(params["content"],trace,basis,call) if activity=="content_check"
                      else check_index(params["title"],params["project_id"],params["document_number"],trace,basis,call))
            outcome = "succeeded" if result["passed"] else "rejected"
        except Exception:
            result, outcome = {"passed":False,"error":"检查执行出错"}, "failed"
        with self.lock, closing(self.store.connect()) as db:
            db.execute("BEGIN IMMEDIATE")
            current = self.store.get_run(db,run["id"])
            # An interrupted process's workers cannot be revived into another run.
            if current["configuration"]["activities"][activity]!="running":
                db.commit()
                return
            current["configuration"]["results"][activity] = result
            activity_step(current,"finish",activity,float(self.clock()),outcome)
            self.settle(current,float(self.clock()))
            self.store.save_run(db,current)
            db.commit()
            self.emit_configuration(current,trace,self.basis(db,current))

    def resume_run(self, run_id: str) -> dict:
        with self.lock, closing(self.store.connect()) as db:
            db.execute("BEGIN IMMEDIATE")
            run = self.store.get_run(db,run_id)
            if run["phase"] in TERMINAL or run["stop_reason"]:
                raise ValueError("这次运行已结束或正在停止，请新建运行")
            trace = self.trace(run)
            evaluation = self.evaluate(db,run,trace,"resume")
            run["resume_required"] = not evaluation["allowed"]
            self.store.save_run(db,run)
            db.commit()
            trace.record("resume_run","change",evaluation["basis"],lambda:{
                "inputs":{"attempt":run_id},"outputs":{"allowed":evaluation["allowed"]}},
                call_id=uuid.uuid4().hex)
        return self.advance(run_id)

    def cancel_run(self, run_id: str) -> dict:
        with self.lock, closing(self.store.connect()) as db:
            db.execute("BEGIN IMMEDIATE")
            run = self.store.get_run(db,run_id)
            self.request_stop(run,"user_cancelled",float(self.clock()))
            self.settle(run,float(self.clock()))
            self.store.save_run(db,run)
            db.commit()
            trace = self.trace(run)
            trace.record("cancel_run","change",self.basis(db,run),lambda:{
                "inputs":{"attempt":run_id},"outputs":{"phase":run["phase"],
                "running_count":sum(s=="running" for s in run["configuration"]["activities"].values())}},
                call_id=uuid.uuid4().hex)
        return run

    def add_approval(self, document_id: str, operator_id: str, reviewer_id: str,
                     deadline: float) -> str:
        if type(deadline) not in (int,float) or not math.isfinite(deadline):
            raise ValueError("截止时间无效")
        with self.lock, closing(self.store.connect()) as db:
            db.execute("BEGIN IMMEDIATE")
            doc = db.execute("SELECT * FROM documents WHERE id=?",(document_id,)).fetchone()
            reviewer = db.execute("SELECT role FROM users WHERE id=?",(reviewer_id,)).fetchone()
            if doc is None or reviewer is None or reviewer["role"]!="reviewer" or reviewer_id==operator_id:
                raise ValueError("须由另一名审核员审批")
            if not db.execute("SELECT 1 FROM users WHERE id=?",(operator_id,)).fetchone():
                raise ValueError("操作人不存在")
            ident = uuid.uuid4().hex[:12]
            db.execute("INSERT INTO grants VALUES(?,?,?,?,?,?,?,0)",
                (ident,doc["project_id"],operator_id,document_id,doc["version"],reviewer_id,float(deadline)))
            self.store.bump(db)
            db.commit()
        return ident

    def revoke_approval(self, approval_id: str) -> None:
        with self.lock, closing(self.store.connect()) as db:
            db.execute("BEGIN IMMEDIATE")
            if db.execute("UPDATE grants SET revoked=1 WHERE id=?",(approval_id,)).rowcount!=1:
                raise ValueError("审批不存在")
            self.store.bump(db)
            db.commit()
        self.tick()

    def set_archive_limit(self, project_id: str, limit_bytes: int) -> dict:
        if type(limit_bytes) is not int or limit_bytes <= 0:
            raise ValueError("归档大小上限必须是正整数（字节），不能使用小数、零或负数")
        if limit_bytes > 9223372036854775807:
            raise ValueError("归档大小上限超过可保存的整数范围")
        with self.lock, closing(self.store.connect()) as db:
            db.execute("BEGIN IMMEDIATE")
            previous = self.store.project_limit(db,project_id)
            if previous["limit_bytes"] != limit_bytes:
                db.execute("UPDATE projects SET archive_limit_bytes=?,limit_revision=limit_revision+1 WHERE id=?",
                           (limit_bytes,project_id))
                self.store.bump(db)
            result = self.store.project_limit(db,project_id)
            db.commit()
        # Every active run re-reads the project setting; completed snapshots stay fixed.
        self.tick()
        return result

    def edit_document(self, document_id: str, title: str, number: str, content: str) -> None:
        if not all(isinstance(x,str) for x in (title,number,content)) or len(content)>100000:
            raise ValueError("资料字段类型无效或内容过长")
        with self.lock, closing(self.store.connect()) as db:
            db.execute("BEGIN IMMEDIATE")
            if db.execute("UPDATE documents SET title=?,number=?,content=?,version=version+1 WHERE id=?",
                          (title,number,content,document_id)).rowcount!=1:
                raise ValueError("资料不存在")
            self.store.bump(db)
            db.commit()
        self.tick()

    def move_document(self, document_id: str, folder_id: str) -> None:
        with self.lock, closing(self.store.connect()) as db:
            db.execute("BEGIN IMMEDIATE")
            folder = db.execute("SELECT * FROM folders WHERE id=?",(folder_id,)).fetchone()
            if folder is None:
                raise ValueError("目标文件夹不存在")
            if db.execute("UPDATE documents SET folder_id=?,project_id=? WHERE id=?",
                          (folder_id,folder["project_id"],document_id)).rowcount!=1:
                raise ValueError("资料不存在")
            self.store.bump(db)
            db.commit()
        self.tick()

    def tick(self) -> None:
        snapshot=self.store.snapshot()
        now=float(self.clock())
        for run in snapshot["runs"]:
            if run["phase"] not in TERMINAL:
                expiry=tuple((g["id"],now>=g["deadline"]) for g in snapshot["grants"]
                             if g["document_id"]==run["input"]["document_id"])
                key=(snapshot["epoch"],run["configuration"]["revision"],run["phase"],
                     run["resume_required"],run["stop_reason"],self.commit_enabled,expiry)
                if self.tick_keys.get(run["id"])!=key:
                    self.advance(run["id"])
                    self.tick_keys[run["id"]]=key

    def start_scheduler(self) -> None:
        def loop():
            while not self.stop_event.wait(.12):
                self.tick()
        self.scheduler = threading.Thread(target=loop,daemon=True,name="archive-scheduler")
        self.scheduler.start()

    def recover_interrupted(self) -> None:
        with self.lock, closing(self.store.connect()) as db:
            db.execute("BEGIN IMMEDIATE")
            rows = list(db.execute("SELECT payload FROM runs"))
            import json
            for row in rows:
                run = json.loads(row["payload"])
                if run["phase"] in TERMINAL:
                    continue
                cfg = run["configuration"]
                for a,s in list(cfg["activities"].items()):
                    if s=="running":
                        cfg["results"][a]={"passed":False,"error":"进程中断"}
                        activity_step(run,"finish",a,float(self.clock()),"failed")
                activity_step(run,"abort","checks_join",float(self.clock()))
                change_phase(run,"interrupt",{"settled":True},float(self.clock()))
                run["stop_reason"]="process_interrupted"
                self.store.save_run(db,run)
            db.commit()

    def close(self) -> None:
        self.stop_event.set()
        if self.scheduler:
            self.scheduler.join(2)
        for worker in self.threads:
            worker.join(3)
