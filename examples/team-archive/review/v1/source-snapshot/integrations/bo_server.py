"""Local synthetic-data application and read-only developer graph endpoints."""
from copy import deepcopy
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import mimetypes
from pathlib import Path
import threading
import time
from urllib.parse import parse_qs, urlparse
from archive_app.service import ArchiveService
from archive_app.storage import ArchiveStore
from archive_app.workflow import LABELS
from integrations.bo_observer import BOObserver
from observer_runtime.behavior_model import check

CASE_NAMES={
    "archive_snapshot":"正常归档 · 固定版本快照","capacity_one":"1 个名额 · 索引排队",
    "capacity_two":"2 个名额 · 两项实际重叠","loss_and_resume":"审批失效 · 保留结果后手动继续",
    "edit_overlap":"内容改版 · 旧新运行同时可查","cancel_running":"取消本次 · 实际结束后归还名额",
    "revoke_with_alternative":"撤销一条 · 另一条仍有效","move_before_commit":"提交前目录变化",
    "expire_before_commit":"提交时恰好到期","edit_before_commit":"提交前内容改版",
    "secret_content":"内容包含禁用标记","missing_index":"索引缺少标题",
    "concurrent_same_version":"同版本并发 · 只有一条归档","join_pending":"一项未完成 · 不能提交",
}


class LocalApplication:
    def __init__(self, root, args, model, manifest, sources):
        self.root,self.args,self.model,self.manifest,self.sources=root,args,model,manifest,sources
        dbpath=Path(args.db)
        if not dbpath.is_absolute():
            dbpath=root/dbpath
        self.store=ArchiveStore(str(dbpath))
        self.store.seed()
        self.observer=BOObserver(model,manifest["build_id"],path=str(root/"data/events.jsonl"))
        self.service=ArchiveService(self.store,self.observer.trace,delay=args.delay,
                                    execution_version=manifest["build_id"])
        self.service.start_scheduler()
        self.case_payload=None
        self.case_mtime=None

    def cases(self):
        path=self.root/"review/v1/observations.json"
        if path.exists():
            stamp=path.stat().st_mtime_ns
            if stamp!=self.case_mtime:
                self.case_payload=json.loads(path.read_text(encoding="utf-8-sig"))
                self.case_mtime=stamp
        return self.case_payload

    def graph_view(self, case="live", version="live"):
        snapshot=self.store.snapshot()
        events=self.observer.snapshot()
        historical=False
        build=self.manifest
        model=self.model
        payload=self.cases()
        selected=None
        if payload and case!="live":
            selected=next((r for r in payload["runs"] if r["case"]==case and r["mode"]=="on"),None)
        if selected:
            snapshot=selected["authority_snapshot"]
            events=selected["events"]
            historical=True
        configurations=[]
        for run in snapshot["runs"]:
            config=deepcopy(run["configuration"])
            config.update(phase=run["phase"],disposition=run["phase"] if run["phase"] in
                ("superseded","interrupted","cancelled") else "current",qualification=run["qualification"],
                stop_reason=run["stop_reason"],resume_required=run["resume_required"],
                run_build_id=run.get("execution_version"),
                source_status="current" if run.get("execution_version")==self.manifest["build_id"] else "unbound")
            configurations.append(config)
        latest=snapshot["runs"][-1] if snapshot["runs"] else None
        document=snapshot["documents"][0]
        basis={"param_version":document["version"],"epoch":snapshot["epoch"],"clock":time.time()}
        if historical and latest:
            basis=latest["qualification"].get("basis",basis)
        bound=check(self.root,self.model,self.manifest)
        if self.args.candidate and bound["status"]=="current":
            bound["status"]="candidate_unverified"
        if historical and payload["build_id"]!=self.manifest["build_id"]:
            bound["status"]="stale"
        allowed_cases=["live"]+[r["case"] for r in (payload or {}).get("runs",[]) if r["mode"]=="on" and r["case"] in CASE_NAMES]
        return {"model":model,"manifest":build,"binding_status":bound,"events":events,
                "health":self.observer.health(),"busy":any(r["phase"] not in ("completed","failed","cancelled","superseded","interrupted") for r in snapshot["runs"]),
                "authority":{"entity":document["id"],"basis":basis,"state":latest["phase"] if latest else "created",
                    "parameters":{"param_version":document["version"],"attempt":latest["id"] if latest else None,
                        "capacity":latest["configuration"]["resources"]["processing_slots"]["capacity"] if latest else 2},
                    "approvals":snapshot["grants"],"relation":snapshot["assignments"],
                    "effects":snapshot["archives"],"historical":historical,"case_label":CASE_NAMES.get(case,"当前操作")},
                "machine":{"current":latest["phase"] if latest else "created","configurations":configurations,
                    "journal":[j for r in snapshot["runs"] for j in r["phase_journal"]]},
                "available_cases":allowed_cases,"case_names":CASE_NAMES,"historical":historical}

    def state(self):
        return {**self.store.snapshot(),"labels":LABELS,"clock":time.time(),
                "build_id":self.manifest["build_id"],"delay":self.args.delay,
                "binding":check(self.root,self.model,self.manifest)}

    def command(self, action, values):
        service=self.service
        if action=="run":
            return {"run_id":service.create_run(values["document_id"],values["operator_id"],values["capacity"])}
        if action=="approve":
            return {"approval_id":service.add_approval(values["document_id"],values["operator_id"],values["reviewer_id"],
                                                       time.time()+float(values["seconds"]))}
        if action=="revoke":
            service.revoke_approval(values["approval_id"])
        elif action=="resume":
            service.resume_run(values["run_id"])
        elif action=="cancel":
            service.cancel_run(values["run_id"])
        elif action=="edit":
            service.edit_document(values["document_id"],values["title"],values["number"],values["content"])
        elif action=="move":
            service.move_document(values["document_id"],values["folder_id"])
        else:
            if action not in ("run","approve"):
                raise ValueError("未知操作")
        return {"ok":True}


def serve(root, args, model, manifest, sources):
    application=LocalApplication(root,args,model,manifest,sources)
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):
            pass

        def reply(self,status,body,content_type="application/json; charset=utf-8"):
            raw=json.dumps(body,ensure_ascii=False).encode() if content_type.startswith("application/json") else body
            self.send_response(status)
            self.send_header("Content-Type",content_type)
            self.send_header("Cache-Control","no-store")
            self.send_header("X-Content-Type-Options","nosniff")
            self.send_header("Content-Length",str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def do_GET(self):
            parsed=urlparse(self.path)
            params=parse_qs(parsed.query)
            try:
                if parsed.path=="/api/state":
                    return self.reply(200,application.state())
                if parsed.path=="/api/view":
                    return self.reply(200,application.graph_view(params.get("case",["live"])[0],params.get("version",["live"])[0]))
                if parsed.path=="/api/versions":
                    return self.reply(200,{"versions":["live"]})
                if parsed.path=="/api/source":
                    name=params.get("path",[""])[0]
                    if name not in sources:
                        return self.reply(404,{"error":"该源码不在已加载版本中"})
                    return self.reply(200,{"source":sources[name],"build_id":manifest["build_id"]})
                if parsed.path in ("/","/control"):
                    path=root/"static/app.html"
                elif parsed.path in ("/graph","/graph/"):
                    path=root/"static/graph/index.html"
                elif parsed.path in ("/app.js","/app.css"):
                    path=root/"static"/parsed.path.lstrip("/")
                else:
                    name=parsed.path.lstrip("/")
                    if "/" in name or "\\" in name or name.startswith("."):
                        return self.reply(404,{"error":"找不到页面"})
                    path=root/"static/graph"/name
                if not path.is_file():
                    return self.reply(404,{"error":"找不到页面"})
                return self.reply(200,path.read_bytes(),(mimetypes.guess_type(path.name)[0] or "application/octet-stream")+"; charset=utf-8")
            except Exception as error:
                self.reply(500,{"error":type(error).__name__,"message":str(error)})

        def do_POST(self):
            origin=self.headers.get("Origin")
            if origin and urlparse(origin).netloc not in (f"127.0.0.1:{args.port}",f"localhost:{args.port}"):
                return self.reply(403,{"error":"仅接受本地同源操作"})
            try:
                size=int(self.headers.get("Content-Length","0"))
                if not 0<size<=200000:
                    raise ValueError("请求大小无效")
                values=json.loads(self.rfile.read(size).decode("utf-8"))
                action=urlparse(self.path).path.removeprefix("/api/")
                result=application.command(action,values)
                return self.reply(200,result)
            except (ValueError,KeyError,TypeError) as error:
                return self.reply(400,{"error":str(error)})
    server=ThreadingHTTPServer(("127.0.0.1",args.port),Handler)
    print(json.dumps({"application":f"http://127.0.0.1:{args.port}/",
                      "graph":f"http://127.0.0.1:{args.port}/graph",
                      "build":manifest["build_id"],"candidate":args.candidate}),flush=True)
    try:
        server.serve_forever()
    finally:
        application.service.close()
        application.observer.close()
        server.server_close()
