"""Regressions for the six independently reproduced assessment failures."""
from copy import deepcopy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'skills/business-observer/scripts'))
from bo_stategraph import BOStateGraph, bo_export_view, bo_validate_export, bo_digest
from bo_contracts import validate_chart, validate_runtime_definition
from mapping_contract import assess
from semantic_probe import Pins
from mapping_contract import protected_plan_errors
from test_stategraph_module import model


def mapping_fixture():
    m = model()
    machine = {'configurations': [{'attempt': 'i', 'phase': 'waiting', 'state_revision': 1,
                'run_build_id': 'b', 'context': {'slots': 1}}]}
    graph = BOStateGraph(m, build_id='b')
    exported = graph.bo_export(runtime={'machine': machine})
    run = {'case': 'case', 'mode': 'on', 'facts': [{'id': 'i', 'state': 'waiting',
           'revision': 1, 'build': 'b', 'slots': 1}],
           'projection': {'build_id': 'b', 'machine': machine, 'instances': exported['instances']}}
    fields = [{'id': name, 'node': 'waiting', 'actual': actual, 'mapped': mapped}
              for name, actual, mapped in [('state', ['state'], ['state']),
                  ('revision', ['revision'], ['revision']), ('build', ['build'], ['build_id']),
                  ('slots', ['slots'], ['context', 'slots'])]]
    plan = {'schema': 'bo-mapping/v1', 'cases': ['case'], 'modes': ['on'],
            'source': 'store.snapshot', 'actual_collection': ['facts'], 'actual_id': ['id'],
            'fields': fields, 'export': {'case': 'case', 'mode': 'on'}}
    payload = {'build_id': 'b', 'runs': [run], 'stategraph_export': exported,
               'mapping_checks': [{'id': 'old', 'source': 'store', 'projection': 'state',
                                   'actual': 'waiting', 'mapped': 'waiting'}]}
    return m, plan, payload


class MappingTests(unittest.TestCase):
    def check_payload(self, m, plan, payload):
        return assess(payload, required=True, plan=plan, model=m, build_id='b')

    def test_real_public_projection_is_checked(self):
        m, plan, payload = mapping_fixture()
        self.assertTrue(self.check_payload(m, plan, payload)['valid'])
        payload['stategraph_export'] = BOStateGraph(m, build_id='b').bo_export(runtime={'machine': {'configurations': []}})
        self.assertFalse(self.check_payload(m, plan, payload)['valid'])

    def test_missing_case_instance_field_wrong_revision_and_type_fail(self):
        mutations = [lambda p: p['runs'].clear(),
            lambda p: p['runs'][0]['projection']['instances'].clear(),
            lambda p: p['runs'][0]['facts'][0].pop('slots'),
            lambda p: p['runs'][0]['facts'][0].update(revision=2),
            lambda p: p['runs'][0]['facts'][0].update(slots=True)]
        for change in mutations:
            with self.subTest(change=mutations.index(change)):
                m, plan, payload = mapping_fixture(); change(payload)
                self.assertFalse(self.check_payload(m, plan, payload)['valid'])

    def test_missing_plan_is_not_complete_mapping(self):
        _, _, payload = mapping_fixture()
        self.assertFalse(assess(payload, required=True)['valid'])

    def test_plan_cannot_drop_cases_fields_or_change_bindings(self):
        _, plan, _ = mapping_fixture()
        for mutate in (lambda p:p['fields'].pop(), lambda p:p['cases'].clear(),
                       lambda p:p.update(actual_collection=['other'])):
            newer=deepcopy(plan);mutate(newer)
            self.assertTrue(protected_plan_errors(plan,newer))
        self.assertFalse(protected_plan_errors(plan,deepcopy(plan)))

    def test_independent_projection_mismatch_not_hidden_by_witness(self):
        m, plan, payload = mapping_fixture()
        payload['runs'][0]['facts'][0]['slots'] = 2
        self.assertFalse(self.check_payload(m, plan, payload)['valid'])
        m, plan, payload = mapping_fixture()
        payload['mapping_checks'].clear()
        self.assertFalse(self.check_payload(m, plan, payload)['valid'])

    def test_missing_revision_cannot_be_passed_as_two_equal_nulls(self):
        m, plan, payload = mapping_fixture()
        run = payload['runs'][0]
        run['facts'][0]['revision'] = None
        run['projection']['machine']['configurations'][0]['state_revision'] = None
        graph = BOStateGraph(m, build_id='b')
        exported = graph.bo_export(runtime={'machine': run['projection']['machine']})
        run['projection']['instances'] = exported['instances']
        payload['stategraph_export'] = exported
        self.assertFalse(self.check_payload(m, plan, payload)['valid'])


class EngineTests(unittest.TestCase):
    def fixture(self, states, initial, transitions, values=None):
        m = model(); values = values or states
        m['machine'].update(states=states, initial=initial, values=values,
            transitions=transitions, events={'go': {'payload': {}}}, context={}, guards={})
        m['nodes'] = [{'id': s, 'kind': 'state', 'layer': 'state', 'value': s} for s in values]
        m['edges'] = []
        return m

    def compare(self, m, cls, wrong):
        holder = SimpleNamespace(); c = m['machine']
        cls(holder, states=c['states'], transitions=c['transitions'], initial=c['initial'], auto_transitions=False)
        start = deepcopy(holder.state); holder.go()
        for state, status in [(holder.state, 'observed'), (wrong, 'mismatch')]:
            with self.subTest(state=state):
                graph = BOStateGraph(m, build_id='b')
                graph.bo_observe('i', state=start, context={}, revision=0, evidence_id='s0', build_id='b')
                value = graph.bo_observe('i', state=state, context={}, revision=1, evidence_id='s1', build_id='b', event='go')
                self.assertEqual(value['status'], status)
                self.assertEqual(value['observed']['state'], state)

    def test_wildcard_respects_first_matching_handler(self):
        from transitions import Machine
        self.compare(self.fixture(['a','b','c'], 'a', [
            {'source':'a','dest':'b','trigger':'go'}, {'source':'*','dest':'c','trigger':'go'}]), Machine, 'c')

    def test_compound_entry_resolves_initial_descendants(self):
        from transitions.extensions import HierarchicalMachine
        m = self.fixture(['idle', {'name':'active','initial':'a','children':['a','b']}], 'idle',
            [{'source':'idle','dest':'active','trigger':'go'}], ['idle','active_a','active_b'])
        self.compare(m, HierarchicalMachine, 'active_b')
        incomplete = BOStateGraph(m, build_id='b').bo_observe('i', state='active', context={},
            revision=0, evidence_id='s0', build_id='b')
        self.assertEqual(incomplete['status'], 'mismatch')
        self.assertEqual(incomplete['observed']['state'], 'active')

    def test_invalid_initial_and_unsupported_engine_fail_at_load(self):
        mutations = [lambda c: c.update(engine='unimplemented.Engine'),
            lambda c: c['states'].append({'name':'group','initial':'missing','children':['a']}),
            lambda c: c['events']['start']['payload'].update(size={'type':'unknown'}),
            lambda c: c['transitions'][0].update(before='arbitrary_callback')]
        for change in mutations:
            with self.subTest(change=mutations.index(change)):
                m=model(); change(m['machine'])
                for entry in (lambda: validate_chart(m), lambda: BOStateGraph(m,build_id='b')):
                    with self.assertRaises(ValueError): entry()

    def test_parallel_entry_and_independent_region_steps_match_real_engine(self):
        from transitions.extensions import HierarchicalMachine
        states=['idle', {'name':'work','parallel':[
            {'name':'a','initial':'one','children':['one','two']},
            {'name':'b','initial':'one','children':['one','two']}]}]
        m=self.fixture(states,'idle',[{'source':'idle','dest':'work','trigger':'go'}],
            ['idle','work_a_one','work_a_two','work_b_one','work_b_two'])
        self.compare(m,HierarchicalMachine,['work_a_two','work_b_one'])
        m['machine']['initial']='work'
        m['machine']['transitions']=[{'source':'work_a_one','dest':'work_a_two','trigger':'go'},
                                    {'source':'work_b_one','dest':'work_b_two','trigger':'go'}]
        self.compare(m,HierarchicalMachine,['work_a_two','work_b_one'])

    def test_startup_definition_gate_raises_instead_of_returning_false(self):
        graph=BOStateGraph(model(),build_id='b');loaded=graph.bo_definition()
        self.assertTrue(graph.bo_require_definition(loaded)['valid'])
        loaded['transitions'].pop()
        with self.assertRaises(ValueError):graph.bo_require_definition(loaded)

    def test_actual_engine_version_and_guard_binding_are_strict(self):
        chart=model()['machine'];chart.update(engine='transitions.Machine',version='0.9.3')
        validate_runtime_definition(chart,loaded_engine='transitions.Machine',loaded_version='0.9.3',guard_names={'allowed'})
        for args in ({'loaded_engine':'other'}, {'loaded_version':'0.9.4'}, {'guard_names':set()}):
            with self.subTest(args=args), self.assertRaises(ValueError):validate_runtime_definition(chart,**args)

    def test_loaded_definition_compares_types_and_rejects_engine_options(self):
        m = model(); loaded = deepcopy(m['machine'])
        loaded['context']['slots']['min'] = False  # False == 0 in Python, not in the contract.
        with self.assertRaises(ValueError): validate_chart(m, loaded)
        self.assertFalse(BOStateGraph(m, build_id='b').bo_check_definition(loaded)['valid'])
        for option in ('queued', 'auto_transitions', 'ignore_invalid_triggers'):
            chart = deepcopy(m['machine']); chart[option] = True
            with self.subTest(option=option), self.assertRaises(ValueError): validate_runtime_definition(chart)


class RuntimeTests(unittest.TestCase):
    def test_real_service_query_and_recording_finish_without_deadlock(self):
        result=subprocess.run([sys.executable,'-B','-X','utf8',__file__,'--lock-probe'],
                              capture_output=True,text=True,encoding='utf-8',timeout=20)
        self.assertEqual(result.returncode,0,result.stderr)
        value=json.loads(result.stdout)
        self.assertEqual(value,{'view_waiting':False,'query_waiting':False,'errors':[]})

    def test_provider_does_not_run_under_graph_lock_in_query_or_export(self):
        for method in ('bo_instances','bo_export'):
            graph=BOStateGraph(model(),build_id='b'); acquired=[]
            def provider():
                def read():
                    with graph._lock: acquired.append(True)
                worker=threading.Thread(target=read,daemon=True);worker.start();worker.join(.3)
                if worker.is_alive(): raise RuntimeError('external provider called with graph lock held')
                return {'configurations':[]}
            graph.bo_bind_instances(provider)
            with self.subTest(method=method): getattr(graph,method)(); self.assertEqual(acquired,[True])

    def test_exact_frames_survive_full_graph_export(self):
        m, _, payload=mapping_fixture(); e={'id':'e','revision':1,'run_id':'p','build_id':'b'}
        machine=deepcopy(payload['stategraph_export']['runtime']['machine']);machine['state_revision']=1
        view={'model':m,'manifest':{'build_id':'b'},'machine':machine,'events':[e],
              'health':{},'authority':{'state':'waiting'},'binding_status':{'status':'current'},
              'runtime_frames':{'schema':'stategraph-runtime-frames/v1','frames':[{
                  'event_id':'e','revision':1,'run_id':'p','build_id':'b','machine':machine,'authority':{'state':'waiting'}}]}}
        exported=bo_export_view(view)
        self.assertEqual(exported['runtime']['runtime_frames'],view['runtime_frames'])
        self.assertIs(bo_validate_export(exported), exported)
        for mutate in (lambda f: f['frames'][0].update(revision=2),
                       lambda f: f['frames'][0].update(event_id='missing'),
                       lambda f: f['frames'][0]['machine'].update(state_revision=True)):
            broken = deepcopy(exported); mutate(broken['runtime']['runtime_frames'])
            broken['sha256'] = bo_digest({k:v for k,v in broken.items() if k != 'sha256'})
            with self.subTest(mutate=mutate), self.assertRaises(ValueError): bo_validate_export(broken)
        for key, value in [('run_id', None), ('build_id', ''), ('revision', -1)]:
            broken = deepcopy(exported)
            broken['runtime']['events'][0][key] = value
            broken['runtime']['runtime_frames']['frames'][0][key] = value
            if key == 'revision': broken['runtime']['runtime_frames']['frames'][0]['machine']['state_revision'] = value
            broken['sha256'] = bo_digest({k:v for k,v in broken.items() if k != 'sha256'})
            with self.subTest(key=key), self.assertRaises(ValueError): bo_validate_export(broken)
        exported['runtime']['runtime_frames']['frames'].clear()
        self.assertEqual(len(view['runtime_frames']['frames']),1)

    def test_default_path_sink_is_bounded(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'.validation') as folder:
            path=Path(folder)/'events.jsonl'
            m={'revision':1,'nodes':[{'id':'n','capture':{'out':{'value':'number'}}}]}
            pins=Pins(m,'b',path=path,retention={'memory_events':2,'memory_seconds':60,'log_bytes':1024,'log_backups':1})
            try:
                trace=pins.attempt('test')
                for value in range(25):trace.record('n','return',{},lambda v=value:{'outputs':{'value':v}})
                self.assertTrue(pins.flush())
                self.assertLessEqual(path.stat().st_size,1024)
                self.assertEqual(pins.health()['retention']['evicted_events'],23)
            finally:pins.close()

    def test_project_retention_policy_is_loaded_and_bad_policy_rejected(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'.validation') as folder:
            root=Path(folder);cfg=root/'bo_stategraph/config/retention.json';cfg.parent.mkdir(parents=True)
            cfg.write_text(json.dumps({'log_bytes':1024}),encoding='utf-8')
            pins=Pins({'nodes':[]},'b',path=root/'log.jsonl',project_root=root,enabled=False)
            self.assertEqual(pins.history.limits['log_bytes'],1024);pins.close()
            cfg.write_text(json.dumps({'log_bytes':0}),encoding='utf-8')
            with self.assertRaises(ValueError):Pins({'nodes':[]},'b',path=root/'log.jsonl',project_root=root)

    def test_atomic_write_retries_only_transient_failure(self):
        import sync_io
        with tempfile.TemporaryDirectory(dir=ROOT/'.validation') as folder:
            path=Path(folder)/'task.json';replace=sync_io.os.replace;calls=[]
            def transient(a,b):
                calls.append(1)
                if len(calls)<3:raise PermissionError('temporary reader')
                return replace(a,b)
            with patch.object(sync_io.os,'replace',side_effect=transient):sync_io.write(path,{'ok':True})
            self.assertEqual(json.loads(path.read_text()),{'ok':True})
            self.assertEqual(len(calls),3)
            with patch.object(sync_io.os,'replace',side_effect=PermissionError('occupied')):
                with self.assertRaises(PermissionError):sync_io.write(path,{'ok':False})
            self.assertEqual(json.loads(path.read_text()),{'ok':True})
            self.assertEqual(list(Path(folder).glob('*.tmp')),[])

    @unittest.skipUnless(os.name=='nt','Windows sharing-lock behavior')
    def test_watcher_survives_real_file_occupation_and_publishes_latest(self):
        import ctypes
        from ctypes import wintypes
        with tempfile.TemporaryDirectory(dir=ROOT/'.validation') as folder:
            root=Path(folder);(root/'app.py').write_text('value=1\n')
            (root/'sync.json').write_text(json.dumps({'code_files':['app.py'],'source_scope':{'roots':['.']}}))
            target=root/'.stategraph/maintenance.json'
            with (root/'watch.log').open('w',encoding='utf-8') as log:
                proc=subprocess.Popen([sys.executable,'-B','-X','utf8',str(ROOT/'skills/business-observer/scripts/bo_sync.py'),
                    'watch','--root',str(root),'--interval','.1'],stdout=log,stderr=log)
                handle=None
                try:
                    deadline=time.monotonic()+6
                    while not target.exists() and time.monotonic()<deadline:time.sleep(.05)
                    old=json.loads(target.read_text(encoding='utf-8'))['source_id']
                    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
                    kernel.CreateFileW.argtypes=[wintypes.LPCWSTR,wintypes.DWORD,wintypes.DWORD,wintypes.LPVOID,wintypes.DWORD,wintypes.DWORD,wintypes.HANDLE]
                    kernel.CreateFileW.restype=wintypes.HANDLE;kernel.CloseHandle.argtypes=[wintypes.HANDLE]
                    handle=kernel.CreateFileW(str(target),0x80000000,3,None,3,0,None)
                    self.assertNotEqual(handle,wintypes.HANDLE(-1).value)
                    (root/'app.py').write_text('value=2\n');time.sleep(1)
                    self.assertIsNone(proc.poll())
                    kernel.CloseHandle(handle);handle=None
                    deadline=time.monotonic()+6
                    while time.monotonic()<deadline:
                        if json.loads(target.read_text(encoding='utf-8'))['source_id']!=old:break
                        time.sleep(.05)
                    self.assertNotEqual(json.loads(target.read_text(encoding='utf-8'))['source_id'],old)
                    self.assertIsNone(proc.poll())
                finally:
                    if handle is not None:kernel.CloseHandle(handle)
                    proc.terminate();proc.wait(timeout=5)


def lock_probe():
    # This child first imports canonical helpers for unit tests. The actual
    # application needs its package namespace, just like a clean run.py process.
    sys.modules.pop('bo_stategraph',None)
    sys.path.insert(0,str(ROOT/'examples/team-archive'))
    from integrations.bo_server import LocalApplication
    source=ROOT/'examples/team-archive';root=Path(tempfile.mkdtemp(dir=ROOT/'.validation'))
    app=LocalApplication(root,SimpleNamespace(db=str(root/'test.sqlite'),delay=0,candidate=False),
        json.loads((source/'behavior.json').read_text(encoding='utf-8')),
        json.loads((source/'manifest.json').read_text(encoding='utf-8')), {})
    service_held,provider_entered=threading.Event(),threading.Event();errors=[]
    original=app.observer.bo_graph._provider
    def provider():provider_entered.set();return original()
    app.observer.bo_graph.bo_bind_instances(provider)
    def view():
        try:
            with app.service.lock:
                service_held.set()
                if not provider_entered.wait(4):raise RuntimeError('query not entered')
                app.recording_view()
        except Exception as exc:errors.append(str(exc))
    def query():
        try:
            if not service_held.wait(4):raise RuntimeError('view not entered')
            app.observer.bo_graph.bo_instances()
        except Exception as exc:errors.append(str(exc))
    a=threading.Thread(target=view,daemon=True);b=threading.Thread(target=query,daemon=True)
    a.start();b.start();a.join(3);b.join(3)
    print(json.dumps({'view_waiting':a.is_alive(),'query_waiting':b.is_alive(),'errors':errors}),flush=True)
    os._exit(0)


if __name__=='__main__':
    if '--lock-probe' in sys.argv:lock_probe()
    unittest.main()
