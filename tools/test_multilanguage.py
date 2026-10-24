"""Cross-language contract, scanner, native execution and real collector regression tests."""
from copy import deepcopy
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
from urllib.request import Request,urlopen
from urllib.error import HTTPError

ROOT=Path(__file__).resolve().parents[1]
SCRIPTS=ROOT/'skills/vibelens/scripts'
sys.path.insert(0,str(SCRIPTS))
from code_structure import scan,enrich
from bo_sync import source_inventory
from behavior_model import capture,digest
from bo_contracts import validate_chart
from bo_observer.protocol import validate_project,validate_event
from bo_observer.development import questions,reconciliation_errors
from bo_observer.service import GraphSession,make_server
from bo_observer.adapters.python.bo_executor import BOExecutor
from bo_observer.adapters.python.bo_probe import BOProbe

JS=SCRIPTS/'bo_observer/adapters/javascript/bo_runtime.mjs'


def project_fixture(root):
    (root/'worker.py').write_text('def advance(state: str, event: str, slots: int):\n    return "running" if slots > 0 else "waiting"\n',encoding='utf-8')
    (root/'intent.json').write_text(json.dumps({'project_id':'fixture','requirements':[{'id':'R1','text':'Start with capacity, otherwise wait.','status':'confirmed','source':'synthetic scenario'}]}))
    machine={'engine':'bo.fsm','version':'1','state_type':'enum','states':['pending','waiting','running','done'],'values':['pending','waiting','running','done'],'initial':'pending',
             'transitions':[{'source':'pending','dest':'running','trigger':'start','conditions':'available'},{'source':'pending','dest':'waiting','trigger':'start','unless':'available'},{'source':'waiting','dest':'running','trigger':'resume','conditions':'available'},{'source':'running','dest':'done','trigger':'finish'}],
             'events':{n:{'payload':{}} for n in ('start','resume','finish')},'context':{'slots':{'type':'integer','min':0}},'guards':{'available':'at least one slot'}}
    node={'id':'advance','kind':'action','layer':'business','label':"Process task",'summary':"Actual calls and results",'source':{'path':'worker.py','symbol':'advance'},'capture':{'in':{'state':'string','event':'string','slots':'number'},'out':{'state':'string'}},'requirements':['R1']}
    model={'schema_version':3,'revision':'1','project_id':'fixture','intent':'intent.json','source_files':['worker.py'],'nodes':[node,{'id':'done','kind':'state','label':"Complete",'summary':"Already completed",'state':'done'}],
           'edges':[{'id':'finish','from':'advance','to':'done','type':'flow','label':"Complete",'evidence':'confirmed definition'}], 'overview':[{'node':'advance'}],'scope':{'unknowns':[]},'machine':machine}
    model['nodes']=[node]+[{'id':s,'kind':'state','layer':'state','value':s,'label':s,'summary':'Declared state'} for s in machine['values']]
    project={'protocol':'bo-project/v1','project_id':'fixture','selection':{'mode':'drive','source':'user','answer':"Develop from the graph",'locator':'simulated dialogue 1'},'model':model}
    (root/'bo_stategraph').mkdir(exist_ok=True)
    (root/'bo_stategraph/project.json').write_text(json.dumps(project),encoding='utf-8')
    return project


class MultiLanguageTests(unittest.TestCase):
    def setUp(self):
        (ROOT/'.validation').mkdir(exist_ok=True)
        self.temp=tempfile.TemporaryDirectory(dir=ROOT/'.validation');self.root=Path(self.temp.name).absolute()
        self.project=project_fixture(self.root)
    def tearDown(self):self.temp.cleanup()
    def node(self,code,data=None):
        result=subprocess.run(['node','--input-type=module','-e',code],input=json.dumps(data or {}),capture_output=True,text=True,encoding='utf-8',timeout=30)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        return json.loads(result.stdout)

    def test_source_inventory_includes_python_node_react_vue_and_unsupported(self):
        for name,code in {'job.ts':'export const start=(value:number)=>value;','Panel.tsx':'export function Panel(){return <button/>}','Panel.vue':'<script setup>function start(){return 1}</script><template><button @click="start">Go</button></template>','missing.go':'package main'}.items(): (self.root/name).write_text(code)
        inventory=source_inventory(self.root,{'source_scope':{'roots':['.']}})
        self.assertTrue({'worker.py','job.ts','Panel.tsx','Panel.vue','missing.go'}<=set(inventory['files']))
        index=scan(self.root,inventory['files'])
        self.assertEqual([e['path'] for e in index['errors']],['missing.go'])
        self.assertIn('Panel.vue::start',index['symbols']);self.assertIn('Panel.vue::<template>',index['symbols'])
        self.assertTrue(any(e['from']=='Panel.vue::<template>' and e['to']=='Panel.vue::start' for e in index['edges']))

    def test_javascript_import_call_and_arrow_handler_bindings(self):
        (self.root/'lib.ts').write_text('export const save=(name:string)=>name;')
        (self.root/'api.ts').write_text('import {save as persist} from "./lib.js"; export function create(name:string){return persist(name)}; app.post("/create",create);')
        index=scan(self.root,['lib.ts','api.ts'])
        self.assertEqual(index['errors'],[])
        self.assertTrue(any(e['from']=='api.ts::create' and e['to']=='lib.ts::save' for e in index['edges']))
        self.assertEqual(index['symbols']['api.ts::create']['entrypoints'],['app.post("/create")'])

    def test_react_handlers_and_class_methods_are_explicit_symbols(self):
        (self.root/'app.tsx').write_text('export function Panel(){const click=()=>1;return <button onClick={click}/>}; class Job { start(x:number){return this.finish(x)} finish(x:number){return x} }')
        index=scan(self.root,['app.tsx'])
        self.assertEqual(index['errors'],[])
        self.assertIn('app.tsx::Panel.click',index['symbols'])
        self.assertTrue(any(e['to']=='app.tsx::Job.finish' for e in index['edges']))

    def test_parser_errors_and_excluded_frontend_implementation_cannot_disappear(self):
        (self.root/'secret.ts').write_text('export function login(password:string){return password.length>0}')
        inventory=source_inventory(self.root,{'source_scope':{'roots':['.'],'exclude':{'secret.ts':'not in original business diagram'}}})
        self.assertIn('secret.ts',inventory['excluded_implementations'])
        (self.root/'broken.ts').write_text('export function (')
        self.assertTrue(scan(self.root,['broken.ts'])['errors'])

    def test_capture_resolves_ts_symbols_and_updates_on_signature_change(self):
        (self.root/'worker.ts').write_text('export function advance(state:string,event:string,slots:number){return state}')
        model=deepcopy(self.project['model']);model['source_files']=['worker.ts'];model['nodes'][0]['source']['path']='worker.ts'
        before=capture(self.root,model)
        (self.root/'worker.ts').write_text('export function advance(state:string,event:string,slots:number,actor:string){return state}')
        after=capture(self.root,model)
        self.assertNotEqual(before['build_id'],after['build_id']);self.assertIn('actor',after['bindings']['advance']['signature'])

    def test_incremental_parse_reuses_unchanged_and_invalidates_changed_source(self):
        first=scan(self.root,['worker.py']);second=scan(self.root,['worker.py'],first)
        self.assertEqual(second['incremental']['reused'],['worker.py'])
        (self.root/'worker.py').write_text('def advance(state, event, slots, actor): return actor')
        self.assertEqual(scan(self.root,['worker.py'],second)['incremental']['parsed'],['worker.py'])

    def test_mode_choice_is_required_for_both_modes(self):
        for mode in ('drive','observe'):
            p=deepcopy(self.project);p['selection']['mode']=mode;validate_project(p)
            p['selection']['source']='default'
            with self.assertRaises(ValueError):validate_project(p)
        self.assertEqual(questions({'model':{}},None)['user'][0]['id'],'development-mode')

    def test_tool_identity_preserves_code_and_schema_but_normalizes_install_metadata(self):
        from sync_config import tool_fingerprints
        original=self.root/'canonical';installed=self.root/'installed'
        for folder in (original,installed):
            folder.mkdir();(folder/'worker.py').write_text('answer = 1\n')
            (folder/'schema.json').write_text('{"type":"integer"}')
        (installed/'origin.json').write_text('{"release":"test-copy"}')
        self.assertEqual(tool_fingerprints(self.root,{},original),tool_fingerprints(self.root,{},installed))
        (installed/'schema.json').write_text('{"type":"string"}')
        self.assertNotEqual(tool_fingerprints(self.root,{},original),tool_fingerprints(self.root,{},installed))

    def test_malformed_engine_graph_and_json_types_are_rejected(self):
        for mutate in (lambda p:p['model']['edges'][0].update(to='missing'),lambda p:p['model']['machine'].update(version='2'),lambda p:p.update(unexpected=True),lambda p:p['model']['machine']['context'].update(slots={'type':'bogus'})):
            p=deepcopy(self.project);mutate(p)
            with self.assertRaises((ValueError,KeyError)):validate_project(p)

    def test_native_python_and_javascript_execution_agree(self):
        machine=self.project['model']['machine'];py=BOExecutor(machine,{'available':lambda ctx,payload:ctx['slots']>0})
        state='pending';expected=[]
        for event,slots in [('start',0),('resume',1),('finish',1)]:
            result=py.step(state,event,{'slots':slots});state=result['state'];expected.append(result)
        actual=self.node(f"import {{BOExecutor}} from {json.dumps(JS.as_uri())};import fs from 'node:fs';const m=JSON.parse(fs.readFileSync(0,'utf8'));const e=new BOExecutor(m,{{available:c=>c.slots>0}});let state='pending';console.log(JSON.stringify([['start',0],['resume',1],['finish',1]].map(([event,slots])=>{{const r=e.step(state,event,{{slots}});state=r.state;return r}})));",machine)
        self.assertEqual(actual,expected)

    def test_native_executor_does_not_treat_truthy_or_async_guards_as_boolean(self):
        with self.assertRaises(ValueError):BOExecutor(self.project['model']['machine'],{'available':lambda c,p:1}).step('pending','start',{'slots':1})
        result=self.node(f"import {{BOExecutor}} from {json.dumps(JS.as_uri())};import fs from 'node:fs';const m=JSON.parse(fs.readFileSync(0,'utf8'));let rejected=0;for(const guard of [()=>1,async()=>true]){{try{{new BOExecutor(m,{{available:guard}}).step('pending','start',{{slots:1}})}}catch{{rejected++}}}}console.log(JSON.stringify(rejected));",self.project['model']['machine'])
        self.assertEqual(result,2)

    def test_hierarchy_is_preserved_but_flat_native_driver_rejects_it(self):
        machine=deepcopy(self.project['model']['machine']);machine['states'][0]={'name':'pending','children':['one'],'initial':'one'}
        with self.assertRaises(ValueError):BOExecutor(machine,{'available':lambda c,p:True})

    def test_business_and_implementation_questions_are_routed_separately(self):
        index=scan(self.root,['worker.py']);index['unresolved']=[{'from':'worker.py::advance','line':2,'column':4,'expression':'callback'}]
        p=deepcopy(self.project);p['model']['implementation']={'features':[{'sources':['worker.py::advance']} ]}
        result=questions(p,index,{'decisions':[{'id':'who','status':'open','question':"Who may start?",'affects':['advance']}]})
        self.assertEqual([q['id'] for q in result['user']],['who']);self.assertEqual(result['coding'][0]['audience'],'coding')
        self.assertTrue(reconciliation_errors({'schema':'bo-reconciliation/v1','source_id':'stale','answers':[]},index,p['model']))

    def test_design_focus_accepts_native_project_envelope(self):
        from bo_design import BODesign
        discovery=json.loads((SCRIPTS.parent/'assets/discovery.example.json').read_text(encoding='utf-8'))
        (self.root/'discovery.json').write_text(json.dumps(discovery),encoding='utf-8')
        (self.root/'sync.json').write_text(json.dumps({'model':'bo_stategraph/project.json','discovery':'discovery.json'}),encoding='utf-8')
        result=BODesign(self.root).focus(['advance'],'Inspect implemented operation')
        self.assertEqual(result['nodes'],['advance'])
        self.assertFalse(result['stale'])

    def test_chained_calls_have_distinct_questions_and_require_each_answer(self):
        (self.root/'worker.py').write_text('def advance(db):\n    return db.execute("SELECT 1").fetchone()\n',encoding='utf-8')
        index=scan(self.root,['worker.py'])
        model=deepcopy(self.project['model'])
        model['implementation']={'features':[{'sources':['worker.py::advance'],'cases':[{'case':'read'}]}]}
        pending=questions({'model':model},index)['coding']
        self.assertEqual(len(pending),2)
        self.assertEqual(len({q['id'] for q in pending}),2)
        record={'schema':'bo-reconciliation/v1','source_id':digest({p:u['file_hash'] for p,u in index['units'].items()}),
                'answers':[{'id':q['id'],'status':'external','dependency':'sqlite3','reason':'Actual cursor/read boundary'} for q in pending]}
        self.assertEqual(reconciliation_errors(record,index,model),[])
        record['answers'].pop()
        self.assertTrue(any(isinstance(e,dict) and 'unanswered_implementation' in e for e in reconciliation_errors(record,index,model)))

    def test_dialogue_choice_confirmation_and_coding_evidence_survive_iteration(self):
        (self.root/'worker.py').write_text('def advance(state, callback):\n    return callback(state)\ndef complete(state):\n    return "done"\n',encoding='utf-8')
        index=scan(self.root,['worker.py'])
        p=deepcopy(self.project);p.pop('selection')
        p['model']['implementation']={'features':[{'sources':['worker.py::advance'],'cases':[{'case':'complete_job'}]}]}
        discovery={'decisions':[{'id':'wait','status':'open','question':"With no available slot, should execution wait or fail immediately?",'affects':['advance']}]}
        first=questions(p,index,discovery)
        self.assertEqual([q['id'] for q in first['user']],['development-mode','wait'])
        p['selection']={'mode':'observe','source':'user','answer':"Observe only; retain application logic",'locator':'synthetic dialogue / user 2'}
        discovery['decisions'][0].update(status='confirmed',answer="Wait, then continue when a slot is available")
        second=questions(p,index,discovery)
        self.assertEqual(second['user'],[])
        self.assertEqual(len(second['coding']),1)
        answer={'schema':'bo-reconciliation/v1','source_id':digest({p:u['file_hash'] for p,u in index['units'].items()}),
                'answers':[{'id':second['coding'][0]['id'],'status':'bound','target':'worker.py::complete','case':'complete_job','reason':'Coding passes complete as the callback; complete_job must verify its actual target and result.'}]}
        self.assertEqual(reconciliation_errors(answer,index,p['model']),[])
        invalid=deepcopy(answer);invalid['answers'][0]['target']='worker.py::missing'
        self.assertTrue(reconciliation_errors(invalid,index,p['model']))
        (self.root/'worker.py').write_text('def advance(state, callback):\n    return callback(state)\ndef complete(state):\n    return "failed"\n',encoding='utf-8')
        self.assertIn('implementation answers refer to an earlier source version',reconciliation_errors(answer,scan(self.root,['worker.py']),p['model']))

    def test_real_http_events_snapshots_recording_noise_and_invalid_facts(self):
        session=GraphSession(self.root);server=make_server(session,0,token='test-token')
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        base=f'http://127.0.0.1:{server.server_port}'
        probe=BOProbe(self.project,session.manifest['build_id'],endpoint=base,token='test-token')
        try:
            session.recordings.start('real HTTP')
            for i in range(10):
                with urlopen(base+'/api/view') as r:json.load(r)
            self.assertEqual(len(session.history.snapshot()),0)
            eid=probe.record('advance','change',lambda:{'inputs':{'state':'pending','event':'start','slots':0},'outputs':{'state':'waiting'}},revision=1)
            probe.snapshot('job','waiting',{'slots':0},1,eid)
            self.assertTrue(probe.flush());self.assertEqual(probe.bo_errors,0)
            self.assertEqual(session.graph.bo_instances()[0]['observed']['state'],'waiting')
            # Preserve a real invalid fact; do not silently replace or discard it.
            next_id=probe.record('advance','change',lambda:{'outputs':{'state':'illegal'}},revision=2)
            probe.snapshot('job','illegal',{'slots':-1},2,next_id)
            probe.flush();entry=session.graph.bo_instances()[0]
            self.assertEqual(entry['status'],'mismatch');self.assertEqual(entry['observed']['state'],'illegal')
            saved=session.recordings.stop();self.assertEqual(len(session.history.snapshot()),2)
            recorded=session.recordings.get(saved['id'])
            self.assertEqual(len(recorded['runtime_frames']['frames']),2)
            self.assertEqual(recorded['gaps'],[])
            with self.assertRaises(HTTPError):
                urlopen(Request(base+'/api/bo/events',data=b'{}',headers={'Content-Type':'application/json'},method='POST'))
        finally:probe.close();server.shutdown();server.server_close();session.close()

    def test_javascript_real_transport_and_service_failure_do_not_change_execution(self):
        session = GraphSession(self.root)
        server = make_server(session, 0, token='token')
        threading.Thread(target=server.serve_forever, daemon=True).start()
        base = f'http://127.0.0.1:{server.server_port}'
        # This is a delivery/isolation check, not a latency benchmark. Allow CI
        # scheduling and Node's first fetch to complete; test timeouts separately.
        script = f"""
import {{BOProbe, BOExecutor}} from {json.dumps(JS.as_uri())};
import fs from 'node:fs';
const x = JSON.parse(fs.readFileSync(0, 'utf8'));
const result = [];
for (const endpoint of [x.endpoint, 'http://127.0.0.1:1']) {{
  const p = new BOProbe({{project:x.project, buildId:x.build, endpoint, token:'token', timeout:5000}});
  const e = new BOExecutor(x.project.model.machine, {{available:c=>c.slots>0}});
  const r = e.step('pending', 'start', {{slots:1}});
  p.record('advance', 'return', () => ({{outputs:{{state:r.state}}}}));
  const flushed = await p.flush(15000);
  result.push({{state:r.state, errors:p.bo_errors, flushed}});
}}
console.log(JSON.stringify(result));
"""
        try:
            with urlopen(base + '/api/view', timeout=5) as response:
                self.assertEqual(response.status, 200)
            result = self.node(script, {
                'project': self.project, 'build': session.manifest['build_id'], 'endpoint': base,
            })
            self.assertEqual([r['state'] for r in result], ['running', 'running'])
            self.assertEqual(result[0]['errors'], 0)
            self.assertGreater(result[1]['errors'], 0)
            self.assertTrue(all(r['flushed'] for r in result))
            received = session.history.snapshot()
            self.assertEqual(len(received), 1)
            self.assertEqual(received[0]['outputs'], {'state': 'running'})
        finally:
            server.shutdown()
            server.server_close()
            session.close()

    def test_javascript_transport_timeout_preserves_business_result(self):
        session = GraphSession(self.root)
        entered = threading.Event()
        release = threading.Event()

        class PendingResponse(BaseHTTPRequestHandler):
            def log_message(self, *_args):
                pass

            def do_POST(self):
                self.rfile.read(int(self.headers['Content-Length']))
                entered.set()
                # Hold the response until the client finishes. A broken timeout
                # produces a successful response and fails the error assertion.
                release.wait(10)
                try:
                    self.send_response(204)
                    self.end_headers()
                except (BrokenPipeError, ConnectionResetError):
                    pass

        server = ThreadingHTTPServer(('127.0.0.1', 0), PendingResponse)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        script = f"""
import {{BOProbe, BOExecutor}} from {json.dumps(JS.as_uri())};
import fs from 'node:fs';
const x = JSON.parse(fs.readFileSync(0, 'utf8'));
const p = new BOProbe({{project:x.project, buildId:x.build, endpoint:x.endpoint, timeout:1000}});
const e = new BOExecutor(x.project.model.machine, {{available:c=>c.slots>0}});
const r = e.step('pending', 'start', {{slots:1}});
p.record('advance', 'return', () => ({{outputs:{{state:r.state}}}}));
const flushed = await p.flush(5000);
console.log(JSON.stringify({{state:r.state, errors:p.bo_errors, flushed}}));
"""
        try:
            result = self.node(script, {
                'project': self.project, 'build': session.manifest['build_id'],
                'endpoint': f'http://127.0.0.1:{server.server_port}',
            })
            self.assertTrue(entered.is_set(), 'The test must reach the real HTTP server')
            self.assertEqual(result['state'], 'running')
            self.assertEqual(result['errors'], 1)
            self.assertTrue(result['flushed'], 'An aborted request must leave no queued work')
        finally:
            release.set()
            server.shutdown()
            server.server_close()
            session.close()

    def test_native_state_snapshots_replay_exact_steps_and_transitions(self):
        session=GraphSession(self.root)
        probe=BOProbe(self.project,session.manifest['build_id'],sink=lambda body,kind:session.event(body) if kind=='events' else session.snapshot(body))
        def report(state,revision,event=None):
            ident=probe.record('advance','change',lambda:{'outputs':{'state':state}},entity='job',attempt='attempt-1',scope='entity',revision=revision)
            probe.snapshot('job',state,{'slots':0 if state=='waiting' else 1},revision,ident,event=event,guards={'available':state!='waiting'} if event in ('start','resume') else {},payload={} if event else None)
            self.assertTrue(probe.flush());self.assertEqual(probe.bo_errors,0)
        try:
            report('pending',0);session.recordings.start('native exact states')
            for revision,state,event in [(1,'waiting','start'),(2,'running','resume'),(3,'done','finish')]:
                report(state,revision,event)
                probe.record('advance','read',lambda:{'outputs':{}},entity='job',attempt='attempt-1',scope='entity')
                self.assertTrue(probe.flush())
            saved=session.recordings.stop();recorded=session.recordings.get(saved['id'])
            self.assertEqual(recorded['gaps'],[])
            self.assertEqual(len(recorded['runtime_frames']['frames']),3)
            self.assertNotEqual(recorded['run_id'],recorded['events'][0]['run_id'])
            from bo_stategraph import bo_validate_export
            exported=bo_validate_export(session.export())
            self.assertEqual(len(exported['runtime']['runtime_frames']['frames']),4)
            viewer=ROOT/'skills/vibelens/assets/stategraph-viewer'
            result=self.node(f"""import fs from 'node:fs';import {{timeline,frame,transferEdges}} from {json.dumps((viewer/'recording.js').as_uri())};
import {{boStepPlan,boStepDetail}} from {json.dumps((viewer/'replay-steps.js').as_uri())};import {{layoutGraph,selectedConfiguration}} from {json.dumps((viewer/'graph-core.js').as_uri())};
const r=JSON.parse(fs.readFileSync(0,'utf8'));r.events.at(-1).observed_at='2000-01-01T00:00:00Z';const items=timeline(r),all=new Map(r.context.model.nodes.map(n=>[n.id,n])),visible=r.context.model.nodes.filter(n=>n.kind==='state').map(n=>({{id:n.id,node:n,type:'state'}}));
const plan=boStepPlan(r,items,all,visible),indices=plan.filter(i=>items[i].kind==='probe');const states=indices.map(i=>frame(r,i,items).machine.current);
const v=frame(r,indices[0],items),g=layoutGraph(v,new Set(),new Set(),new Map(),'latest','latest',{{match:()=>new Set(visible.map(n=>n.id))}});const animation=transferEdges(items[indices[0]],v.events,g.edges,g.all,selectedConfiguration(v));
const detail=boStepDetail(r,items,indices[1],indices[0],all,visible);console.log(JSON.stringify({{states,animation,changes:detail.rows,ordered:items.slice(1,-1).map(e=>e.seq)}}));""",recorded)
            self.assertEqual(result['states'],['waiting','running','done'])
            self.assertTrue(result['animation'])
            self.assertTrue(any(c['before']=='waiting' and c['after']=='running' for c in result['changes']))
            self.assertEqual(result['ordered'],sorted(result['ordered']))
        finally:probe.close();session.close()

    def test_probe_off_fault_queue_pressure_and_self_reporting_are_isolated(self):
        off=BOProbe(self.project,'b',enabled=False);called=[]
        self.assertIsNone(off.record('advance','return',lambda:called.append(1)));self.assertEqual(called,[])
        def sink(body,kind):probe.record('advance','return',lambda:{'outputs':{'state':'recursive'}});raise RuntimeError('disk failure')
        probe=BOProbe(self.project,'b',sink=sink)
        try:
            probe.record('advance','return',lambda:{'outputs':{'state':'done'}});probe.flush()
            self.assertEqual(probe.bo_errors,1);self.assertEqual(probe.bo_suppressed,1)
        finally:probe.close()

    def test_duplicate_stale_and_foreign_build_cannot_overwrite(self):
        session=GraphSession(self.root);events=[];probe=BOProbe(self.project,session.manifest['build_id'],sink=lambda e,k:events.append(e))
        try:
            probe.record('advance','return',lambda:{'outputs':{'state':'done'}});probe.flush();event=events[0]
            session.event(event);self.assertTrue(session.event(event)['duplicate'])
            mutated={**event,'outputs':{'state':'waiting'}}
            with self.assertRaises(ValueError):session.event(mutated)
            with self.assertRaises(ValueError):session.event({**event,'build_id':'different'})
            (self.root/'worker.py').write_text('def advance(state,event,slots): return "bad"')
            self.assertEqual(session.view()['binding_status']['status'],'stale')
        finally:probe.close();session.close()

    def test_dom_entrypoints_and_side_effect_imports_cannot_hide(self):
        (self.root/'page.js').write_text("import './observer.js';function login(e){return e.type};button.onclick=login;button.addEventListener('click',login)")
        index=scan(self.root,['page.js'])
        self.assertEqual(len(index['symbols']['page.js::login']['entrypoints']),2)
        from architecture_guard import inspect
        (self.root/'observer.js').write_text('export function observe(){}')
        result=inspect(self.root,{'scan':['page.js','observer.js'],'layers':{'business':{'paths':['page.js'],'allows':['business']},'observer':{'paths':['observer.js'],'allows':['observer']}}})
        self.assertTrue(any('forbidden_dependency' in e for e in result['errors']))

    def test_verified_history_is_not_active_source_but_mutations_are_not_exempt(self):
        folder=self.root/'review/v1/source-snapshot';folder.mkdir(parents=True)
        source=folder/'page.js';source.write_text('button.onclick=()=>login()')
        import hashlib
        (folder.parent/'manifest.json').write_text(json.dumps({'files':{'page.js':hashlib.sha256(source.read_bytes()).hexdigest()}}))
        cfg={'source_scope':{'exclude':{'review/**':'immutable reviewed evidence'},'frozen_sources':{'review/v1/source-snapshot':'review/v1/manifest.json'}}}
        self.assertFalse(source_inventory(self.root,cfg)['excluded_entrypoints'])
        source.write_text('button.onclick=()=>otherLogin()')
        self.assertTrue(source_inventory(self.root,cfg)['excluded_entrypoints'])

    def test_javascript_probe_reentry_and_queue_bounds(self):
        result=self.node(f"""import {{BOProbe}} from {json.dumps(JS.as_uri())};import fs from 'node:fs';const project=JSON.parse(fs.readFileSync(0,'utf8'));let calls=0;
const probe=new BOProbe({{project,buildId:'b',capacity:1,sink:()=>{{calls++;probe.record('advance','read',()=>({{}}));probe.snapshot('a','done',{{slots:1}},1,'x');}}}});
probe.record('advance','read',()=>({{}}));probe.record('advance','read',()=>({{}}));await probe.flush();console.log(JSON.stringify({{calls,dropped:probe.bo_dropped,suppressed:probe.bo_suppressed}}));""",self.project)
        self.assertEqual(result,{'calls':1,'dropped':1,'suppressed':2})

    def test_native_ingress_reuses_session_and_rejects_conflicting_duplicate(self):
        from semantic_probe import Pins
        from bo_observer.observation.native_ingress import NativeIngress
        collected=[];raw=[]
        pins=Pins(self.project['model'],'b',sink=lambda s:collected.append(json.loads(s)))
        probe=BOProbe(self.project,'b',sink=lambda e,k:raw.append(e));ingress=NativeIngress(pins,self.project)
        try:
            probe.record('advance','return',lambda:{'outputs':{'state':'done'}});probe.flush()
            self.assertTrue(ingress.accept(raw[0])['recorded']);self.assertTrue(ingress.accept(raw[0])['duplicate']);pins.flush()
            self.assertEqual(collected[0]['stream_id'],pins.run_id)
            with self.assertRaises(ValueError):ingress.accept({**raw[0],'outputs':{'state':'changed'}})
            skipped={**raw[0],'id':'skipped','seq':2}
            pins.bo_scope=set()
            self.assertFalse(ingress.accept(skipped)['recorded'])
            pins.bo_scope=None
            self.assertEqual(ingress.accept({**raw[0],'id':'third','seq':3})['gap'],0)
            self.assertEqual(ingress.accept({**raw[0],'id':'fifth','seq':5})['gap'],1)
            self.assertEqual(pins.dropped,1)
        finally:probe.close();pins.close()

    def test_view_source_and_saved_recording_use_build_source(self):
        session=GraphSession(self.root);server=make_server(session,0);threading.Thread(target=server.serve_forever,daemon=True).start()
        try:
            with urlopen(f'http://127.0.0.1:{server.server_port}/api/source?path=worker.py') as response:source=json.load(response)
            self.assertIn('def advance',source['source'])
            session.recordings.start('source snapshot');saved=session.recordings.stop()
            self.assertIsInstance(session.recordings.get(saved['id'])['sources']['worker.py'],str)
        finally:server.shutdown();server.server_close();session.close()

if __name__=='__main__':unittest.main()
