"""Independent audit probes. Writes only audit evidence and isolated fixtures.

Run: python -B -X utf8 docs/assessment/2026-10-22/reproduce.py
The intentionally wrong observations below test diagnosis, not business behavior.
No product source, accepted baseline, user database or running service is changed.
"""
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

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
WORK = ROOT / '.validation/assessment-20261022'
SCRIPTS = ROOT / 'skills/business-observer/scripts'


def deadlock_probe():
    # Actual example methods and locks. Barriers only select a legal interleaving.
    source = WORK / 'source/examples/team-archive'
    sys.path.insert(0, str(source))
    from integrations.bo_server import LocalApplication
    root = Path(tempfile.mkdtemp(prefix='lock-order-', dir=WORK))
    model = json.loads((source / 'behavior.json').read_text(encoding='utf-8'))
    manifest = json.loads((source / 'manifest.json').read_text(encoding='utf-8'))
    app = LocalApplication(root, SimpleNamespace(db=str(root/'audit.sqlite'), delay=0,
                           candidate=False), model, manifest, {})
    service_held, graph_held = threading.Event(), threading.Event()
    original = app.observer.bo_graph._provider
    def synchronized_provider():
        graph_held.set()
        return original()
    app.observer.bo_graph.bo_bind_instances(synchronized_provider)
    errors = []
    def recorded_view():
        try:
            with app.service.lock:
                service_held.set()
                if not graph_held.wait(4): raise RuntimeError('reader did not start')
                app.recording_view()
        except Exception as exc: errors.append(repr(exc))
    def query():
        try:
            if not service_held.wait(4): raise RuntimeError('view did not start')
            app.observer.bo_graph.bo_instances()
        except Exception as exc: errors.append(repr(exc))
    view = threading.Thread(target=recorded_view, daemon=True)
    reader = threading.Thread(target=query, daemon=True)
    view.start(); reader.start()
    view.join(2); reader.join(2)
    result = {'view_waiting':view.is_alive(), 'query_waiting':reader.is_alive(),
              'service_lock_acquired':service_held.is_set(), 'graph_lock_acquired':graph_held.is_set(),
              'errors':errors, 'product_methods':'LocalApplication.recording_view / BOStateGraph.bo_instances'}
    print(json.dumps(result), flush=True)
    # All data belongs to this disposable child. Release OS locks on termination.
    os._exit(0)


if '--deadlock' in sys.argv:
    deadlock_probe()

sys.path.insert(0, str(SCRIPTS))
from bo_stategraph import BOStateGraph, bo_export_view, bo_validate_export, bo_digest
from bo_contracts import value_errors
from mapping_contract import assess as mapping_assess
from transitions import Machine
from transitions.extensions import HierarchicalMachine


def model(states, values, initial, transitions):
    return {'machine':{'states':states, 'values':values, 'initial':initial,
            'events':{'go':{'payload':{}}}, 'context':{}, 'guards':{}, 'transitions':transitions},
            'nodes':[{'id':s,'kind':'state','layer':'state','value':s} for s in values], 'edges':[]}


def transition_probe(name, definition, supplied, cls):
    graph = BOStateGraph(definition, build_id='audit')
    holder = SimpleNamespace()
    chart = definition['machine']
    cls(holder, states=chart['states'], transitions=chart['transitions'],
        initial=chart['initial'], auto_transitions=False)
    graph.bo_observe('i', state=holder.state, context={}, revision=0,
                     evidence_id='start', build_id='audit')
    holder.go()
    observed = graph.bo_observe('i', state=supplied, context={}, revision=1,
                               evidence_id='after', build_id='audit', event='go')
    return {'id':name, 'actual_engine_state':holder.state, 'supplied_state':supplied,
            'observer_status':observed['status'], 'errors':observed['errors'],
            'candidates':observed['transition_check']['candidates']}


def locked_watch():
    if os.name != 'nt': return {'id':'watch_write_conflict', 'status':'not_run', 'reason':'Windows-specific'}
    import ctypes
    from ctypes import wintypes
    root = Path(tempfile.mkdtemp(prefix='watch-conflict-', dir=WORK))
    (root/'app.py').write_text('def run(): return 1\n', encoding='utf-8')
    (root/'sync.json').write_text(json.dumps({'code_files':['app.py'],
        'source_scope':{'roots':['.']}}), encoding='utf-8')
    log = OUT/'watch-write-conflict.log'
    with log.open('w', encoding='utf-8') as stream:
        proc = subprocess.Popen([sys.executable,'-B','-X','utf8',str(SCRIPTS/'bo_sync.py'),
            'watch','--root',str(root),'--interval','.1'], stdout=stream, stderr=stream)
        handle = None
        try:
            target = root/'.stategraph/maintenance.json'
            deadline = time.monotonic()+5
            while not target.exists() and time.monotonic()<deadline: time.sleep(.05)
            if not target.exists(): raise RuntimeError('watcher did not create initial task')
            kernel = ctypes.WinDLL('kernel32', use_last_error=True)
            kernel.CreateFileW.argtypes = [wintypes.LPCWSTR,wintypes.DWORD,wintypes.DWORD,
                wintypes.LPVOID,wintypes.DWORD,wintypes.DWORD,wintypes.HANDLE]
            kernel.CreateFileW.restype = wintypes.HANDLE
            kernel.CloseHandle.argtypes = [wintypes.HANDLE]
            # A normal open reader that allows read/write but not atomic deletion.
            handle = kernel.CreateFileW(str(target), 0x80000000, 0x1|0x2, None, 3, 0, None)
            if handle == wintypes.HANDLE(-1).value: raise ctypes.WinError(ctypes.get_last_error())
            (root/'app.py').write_text('def run(): return 2\n', encoding='utf-8')
            try: proc.wait(timeout=4)
            except subprocess.TimeoutExpired: pass
            status = proc.poll()
            kernel.CloseHandle(handle); handle = None
            time.sleep(.25)
            return {'id':'watch_write_conflict','exit_while_reader_open':status,
                    'recovered_after_reader_closed':proc.poll() is None,
                    'log':log.name, 'fixture':str(root)}
        finally:
            if handle is not None: kernel.CloseHandle(handle)
            if proc.poll() is None: proc.terminate(); proc.wait(timeout=5)


def main():
    WORK.mkdir(exist_ok=True)
    results = []
    flat = model(['a','b','c'], ['a','b','c'], 'a', [
        {'source':'a','dest':'b','trigger':'go'}, {'source':'*','dest':'c','trigger':'go'}])
    results.append(transition_probe('wildcard_priority', flat, 'c', Machine))
    nested = model(['idle',{'name':'active','initial':'a','children':['a','b']}],
        ['idle','active_a','active_b'], 'idle', [{'source':'idle','dest':'active','trigger':'go'}])
    results.append(transition_probe('compound_initial', nested, 'active_b', HierarchicalMachine))
    parent = model([{'name':'active','children':['a','b']},'done'],
        ['active_a','active_b','done'], 'active_a', [{'source':'active','dest':'done','trigger':'go'}])
    results.append(transition_probe('original_parent_fixed', parent, 'done', HierarchicalMachine))
    results.append({'id':'strict_enum_fixed','errors':value_errors(True,{'type':'enum','values':[1]},'value')})

    machine = {'state_revision':1,'configurations':[{'attempt':'i','phase':'a','context':{},
        'state_revision':1,'run_build_id':'audit'}]}
    event = {'id':'producer:1','seq':1,'revision':1,'run_id':'producer','build_id':'audit'}
    frame = {'event_id':event['id'],'run_id':'producer','build_id':'audit','revision':1,
             'machine':deepcopy(machine),'authority':{'state':'a'}}
    view = {'model':flat,'manifest':{'build_id':'audit'},'machine':machine,'events':[event],
        'health':{'run_id':'producer'},'runtime_frames':{'schema':'stategraph-runtime-frames/v1','frames':[frame]}}
    exported = bo_export_view(view)
    results.append({'id':'export_drops_runtime_frames','input_frames':len(view['runtime_frames']['frames']),
        'export_has_frames':'runtime_frames' in exported['runtime'],
        'export_checks_valid':bo_validate_export(exported) is exported})

    checks = [{'id':'states','source':'actual storage','projection':'instances.i.state','actual':'a','mapped':'a'},
              {'id':'slots','source':'actual storage','projection':'instances.i.context.slots','actual':1,'mapped':99}]
    results.append({'id':'missing_mapping_witness', 'complete':mapping_assess({'mapping_checks':checks},required=True),
        'dropped_failing_item':mapping_assess({'mapping_checks':checks[:1]},required=True),
        'scope':'Checker input test, not a claim that every full application gate passes.'})
    altered = deepcopy(exported)
    altered['runtime']['machine']['configurations'][0]['phase']='c'
    graph = BOStateGraph(flat,build_id='audit')
    altered['instances']=graph.bo_instances(altered['runtime']['machine'])
    altered['sha256']=bo_digest({k:v for k,v in altered.items() if k!='sha256'})
    checks[0]['mapped']='a'
    results.append({'id':'witness_not_bound_to_projection','exported_state':altered['instances'][0]['observed']['state'],
        'actual_and_witness_state':checks[0]['actual'],
        'export_checks_valid':bo_validate_export(altered) is altered,
        'mapping_result':mapping_assess({'stategraph_export':altered,'mapping_checks':checks[:1]},required=True),
        'scope':'Public checks accept internally valid export plus disconnected witness values.'})

    results.append(locked_watch())
    child = subprocess.run([sys.executable,'-B','-X','utf8',__file__,'--deadlock'],
        capture_output=True,text=True,encoding='utf-8',timeout=20)
    (OUT/'query-lock-order.log').write_text(child.stdout+child.stderr,encoding='utf-8')
    results.append({'id':'query_view_lock_order','exit_code':child.returncode,
        'result':json.loads(child.stdout) if child.returncode==0 else child.stderr,
        'method':'Actual methods with barriers controlling thread scheduling; disposable process.'})
    (OUT/'reproductions.json').write_text(json.dumps(results,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(results,ensure_ascii=False,indent=2))


if __name__ == '__main__': main()
