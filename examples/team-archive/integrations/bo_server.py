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
from bo_stategraph.workflow import LABELS
from integrations.bo_observer import BOObserver
from observer_runtime.behavior_model import check
from observer_runtime.recording_session import Recordings
from observer_runtime.view_preferences import Preferences, PreferenceConflict
from bo_stategraph import bo_export_view
from bo_stategraph.query import bo_machine

CASE_NAMES={
    "archive_snapshot":"正常归档 · 固定版本快照","capacity_one":"1 个名额 · 索引排队",
    "capacity_two":"2 个名额 · 两项实际重叠","loss_and_resume":"审批失效 · 保留结果后手动继续",
    "edit_overlap":"内容改版 · 旧新运行同时可查","cancel_running":"取消本次 · 实际结束后归还名额",
    "revoke_with_alternative":"撤销一条 · 另一条仍有效","move_before_commit":"提交前目录变化",
    "expire_before_commit":"提交时恰好到期","edit_before_commit":"提交前内容改版",
    "secret_content":"内容包含禁用标记","missing_index":"索引缺少标题",
    "concurrent_same_version":"同版本并发 · 只有一条归档","join_pending":"一项未完成 · 不能提交",
    "size_equal":"正文恰好 8192 字节 · 允许归档",
    "size_utf8_over":"UTF-8 正文 8193 字节 · 等待",
    "size_running_restore":"运行中调小上限 · 恢复后手动继续",
    "size_commit_fresh":"检查通过后调小上限 · 提交重新判断",
    "size_resume_over":"仍超限时继续 · 不启动检查",
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
        self.preferences=Preferences(root,"team-archive-example")
        self.case_cache={}
        self.observer.bo_graph.bo_bind_instances(lambda: self.recording_view()["machine"])
        self.frozen=None
        frozen_root=root/"review/v1"
        if (frozen_root/"manifest.json").exists():
            frozen_model=json.loads((frozen_root/"behavior.json").read_text(encoding="utf-8"))
            frozen_manifest=json.loads((frozen_root/"manifest.json").read_text(encoding="utf-8"))
            source_root=frozen_root/"source-snapshot"
            frozen_sources={name:(source_root/name).read_text(encoding="utf-8")
                            for name in frozen_manifest["files"]}
            self.frozen=(frozen_model,frozen_manifest,frozen_sources,source_root)
        self.recordings=Recordings(root/"data/recordings",self.recording_view,sources,scope_setter=self.observer.pins.bo_set_scope,event_source=self.observer.events,
            action_nodes={"run":"archive_request","approve":"issue_approval","revoke":"approval_revoked",
                          "resume":"resume_run","cancel":"cancel_run","size-limit":"set_size_limit",
                          "edit":"content_changed","move":"move_folder"})

    def recording_view(self):
        with self.service.lock:
            return self.graph_view()

    def bo_export_graph(self):
        # Same full model and authoritative configurations as the live graph.
        # UI filters/expansion have no effect on this endpoint.
        return bo_export_view(self.recording_view(), graph=self.observer.bo_graph)

    def cases(self, version="live"):
        path=self.root/("review/v1/observations.json" if version=="v1" else "review/v2/observations.json")
        if path.exists():
            stamp=path.stat().st_mtime_ns
            cached=self.case_cache.get(version)
            if not cached or stamp!=cached[0]:
                self.case_cache[version]=(stamp,json.loads(path.read_text(encoding="utf-8-sig")))
            return self.case_cache[version][1]
        return None

    def version_sources(self, version):
        if version=="live":
            return self.model,self.manifest,self.sources,self.root
        if version=="v1" and self.frozen:
            return self.frozen
        raise ValueError("没有这个已保存版本")

    def graph_view(self, case="live", version="live"):
        snapshot=self.store.snapshot()
        events=self.observer.snapshot()
        historical=False
        model,build,_,source_root=self.version_sources(version)
        payload=self.cases(version)
        if version=="v1" and case=="live":
            case="archive_snapshot"
        selected=None
        if payload and case!="live":
            selected=next((r for r in payload["runs"] if r["case"]==case and r["mode"]=="on"),None)
        if selected:
            snapshot=selected["authority_snapshot"]
            events=selected["events"]
            historical=True
        if version=="v1" and not selected:
            raise ValueError("首版没有保存这个运行场景")
        machine=bo_machine(snapshot,build["build_id"])
        latest=snapshot["runs"][-1] if snapshot["runs"] else None
        document=snapshot["documents"][0]
        basis={"param_version":document["version"],"epoch":snapshot["epoch"],"clock":time.time()}
        if historical and latest:
            basis=latest["qualification"].get("basis",basis)
        bound=check(source_root,model,build)
        if version=="live" and self.args.candidate and bound["status"]=="current":
            bound["status"]="candidate_unverified"
        if historical and payload["build_id"]!=build["build_id"]:
            bound["status"]="stale"
        allowed_cases=["live"]+[r["case"] for r in (payload or {}).get("runs",[]) if r["mode"]=="on" and r["case"] in CASE_NAMES]
        project=next(p for p in snapshot["projects"] if p["id"]==document["project_id"])
        size_parameters={} if version=="v1" else {
            "content_bytes":len(document["content"].encode("utf-8")),
            "limit_bytes":project["archive_limit_bytes"],"limit_revision":project["limit_revision"]}
        return {"model":model,"manifest":build,"binding_status":bound,"events":events,
                "health":self.observer.health() if not historical else {"errors":0,"dropped":0,"scope":"saved events only"},
                "busy":not historical and any(r["phase"] not in ("completed","failed","cancelled","superseded","interrupted") for r in snapshot["runs"]),
                "authority":{"entity":document["id"],"basis":basis,"state":latest["phase"] if latest else "created",
                    "parameters":{"param_version":document["version"],"attempt":latest["id"] if latest else None,
                        "capacity":latest["configuration"]["resources"]["processing_slots"]["capacity"] if latest else 2,
                        **size_parameters},
                    "approvals":snapshot["grants"],"relation":snapshot["assignments"],
                    "effects":snapshot["archives"],"historical":historical,"case_label":CASE_NAMES.get(case,"当前操作")},
                "machine":machine,"instances":self.observer.bo_graph.bo_instances(machine),
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
        elif action=="size-limit":
            return service.set_archive_limit(values["project_id"],values["limit_bytes"])
        else:
            if action not in ("run","approve"):
                raise ValueError("未知操作")
        return {"ok":True}


def serve(root, args, model, manifest, sources):
    application=LocalApplication(root,args,model,manifest,sources)
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):
            pass

        def reply(self,status,body,content_type="application/json; charset=utf-8",download=False):
            raw=json.dumps(body,ensure_ascii=False).encode() if content_type.startswith("application/json") else body
            self.send_response(status)
            self.send_header("Content-Type",content_type)
            self.send_header("Cache-Control","no-store")
            self.send_header("X-Content-Type-Options","nosniff")
            self.send_header("Content-Length",str(len(raw)))
            if download:
                self.send_header("Content-Disposition", 'attachment; filename="stategraph.json"')
            self.end_headers()
            self.wfile.write(raw)

        def do_GET(self):
            parsed=urlparse(self.path)
            params=parse_qs(parsed.query)
            try:
                if parsed.path=="/api/preferences":
                    return self.reply(200,application.preferences.read())
                if parsed.path=="/api/state":
                    return self.reply(200,application.state())
                if parsed.path in ("/api/stategraph", "/api/stategraph/export"):
                    return self.reply(200,application.bo_export_graph(),download=parsed.path.endswith("/export"))
                if parsed.path=="/api/view":
                    return self.reply(200,application.graph_view(params.get("case",["live"])[0],params.get("version",["live"])[0]))
                if parsed.path=="/api/versions":
                    return self.reply(200,{"versions":["live","v1"] if application.frozen else ["live"]})
                if parsed.path=="/api/recordings":
                    return self.reply(200,application.recordings.list())
                if parsed.path.startswith("/api/recordings/"):
                    return self.reply(200,application.recordings.get(parsed.path.rsplit("/",1)[-1]))
                if parsed.path=="/api/source":
                    name=params.get("path",[""])[0]
                    if params.get("recording"):
                        saved=application.recordings.get(params["recording"][0])
                        source_build,version_sources={"build_id":saved["build_id"]},saved["sources"]
                    else:
                        _,source_build,version_sources,_=application.version_sources(params.get("version",["live"])[0])
                    if name not in version_sources:
                        return self.reply(404,{"error":"该源码不在已加载版本中"})
                    return self.reply(200,{"source":version_sources[name],"build_id":source_build["build_id"]})
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
            action,values=None,{}
            try:
                size=int(self.headers.get("Content-Length","0"))
                limit=2*1024*1024 if urlparse(self.path).path=="/api/preferences" else 200000
                if not 0<size<=limit:
                    raise ValueError("请求大小无效")
                values=json.loads(self.rfile.read(size).decode("utf-8"))
                if not isinstance(values,dict):
                    raise ValueError("请求必须是对象")
                action=urlparse(self.path).path.removeprefix("/api/")
                if action=="preferences":
                    return self.reply(200,application.preferences.save(values))
                if action=="recordings/start":
                    return self.reply(200,application.recordings.start(values.get("label",""),values.get("scope")))
                if action=="recordings/stop":
                    return self.reply(200,application.recordings.stop())
                result=application.command(action,values)
                application.recordings.command(action,values,result)
                return self.reply(200,result)
            except PreferenceConflict as error:
                return self.reply(409,{"error":str(error)})
            except (ValueError,KeyError,TypeError) as error:
                if action and action!="preferences" and not action.startswith("recordings/"):
                    application.recordings.command(action,values,error=error)
                return self.reply(400,{"error":str(error)})
    server=ThreadingHTTPServer(("127.0.0.1",args.port),Handler)
    print(json.dumps({"application":f"http://127.0.0.1:{args.port}/",
                      "graph":f"http://127.0.0.1:{args.port}/graph",
                      "build":manifest["build_id"],"candidate":args.candidate}),flush=True)
    try:
        server.serve_forever()
    finally:
        application.recordings.close()
        application.service.close()
        application.observer.close()
        server.server_close()
