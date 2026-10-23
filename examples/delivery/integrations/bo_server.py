"""Optional business-observer local UI; all commands go through Delivery."""
import json
from pathlib import Path
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from observer_generated.runtime.behavior_model import capture,check
from observer_generated.runtime.recording_session import Recordings
from observer_generated.runtime.view_preferences import Preferences, PreferenceConflict
from observer_generated.runtime.bo_web import BOWeb
from bo_stategraph import bo_export_view
from bo_stategraph.query import bo_machine
MODEL=json.loads((ROOT/'observer_generated/behavior.json').read_text(encoding='utf-8'))
LOADED=capture(ROOT,MODEL)
SOURCES={p:(ROOT/p).read_text(encoding='utf-8-sig') for p in MODEL['source_files']}
from integrations.bo_adapter import BOAdapter
from app.service import Delivery
from app.store import Store
from app.ports import Events
from app.checks import run_checks
from integrations.bo_scenarios import SCENARIOS


class Session:
    def __init__(self):
        (ROOT/'scratch').mkdir(exist_ok=True)
        self.preferences=Preferences(ROOT,'delivery-example')
        self.store=Store(str(ROOT/'scratch/live.sqlite'))
        self.bo_adapter=BOAdapter(MODEL,LOADED['build_id'])
        self.app=Delivery(self.store,Events(self.bo_adapter),checker=self.demo_check,execution_version=LOADED['build_id'])
        self.lock=threading.Lock();self.active_versions=set();self.error=''
        self.bo_adapter.bo_graph.bo_bind_instances(lambda: self.view()["machine"])
        self.recordings=Recordings(ROOT/'scratch/recordings',self.view,SOURCES,scope_setter=self.bo_adapter.bo_pins.bo_set_scope,event_source=self.bo_adapter.bo_events,
            action_nodes={'prepare':'read','execute':'execute','commit':'commit','grant':'grant',
                          'revoke':'grant','edit':'change','cancel':'change'})

    @property
    def busy(self):
        with self.lock:return bool(self.active_versions)

    def demo_check(self,content,**kwargs):
        time.sleep(.6)  # Explicit demo pacing to make the checking phase observable.
        return run_checks(content,task_hook=lambda task:time.sleep(.6),**kwargs)

    def view(self):
        events=self.bo_adapter.snapshot()
        # Capture completion and its business snapshot together. Flushing events
        # after reading the job could return an old "checking" state with busy=False.
        with self.lock:
            job=self.store.snapshot()
            busy=bool(self.active_versions)
        machine=bo_machine(job)
        return {'model':MODEL,'manifest':LOADED,'events':events,
                'health':self.bo_adapter.health(),'binding_status':check(ROOT,MODEL,LOADED),
                'machine':machine,'instances':self.bo_adapter.bo_graph.bo_instances(machine),
                'authority':{'basis':{k:job[k] for k in ('param_version','epoch','clock')},
                             'parameters':job,'effects':job['effects'],'entity':'delivery:1','state':job['state']},
                'busy':busy,'error':self.error,'historical':False}

    def work(self,action,version):
        try:getattr(self.app,action)(expected_version=version)
        except Exception as exc:self.error=str(exc)
        finally:
            with self.lock:self.active_versions.discard(version)


def serve(port=8797):
    session=Session()
    bo_web=BOWeb(ROOT,assets=ROOT/'observer_generated/static',graph_routes=('/','/graph','/graph/'))
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*_):pass
        def send(self,data,status=200,kind='application/json; charset=utf-8',download=False):
            if not isinstance(data,bytes):data=json.dumps(data,ensure_ascii=False).encode()
            self.send_response(status);self.send_header('Content-Type',kind);self.send_header('Cache-Control','no-store')
            if download:self.send_header('Content-Disposition','attachment; filename="stategraph.json"')
            self.end_headers();self.wfile.write(data)
        def do_GET(self):
            request=urlparse(self.path);query=parse_qs(request.query)
            version=query.get('version',['live'])[0]
            histories={p.stem:p for p in (ROOT/'history').glob('*.json')}
            try:
                if not bo_web.allowed(request.path):return self.send({'error':"Debug Web is disabled",'code':'bo_web_disabled'},404)
                bo_value=bo_web.get(self.path)
                if bo_value is not None:return self.send(bo_value)
                if request.path=='/api/app-state':return self.send(session.store.snapshot())
                if request.path=='/api/preferences':return self.send(session.preferences.read())
                if request.path in ('/api/stategraph','/api/stategraph/export'):
                    return self.send(bo_export_view(session.view(),graph=session.bo_adapter.bo_graph),download=request.path.endswith('/export'))
                historical=json.loads(histories[version].read_text(encoding='utf-8')) if version in histories else None
                if request.path=='/api/versions':return self.send({'versions':['live',*sorted(histories)]})
                if request.path=='/api/recordings':return self.send(session.recordings.list())
                if request.path.startswith('/api/recordings/'):
                    return self.send(session.recordings.get(request.path.rsplit('/',1)[-1]))
                if request.path=='/api/view':
                    if version!='live' and not historical:raise ValueError('unknown version')
                    value=session.view() if not historical else historical['views'][query.get('case',['normal'])[0]]
                    return self.send({**value,'layout_id':'delivery-example','available_cases':list(historical['views']) if historical else ['live'],
                                      'case_names':{k:v[0] for k,v in SCENARIOS.items()},'case_label':value.get('case_label',"Current application")})
                if request.path=='/api/source':
                    sources=historical['sources'] if historical else SOURCES
                    manifest=next(iter(historical['views'].values()))['manifest'] if historical else LOADED
                    if query.get('recording'):
                        saved=session.recordings.get(query['recording'][0])
                        sources,manifest=saved['sources'],{'build_id':saved['build_id']}
                    return self.send({'source':sources[query['path'][0]],'build_id':manifest['build_id']})
                if request.path=='/control':
                    return self.send(bo_web.entry_html((ROOT/'integrations/control.html').read_bytes()),kind='text/html; charset=utf-8')
                names={'/':'index.html','/graph':'index.html','/viewer.css':'viewer.css','/viewer.js':'viewer.js','/graph-core.js':'graph-core.js','/layout.js':'layout.js',
                       '/preferences.js':'preferences.js','/polling.js':'polling.js','/renderer.js':'renderer.js','/analysis.js':'analysis.js','/recording.js':'recording.js','/glyphs.js':'glyphs.js','/replay-steps.js':'replay-steps.js','/runtime-frames.js':'runtime-frames.js','/conversation.js':'conversation.js',
                       '/pixi.min.js':'pixi.min.js','/elk.bundled.js':'elk.bundled.js','/elk-worker.min.js':'elk-worker.min.js'}
                filename=names[request.path]
                kind='text/html' if filename.endswith('.html') else 'text/css' if filename.endswith('.css') else 'text/javascript'
                return self.send((ROOT/'observer_generated/static'/filename).read_bytes(),kind=kind+'; charset=utf-8')
            except (KeyError,ValueError) as exc:self.send({'error':str(exc)},404)
        def do_POST(self):
            if not bo_web.allowed(urlparse(self.path).path):return self.send({'error':"Debug Web is disabled",'code':'bo_web_disabled'},404)
            if urlparse(self.path).path.startswith('/api/design'):return self.send({'error':"The graph is read-only; request changes in the development conversation"},405)
            if self.path not in ('/api/command','/api/preferences','/api/recordings/start','/api/recordings/stop'):
                return self.send({'error':'unknown path'},404)
            origin=self.headers.get('Origin')
            if origin and origin!='http://'+self.headers.get('Host',''):return self.send({'error':'origin'},403)
            action,data=None,{}
            try:
                length=int(self.headers.get('Content-Length',0))
                if not 0<length<=(2*1024*1024 if self.path=='/api/preferences' else 16384):raise ValueError('invalid body size')
                data=json.loads(self.rfile.read(length))
                if not isinstance(data,dict):raise ValueError('request must be an object')
                if self.path=='/api/preferences':return self.send(session.preferences.save(data))
                if self.path=='/api/recordings/start':return self.send(session.recordings.start(data.get('label',''),data.get('scope')))
                if self.path=='/api/recordings/stop':return self.send(session.recordings.stop())
                action=data.pop('action')
                if action in ('prepare','execute'):
                    with session.lock:
                        version=session.store.snapshot()['param_version']
                        if version in session.active_versions:return self.send({'error':'busy'},409)
                        session.active_versions.add(version);session.error=''
                    threading.Thread(target=session.work,args=(action,version),daemon=True).start()
                elif action=='commit':session.app.commit()
                else:session.app.command(action,**data)
                session.recordings.command(action,data,{'ok':True})
                self.send({'ok':True})
            except PreferenceConflict as exc:
                self.send({"error":str(exc)},409)
            except Exception as exc:
                if action:session.recordings.command(action,data,error=exc)
                self.send({'error':str(exc)},400)
    server=ThreadingHTTPServer(('127.0.0.1',port),Handler)
    print(json.dumps({'url':f'http://127.0.0.1:{server.server_port}','build_id':LOADED['build_id']}),flush=True)
    try:server.serve_forever()
    finally:
        session.recordings.close()
        session.bo_adapter.bo_pins.close()
        server.server_close()


if __name__=='__main__':serve(int(sys.argv[1]) if len(sys.argv)>1 else 8797)
