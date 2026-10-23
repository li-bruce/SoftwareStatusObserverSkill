"""Local runnable web application. Server-side cookie identities enforce roles."""
from contextlib import asynccontextmanager
import json
import mimetypes
import os
from pathlib import Path
import re
import secrets
import time
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response
from app.service import DomainError, ReviewService
from app.storage import Store
from bo_stategraph.query import bo_machine
from observer_runtime.behavior_model import capture, check
from observer_runtime.bo_web import BOWeb
from observer_runtime.recording_session import Recordings
from observer_runtime.view_preferences import Preferences, PreferenceConflict
from .bo_observer import BOObserver

ROOT=Path(__file__).resolve().parents[1]


def create_app(directory=None, probe_mode='on'):
    model=json.loads((ROOT/'behavior.json').read_text(encoding='utf-8'))
    manifest=capture(ROOT,model)
    store=Store(directory or os.getenv('UPLOAD_REVIEW_DATA',str(ROOT/'data')))
    observer=BOObserver(ROOT,model,manifest['build_id'],mode=probe_mode,event_dir=store.directory)
    service=ReviewService(store,manifest['build_id'],observer.trace,int(os.getenv('MAX_UPLOAD_BYTES',20*1024*1024)))
    web=BOWeb(ROOT,assets=ROOT/'static/graph')
    prefs=Preferences(ROOT,'upload-review-v1')

    def bo_view():
        events=observer.snapshot()
        rows=store.snapshot()
        machine=bo_machine(rows,manifest['build_id'])
        current=rows[-1] if rows else None
        return {'model':model,'manifest':manifest,'layout_id':'upload-review-v1',
            'binding_status':check(ROOT,model,manifest),'events':events,'machine':machine,
            'authority':{'entity':current['id'] if current else None,
                'state':current['status'] if current else None,
                'basis':{'param_version':1,'epoch':current['revision'] if current else 1},
                'parameters':{'size':current['size'] if current else None,'param_version':1},
                'effects':[]},'health':observer.health(),'busy':False,'historical':False,'available_cases':['live']}

    observer.graph.bo_bind_instances(lambda:bo_machine(store.snapshot(),manifest['build_id']))
    sources={name:(ROOT/name).read_text(encoding='utf-8') for name in manifest['files']}
    recordings=Recordings(store.directory/'recordings',bo_view,sources,event_source=observer.events,scope_setter=observer.pins.bo_set_scope)

    @asynccontextmanager
    async def lifespan(_):
        yield
        recordings.close()
        observer.close()

    app=FastAPI(title='文件上传与审核',lifespan=lifespan,docs_url=None,redoc_url=None)
    app.state.service,app.state.store=service,store
    app.state.observer,app.state.view,app.state.recordings=observer,bo_view,recordings

    def user(request):
        token=request.cookies.get('upload_review_session','')
        with store.connection() as db:
            row=db.execute('SELECT u.id,u.name,u.role FROM users u JOIN sessions s ON s.user_id=u.id WHERE s.token=? AND s.expires>?',
                (token,time.time())).fetchone()
        if not row:
            raise DomainError(401,'请先登录')
        return dict(row)

    @app.middleware('http')
    async def boundaries(request,call_next):
        if request.method in ('POST','PUT','PATCH','DELETE'):
            origin=request.headers.get('origin')
            if origin and origin!=str(request.base_url).rstrip('/'):
                return JSONResponse({'error':'请求来源无效'},status_code=403)
        if not web.allowed(request.url.path):
            return JSONResponse({'code':'bo_web_disabled','error':'调试图已关闭'},status_code=404)
        response=await call_next(request)
        try:
            endpoint=request.scope.get('endpoint')
            if endpoint and not web.is_observer_request(request.url.path):
                arguments={**dict(request.query_params),**request.path_params}
                observer.bo_http(endpoint.__name__,request.method,request.url.path,arguments,response.status_code)
        except Exception:
            pass
        response.headers['X-Content-Type-Options']='nosniff'
        response.headers['Referrer-Policy']='same-origin'
        response.headers['Cache-Control']='no-store'
        return response

    @app.exception_handler(DomainError)
    async def domain_error(request,exc):
        return JSONResponse({'error':str(exc)},status_code=exc.status)

    @app.get('/')
    @app.get('/control')
    def index():
        return HTMLResponse(web.entry_html((ROOT/'static/app.html').read_bytes()))

    @app.get('/favicon.ico')
    def favicon():
        return Response(status_code=204)

    @app.get('/health')
    def health():
        return {'status':'ok','build_id':manifest['build_id']}

    @app.get('/api/session')
    def session(request: Request):
        return {'user':user(request),'max_bytes':service.max_bytes}

    @app.post('/api/login')
    async def login(request: Request):
        raw=await request.body()
        if len(raw)>4096:
            raise DomainError(400,'登录请求无效')
        try:
            values=json.loads(raw)
            username,password=values['username'],values['password']
            if not isinstance(username,str) or not isinstance(password,str):
                raise ValueError()
        except (ValueError,KeyError,TypeError):
            raise DomainError(400,'请输入账号和密码')
        actor=store.authenticate(username,password)
        if not actor:
            raise DomainError(401,'账号或密码不正确')
        token=secrets.token_urlsafe(32)
        with store.connection(write=True) as db:
            db.execute('DELETE FROM sessions WHERE expires<?',(time.time(),))
            db.execute('INSERT INTO sessions VALUES(?,?,?)',(token,actor['id'],time.time()+12*3600))
        response=JSONResponse({'user':actor,'max_bytes':service.max_bytes})
        response.set_cookie('upload_review_session',token,httponly=True,samesite='strict',max_age=12*3600)
        return response

    @app.post('/api/logout')
    def logout(request: Request):
        with store.connection(write=True) as db:
            db.execute('DELETE FROM sessions WHERE token=?',(request.cookies.get('upload_review_session',''),))
        response=JSONResponse({'ok':True})
        response.delete_cookie('upload_review_session')
        return response

    @app.get('/api/files')
    def files(request: Request):
        return {'files':service.list_files(user(request))}

    @app.post('/api/files')
    async def upload(request: Request,filename: str='',note: str=''):
        actor=user(request)
        if actor['role']!='uploader':
            raise DomainError(403,'只有上传者可以提交文件')
        chunks=[]
        size=0
        async for chunk in request.stream():
            size+=len(chunk)
            if size>service.max_bytes:
                raise DomainError(413,'文件超过当前上传大小上限')
            chunks.append(chunk)
        return service.upload(actor,filename,b''.join(chunks),note)

    @app.get('/api/files/{ident}/download')
    def download(ident: str,request: Request):
        row=service.detail(user(request),ident)
        path=store.files/row['id']
        if not path.is_file():
            raise DomainError(404,'暂存文件缺失，请联系维护者')
        return FileResponse(path,filename=row['filename'],media_type='application/octet-stream')

    @app.post('/api/files/{ident}/review')
    async def review(ident: str,request: Request):
        raw=await request.body()
        if len(raw)>8192:
            raise DomainError(400,'审核请求过长')
        try:
            value=json.loads(raw)
            decision,note=value['decision'],value.get('note','')
            if not isinstance(decision,str) or not isinstance(note,str):
                raise ValueError()
        except (ValueError,KeyError,TypeError):
            raise DomainError(400,'审核请求格式无效')
        return service.review(user(request),ident,decision,note)

    @app.get('/api/messages')
    def messages(request: Request):
        return {'messages':service.messages(user(request))}

    @app.post('/api/messages/{ident}/read')
    def read_message(ident: int,request: Request):
        service.read_message(user(request),ident)
        return {'ok':True}

    @app.get('/api/design')
    def design():
        return web.get('/api/design')

    @app.get('/api/view')
    def graph_view():
        return bo_view()

    @app.get('/api/stategraph')
    def instances():
        return {'model':observer.graph.bo_structure(),'instances':observer.graph.bo_instances()}

    @app.get('/api/stategraph/export')
    def export():
        current=bo_view()
        return observer.graph.bo_export(runtime={'machine':current['machine'],'events':current['events']},binding=current['binding_status'])

    @app.get('/api/source')
    def source(node: str | None=None,path: str | None=None,recording: str | None=None):
        if recording:
            value=recordings.get(recording)
            name=path or value.get('context',{}).get('manifest',{}).get('bindings',{}).get(node,{}).get('path')
            if name not in value['sources']:
                raise DomainError(404,'该源码不在已记录版本中')
            return {'source':value['sources'][name],'build_id':value['build_id']}
        if path:
            if path not in sources:
                raise DomainError(404,'该源码不在已加载版本中')
            return {'source':sources[path],'build_id':manifest['build_id']}
        binding=manifest['bindings'].get(node)
        if not binding:
            raise DomainError(404,'该节点没有绑定源码')
        return {'node':node,**binding,'source':binding['snippet'],'build_id':manifest['build_id'],'loaded':True}

    @app.get('/api/preferences')
    def preferences():
        return prefs.read()

    @app.post('/api/preferences')
    async def save_preferences(request: Request):
        value=await request.json()
        try:
            return prefs.save(value)
        except PreferenceConflict as exc:
            raise DomainError(409,str(exc))
        except ValueError as exc:
            raise DomainError(400,str(exc))

    @app.get('/api/recordings')
    def list_recordings():
        return recordings.list()

    @app.get('/api/recordings/{ident}')
    def get_recording(ident: str):
        return recordings.get(ident)

    @app.post('/api/recordings/start')
    async def start_recording(request: Request):
        value=await request.json()
        try:
            return recordings.start(value.get('label',''),value.get('scope'))
        except ValueError as exc:
            raise DomainError(400,str(exc)) from exc

    @app.post('/api/recordings/stop')
    def stop_recording():
        return recordings.stop()

    @app.get('/graph')
    def graph():
        return FileResponse(ROOT/'static/graph/index.html')

    @app.get('/{name}')
    def asset(name: str):
        if not re.fullmatch(r'[A-Za-z0-9_.-]+',name) or name.startswith('.'):
            raise DomainError(404,'页面不存在')
        path=ROOT/'static'/name if name in ('app.js','app.css') else ROOT/'static/graph'/name
        if not path.is_file():
            raise DomainError(404,'页面不存在')
        return FileResponse(path,media_type=mimetypes.guess_type(name)[0])

    return app
