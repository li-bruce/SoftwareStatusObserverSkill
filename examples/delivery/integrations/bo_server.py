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
        self.store=Store(str(ROOT/'scratch/live.sqlite'))
        self.bo_adapter=BOAdapter(MODEL,LOADED['build_id'])
        self.app=Delivery(self.store,Events(self.bo_adapter),checker=self.demo_check)
        self.lock=threading.Lock();self.active_versions=set();self.error=''

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
        return {'model':MODEL,'manifest':LOADED,'events':events,
                'health':self.bo_adapter.bo_pins.health(),'binding_status':check(ROOT,MODEL,LOADED),
                'machine':{'current':job['state'],'journal':job['journal'],'configurations':job['executions']},
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
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*_):pass
        def send(self,data,status=200,kind='application/json; charset=utf-8'):
            if not isinstance(data,bytes):data=json.dumps(data,ensure_ascii=False).encode()
            self.send_response(status);self.send_header('Content-Type',kind);self.send_header('Cache-Control','no-store')
            self.end_headers();self.wfile.write(data)
        def do_GET(self):
            request=urlparse(self.path);query=parse_qs(request.query)
            version=query.get('version',['live'])[0]
            histories={p.stem:p for p in (ROOT/'history').glob('*.json')}
            try:
                historical=json.loads(histories[version].read_text(encoding='utf-8')) if version in histories else None
                if request.path=='/api/versions':return self.send({'versions':['live',*sorted(histories)]})
                if request.path=='/api/view':
                    if version!='live' and not historical:raise ValueError('unknown version')
                    value=session.view() if not historical else historical['views'][query.get('case',['normal'])[0]]
                    return self.send({**value,'layout_id':'delivery-example','available_cases':list(historical['views']) if historical else ['live'],
                                      'case_names':{k:v[0] for k,v in SCENARIOS.items()},'case_label':value.get('case_label','当前程序')})
                if request.path=='/api/source':
                    sources=historical['sources'] if historical else SOURCES
                    manifest=next(iter(historical['views'].values()))['manifest'] if historical else LOADED
                    return self.send({'source':sources[query['path'][0]],'build_id':manifest['build_id']})
                if request.path=='/control':
                    return self.send((ROOT/'integrations/control.html').read_bytes(),kind='text/html; charset=utf-8')
                names={'/':'index.html','/viewer.css':'viewer.css','/viewer.js':'viewer.js','/graph-core.js':'graph-core.js','/layout.js':'layout.js',
                       '/pixi.min.js':'pixi.min.js','/elk.bundled.js':'elk.bundled.js','/elk-worker.min.js':'elk-worker.min.js'}
                filename=names[request.path]
                kind='text/html' if filename.endswith('.html') else 'text/css' if filename.endswith('.css') else 'text/javascript'
                return self.send((ROOT/'observer_generated/static'/filename).read_bytes(),kind=kind+'; charset=utf-8')
            except (KeyError,ValueError) as exc:self.send({'error':str(exc)},404)
        def do_POST(self):
            if self.path!='/api/command':return self.send({'error':'unknown path'},404)
            origin=self.headers.get('Origin')
            if origin and origin!='http://'+self.headers.get('Host',''):return self.send({'error':'origin'},403)
            try:
                length=int(self.headers.get('Content-Length',0))
                if not 0<length<=16384:raise ValueError('invalid body size')
                data=json.loads(self.rfile.read(length));action=data.pop('action')
                if action in ('prepare','execute'):
                    with session.lock:
                        version=session.store.snapshot()['param_version']
                        if version in session.active_versions:return self.send({'error':'busy'},409)
                        session.active_versions.add(version);session.error=''
                    threading.Thread(target=session.work,args=(action,version),daemon=True).start()
                elif action=='commit':session.app.commit()
                else:session.app.command(action,**data)
                self.send({'ok':True})
            except Exception as exc:self.send({'error':str(exc)},400)
    server=ThreadingHTTPServer(('127.0.0.1',port),Handler)
    print(json.dumps({'url':f'http://127.0.0.1:{server.server_port}','build_id':LOADED['build_id']}),flush=True)
    server.serve_forever()


if __name__=='__main__':serve(int(sys.argv[1]) if len(sys.argv)>1 else 8797)
