"""Regression for the login, upload note and notification omissions in a real trial."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'skills/vibelens/scripts'))
from code_structure import scan, enrich
from implementation_coverage import static_errors, runtime_errors, protected_errors, protected_captures, inventory_errors
from bo_sync import source_inventory
from semantic_probe import Pins
from sync_config import tool_fingerprints
from bo_upgrade import bridge_source, CORE

SOURCE = '''
class Routes:
    def post(self, path):
        return lambda fn: fn
api = Routes()

@api.post('/login')
def login(username, password, trace):
    allowed = username == 'reviewer' and password == 'synthetic-only'
    trace.record('login', 'return', {'param_version': 1}, lambda: {
        'inputs': {'username': username, 'password_present': bool(password)},
        'outputs': {'authenticated': allowed}})
    return allowed

@api.post('/files')
def upload(note, trace):
    saved = {'note': note, 'state': 'pending'}
    trace.record('upload', 'commit', {'param_version': 1}, lambda: {
        'inputs': {'note': note}, 'outputs': {'state': saved['state']}})
    notify(trace)
    return saved

def notify(trace):
    trace.record('notify', 'commit', {'param_version': 1}, lambda: {'outputs': {'count': 1}})

@api.post('/messages/read')
def read_message(message_id, trace):
    trace.record('read_message', 'commit', {'param_version': 1}, lambda: {
        'inputs': {'message_id': message_id}, 'outputs': {'read': True}})
    return True
'''


def fixture(root):
    (root/'app.py').write_text(SOURCE, encoding='utf-8')
    index = scan(root, ['app.py'])
    captures = {'login': {'in': {'username':'string','password_present':'boolean'},'out':{'authenticated':'boolean'}},
        'upload': {'in':{'note':'string'},'out':{'state':'string'}},
        'notify': {'out':{'count':'number'}}, 'read_message': {'in':{'message_id':'string'},'out':{'read':'boolean'}}}
    nodes = [{'id': nid, 'kind':'effect' if nid == 'notify' else 'function', 'layer':'business',
              'label':nid, 'source':{'path':'app.py','symbol':nid}, 'capture':capture} for nid,capture in captures.items()]
    features = []
    for n in nodes:
        sid = 'app.py::'+n['id']
        params = []
        for p in index['symbols'][sid]['parameters']:
            name = p['name']
            item = {'source':sid,'name':name}
            if name == 'trace': item.update(policy='context',reason="Optional observation interface")
            elif name == 'password': item.update(node=n['id'],field='password_present',policy='derived',reason="Record presence only; never capture credentials")
            else: item.update(node=n['id'],field=name,policy='value')
            params.append(item)
        case={'case':'review','node':n['id'],'phase':'return' if n['id']=='login' else 'commit'}
        if n['id']=='upload': case['values']=[{'field':'note','path':['saved','note']}]
        features.append({'id':n['id'],'label':n['id'],'business_node':n['id'],'nodes':[n['id']],
                         'sources':[sid],'parameters':params,'cases':[case]})
    plan = {'schema':'bo-implementation/v1','features':features,'support':{
        'app.py::Routes.post':{'node':'upload','reason':"Test decorator preserves static implementation ownership"}},'excluded':{}}
    model = {'revision':'test','nodes':nodes,'edges':[], 'graph_roots':list(captures), 'implementation':plan}
    return enrich(model,index), index


class CoverageTests(unittest.TestCase):
    def setUp(self):
        (ROOT/'.validation').mkdir(exist_ok=True)
        self.tmp = tempfile.TemporaryDirectory(dir=ROOT/'.validation')
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.model,self.index=fixture(self.root)
        self.plan=self.model['implementation']

    def run_program(self, model=None):
        events=[]
        pins=Pins(model or self.model,'build',sink=lambda line:events.append(json.loads(line)))
        trace=pins.attempt('review')
        namespace={}
        exec(compile(SOURCE,'app.py','exec'),namespace)
        self.assertTrue(namespace['login']('reviewer','synthetic-only',trace))
        saved=namespace['upload']("Please review the attachment",trace)
        self.assertTrue(namespace['read_message']('message-1',trace))
        pins.close()
        return {'build_id':'build','runs':[{'case':'review','mode':'on','events':events,'observations':{'saved':saved}}]}

    def test_real_execution_covers_login_note_and_message_lifecycle(self):
        self.assertEqual(static_errors(self.plan,self.model,self.index),[])
        payload=self.run_program()
        self.assertEqual(runtime_errors(self.plan,self.model,payload)['errors'],[])
        self.assertNotIn('synthetic-only',json.dumps(payload))

    def test_a_new_endpoint_is_discovered_without_using_graph_nodes(self):
        (self.root/'app.py').write_text(SOURCE+'\n@api.post("/logout")\ndef logout():\n    return True\n',encoding='utf-8')
        errors=static_errors(self.plan,self.model,scan(self.root,['app.py']))
        self.assertTrue(any(e.get('unclassified_implementation')=='app.py::logout' for e in errors if isinstance(e,dict)))

    def test_free_text_exclusion_cannot_waive_login(self):
        self.plan['features']=[f for f in self.plan['features'] if f['id']!='login']
        self.plan['excluded']['app.py::login']={'category':'utility','reason':'HTTP tests already cover it'}
        self.assertTrue(any('entrypoint_cannot_be_excluded' in e for e in static_errors(self.plan,self.model,self.index)))

    def test_source_file_exclusion_still_detects_routes(self):
        result=source_inventory(self.root,{'source_scope':{'roots':['.'],'exclude':{'app.py':'covered by HTTP tests'}}})
        self.assertIn('app.py',result['excluded_entrypoints'])

    def test_exclusion_cannot_hide_plain_business_functions(self):
        (self.root/'storage.py').write_text('def authenticate(user): return bool(user)\n',encoding='utf-8')
        cfg={'stategraph':{'module':'bo_stategraph/__init__.py'},'code_files':['app.py'],
             'source_scope':{'roots':['.'],'exclude':{'storage.py':'tested elsewhere'}}}
        self.assertTrue(any('excluded_application_implementation' in e for e in inventory_errors(cfg,source_inventory(self.root,cfg))))

    def test_omitting_note_from_capture_fails_static_and_actual_recording(self):
        next(n for n in self.model['nodes'] if n['id']=='upload')['capture']['in']={}
        self.assertTrue(any('parameter_without_capture' in e for e in static_errors(self.plan,self.model,self.index)))
        result=runtime_errors(self.plan,self.model,self.run_program())
        self.assertTrue(any('feature_value_mismatch' in e for e in result['errors']))

    def test_declaring_a_field_does_not_prove_it_was_captured(self):
        payload=self.run_program()
        event=next(e for e in payload['runs'][0]['events'] if e['node']=='upload')
        event['inputs'].pop('note')
        errors=runtime_errors(self.plan,self.model,payload)['errors']
        self.assertTrue(any('feature_field_not_observed' in e for e in errors))

    def test_modified_note_is_detected_by_independent_saved_value(self):
        payload=self.run_program()
        next(e for e in payload['runs'][0]['events'] if e['node']=='upload')['inputs']['note']='wrong'
        self.assertTrue(any('feature_value_mismatch' in e for e in runtime_errors(self.plan,self.model,payload)['errors']))

    def test_missing_notify_probe_cannot_be_replaced_by_other_events(self):
        payload=self.run_program()
        payload['runs'][0]['events']=[e for e in payload['runs'][0]['events'] if e['node']!='notify']
        self.assertTrue(any('feature_event_missing' in e for e in runtime_errors(self.plan,self.model,payload)['errors']))

    def test_coverage_cannot_be_weakened_to_make_a_gate_pass(self):
        after=copy.deepcopy(self.plan)
        after['features'][1]['parameters']=[]
        self.assertTrue(protected_errors(self.plan,after))

    def test_parameter_cannot_be_labelled_context_arbitrarily(self):
        self.plan['features'][1]['parameters'][0]={'source':'app.py::upload','name':'note','policy':'context','reason':'optional'}
        self.assertTrue(any('invalid_context_parameter' in e for e in static_errors(self.plan,self.model,self.index)))

    def test_deleting_an_output_field_is_a_weakened_obligation(self):
        changed=copy.deepcopy(self.model)
        next(n for n in changed['nodes'] if n['id']=='notify')['capture']={}
        self.assertTrue(protected_captures(self.model,changed))

    def test_explicit_source_move_preserves_parameter_obligations(self):
        after=copy.deepcopy(self.plan)
        f=after['features'][0];f['sources']=['new.py::login']
        for p in f['parameters']:p['source']='new.py::login'
        self.assertEqual(protected_errors(self.plan,after,{'app.py::login':{'path':'new.py','symbol':'login'}}),[])

    def test_reclassification_does_not_remove_the_old_runtime_requirement(self):
        after=copy.deepcopy(self.plan)
        after['features']=[f for f in after['features'] if f['id']!='login']
        after['support']['app.py::login']={'node':'upload','reason':'helper'}
        self.assertTrue(protected_errors(self.plan,after))

    def test_declared_shape_errors_are_diagnostics(self):
        self.assertTrue(static_errors({'schema':'bo-implementation/v1','features':['wrong']},self.model,self.index))

    def test_installed_skill_is_not_part_of_application_source(self):
        tool=self.root/'.agents/skills/vibelens/helper.py'
        tool.parent.mkdir(parents=True);tool.write_text('def helper(): return 1\n',encoding='utf-8')
        inventory=source_inventory(self.root,{'source_scope':{'roots':['.']}})
        self.assertEqual(set(inventory['files']),{'app.py'})

    def test_canonical_and_generated_bridge_hash_the_same_execution_tools(self):
        canonical=self.root/'canonical';runtime=self.root/'runtime';module=self.root/'bo_stategraph'
        for p in [canonical,runtime,module]:p.mkdir()
        for source,target in CORE.items():
            data=('# actual shared implementation '+source+'\n').encode()
            (canonical/source).write_bytes(data);(module/target).write_bytes(data)
            (runtime/source).write_bytes(bridge_source(source))
        cfg={'stategraph':{'module':'bo_stategraph/__init__.py'}}
        self.assertEqual(tool_fingerprints(self.root,cfg,canonical),tool_fingerprints(self.root,cfg,runtime))
        with (runtime/'bo_stategraph.py').open('a') as f:f.write('\n# local change\n')
        self.assertNotEqual(tool_fingerprints(self.root,cfg,canonical),tool_fingerprints(self.root,cfg,runtime),'edited bridges cannot be normalized away')
        (runtime/'bo_stategraph.py').write_bytes(bridge_source('bo_stategraph.py'))
        (runtime/'__init__.py').write_text('"""Project package."""\n',encoding='utf-8')
        self.assertEqual(tool_fingerprints(self.root,cfg,canonical),tool_fingerprints(self.root,cfg,runtime))
        (runtime/'__init__.py').write_text('changed = True\n',encoding='utf-8')
        self.assertNotEqual(tool_fingerprints(self.root,cfg,canonical),tool_fingerprints(self.root,cfg,runtime),'nonempty package initialization remains versioned')


if __name__=='__main__': unittest.main()
