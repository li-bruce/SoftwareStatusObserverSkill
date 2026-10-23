"""Round-one regressions: old audit failures and new independent-module boundaries."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import subprocess
import shutil
import sys
import tempfile
import time
import unittest
import zipfile
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'skills/business-observer/scripts'))
from bo_stategraph import BOStateGraph, bo_validate_export, bo_digest
from bo_contracts import active_states, value_errors
from statechart_contract import validate_chart
from change_sync import assess_observations, config, snapshot, structural_errors
from bo_sync import source_inventory, maintenance_task
from bo_retention import EventHistory
from view_preferences import Preferences, PreferenceConflict
from recording_session import Recordings
from mapping_contract import assess as assess_mapping
from test_stategraph_module import model
from bo_upgrade import plan as upgrade_plan, apply as upgrade_apply


class RefactorTests(unittest.TestCase):
    def setUp(self):
        folder=ROOT/'.validation/refactor-tests';folder.mkdir(parents=True,exist_ok=True)
        self.temp=tempfile.TemporaryDirectory(dir=folder);self.root=Path(self.temp.name)
    def tearDown(self): self.temp.cleanup()

    def test_begin_rejects_incomplete_source_inventory_before_writing_baseline(self):
        import change_sync
        from code_structure import scan
        # A real syntax failure must not become a supposedly complete baseline.
        (self.root/'broken.py').write_text('def broken(:\n', encoding='utf-8')
        index = scan(self.root, ['broken.py'])
        self.assertTrue(index['errors'])
        initial = {'id':'candidate', 'structure':index, 'model':{}}
        cfg = {'manifest':'manifest.json'}
        args = ['change_sync.py', 'begin', '--root', str(self.root),
                '--change', '.stategraph/new', '--request', 'Repair source mapping']
        with patch.object(sys, 'argv', args), patch.object(change_sync, 'config', return_value=cfg), \
             patch.object(change_sync, 'snapshot', return_value=initial):
            with self.assertRaisesRegex(ValueError, 'source scan is incomplete'):
                change_sync.main()
        self.assertFalse((self.root/'.stategraph/active.json').exists())
        self.assertFalse((self.root/'.stategraph/new/baseline.json').exists())

    def test_upgrade_normalizes_windows_keys_and_retains_modified_file_checks(self):
        upgrade_apply(self.root, runtime='tools\\observer', viewers=['static\\graph'])
        metadata = self.root/'bo_stategraph/runtime-version.json'
        doc = json.loads(metadata.read_text(encoding='utf-8'))
        self.assertIn('static/graph/viewer.js', doc['files'])
        self.assertFalse(any('\\' in key for key in doc['files']))
        # An old manifest with mixed separators migrates without retiring live files.
        doc['files'] = {key.replace('/', '\\', 1): value for key,value in doc['files'].items()}
        metadata.write_text(json.dumps(doc), encoding='utf-8')
        proposal = upgrade_plan(self.root, runtime='tools/observer', viewers=['static/graph'])
        self.assertTrue(proposal['valid'])
        self.assertEqual(proposal['retired_files'], [])
        self.assertEqual(proposal['changes'], [])
        (self.root/'static/graph/viewer.js').write_text('// user modification', encoding='utf-8')
        self.assertIn('static/graph/viewer.js', upgrade_plan(self.root, runtime='tools/observer', viewers=['static/graph'])['conflicts'])
        with self.assertRaises(ValueError): upgrade_plan(self.root, runtime='..\\outside')

    def test_validator_parity_for_invalid_target_guard_cycle_and_schema(self):
        mutations=[lambda m:m['machine']['transitions'][0].update(dest='missing'),
                   lambda m:m['machine']['transitions'][0].update(conditions='missing'),
                   lambda m:m['nodes'][0].update(parent='waiting'),
                   lambda m:m.update(schema_version=3)]
        for mutation in mutations:
            m=model();mutation(m)
            for check in (lambda:validate_chart(m),lambda:BOStateGraph(m,build_id='b')):
                with self.assertRaises(ValueError): check()

    def test_boolean_is_not_integer_enum_or_number(self):
        for spec in ({'type':'enum','values':[1]},{'type':'integer'},{'type':'number'}):
            self.assertTrue(value_errors(True,spec,'value'))
        self.assertFalse(value_errors(1,{'type':'enum','values':[1]},'value'))

    def test_resource_declaration_uses_the_same_validator(self):
        m=json.loads((ROOT/'examples/delivery/observer_generated/behavior.json').read_text(encoding='utf-8'))
        m['machine']['execution']['resources'][0]['min']=-1
        for check in (lambda:validate_chart(m),lambda:BOStateGraph(m,build_id='b')):
            with self.assertRaisesRegex(ValueError,'capacity'):check()

    def test_actual_negative_resource_is_kept_and_flagged(self):
        m=json.loads((ROOT/'examples/delivery/observer_generated/behavior.json').read_text(encoding='utf-8'))
        graph=BOStateGraph(m,build_id='b')
        config={'attempt':'a','phase':'checking','state_revision':1,'run_build_id':'b',
                'activities':{'checksum':'running','privacy':'pending'},
                'resources':{'workers':{'capacity':1,'available':-1,'holders':['checksum']}},
                'join':{'state':'waiting','pending':['checksum','privacy']},'revision':0,'journal':[],'param_version':1}
        result=graph.bo_instances({'configurations':[config]})[0]
        self.assertEqual(result['status'],'mismatch')
        self.assertEqual(result['observed']['configuration']['resources']['workers']['available'],-1)

    def test_required_checks_cannot_silently_disappear(self):
        from change_sync import review_errors
        base={'intent':{'requirements':[]},'acceptance':{'checks':[]},'verification_contract':{'probe_modes':['on','off','fault'],'test_commands':[['python','test.py']]}}
        current={**deepcopy(base),'id':'x','verification_contract':{'probe_modes':['on'],'test_commands':[]}}
        review={'candidate_id':'x','decisions':{p:{'action':'unchanged','reason':'fixture'} for p in ('business','state_machine','abstraction','probes')}}
        (self.root/'review.json').write_text(json.dumps(review))
        failures=review_errors(self.root,base,current,{'unmapped_changed_symbols':[]})
        self.assertEqual({f['weakened_verification'] for f in failures},{'probe_modes','test_commands'})

    def move_fixture(self):
        from code_structure import scan
        old={'path':'old.py','symbol':'commit'};new={'path':'new.py','symbol':'commit'}
        for path in ('old.py','new.py'):
            (self.root/path).write_text('def commit(trace):\n    trace.record("result", "commit")\n    return True\n')
        base={'intent':{'requirements':[{'id':'R1','text':'Commit once'}]},'acceptance':{'checks':[]},
              'structure':scan(self.root,['old.py']), 'model':{'nodes':[{'id':'result','source':old}]},
              'verification_contract':{'required_probes':[{'symbol':'old.py::commit','node':'result','phase':'commit'}]},
              'whitebox':{'rules':[{'id':'one','requirement':'R1','node':'result','source':old,'parameters':{'trace':'object'}}],
                          'checks':[{'id':'commit-once','rule':'one','fields':[{'path':['outputs','count'],'equals':1}]}]}}
        current=deepcopy(base);current.update(id='candidate',structure=scan(self.root,['new.py']))
        current['model']['nodes'][0]['source']=new
        current['verification_contract']['required_probes'][0]['symbol']='new.py::commit'
        current['whitebox']['rules'][0]['source']=new
        review={'candidate_id':'candidate','source_moves':[{'from':old,'to':new,'reason':'Move the existing implementation; keep probe and independent assertions.'}],
                'decisions':{p:{'action':'updated','reason':'source relocation'} for p in ('business','state_machine','abstraction','probes')}}
        return base,current,review

    def move_errors(self,base,current,review):
        from change_sync import review_errors
        (self.root/'review.json').write_text(json.dumps(review))
        return review_errors(self.root,base,current,{'unmapped_changed_symbols':[]})

    def test_explicit_source_move_preserves_probe_and_whitebox_identity(self):
        base,current,review=self.move_fixture()
        self.assertTrue(self.move_errors(base,current,{**review,'source_moves':[]}))
        self.assertEqual(self.move_errors(base,current,review),[])
        self.assertEqual(base['whitebox']['rules'][0]['source']['path'],'old.py','baseline is immutable')

    def test_source_move_cannot_weaken_assertions_or_remove_probe(self):
        base,current,review=self.move_fixture()
        for mutate in (lambda c:c['whitebox']['checks'][0]['fields'][0].update(equals=0),
                       lambda c:c['whitebox']['rules'][0]['parameters'].clear(),
                       lambda c:c['verification_contract']['required_probes'][0].update(phase='return'),
                       lambda c:c['verification_contract'].update(required_probes=[])):
            changed=deepcopy(current);mutate(changed)
            self.assertTrue(self.move_errors(base,changed,review))

    def test_source_move_rejects_unknown_ambiguous_and_lost_graph_bindings(self):
        base,current,review=self.move_fixture()
        bad=deepcopy(review);bad['source_moves'][0]['to']['symbol']='unknown'
        self.assertTrue(self.move_errors(base,current,bad))
        bad=deepcopy(review);bad['source_moves']*=2
        self.assertTrue(self.move_errors(base,current,bad))
        current['model']['nodes']=[]
        self.assertTrue(self.move_errors(base,current,review))

    def hierarchical(self):
        m=model();m['machine'].update(states=[{'name':'checking','children':['content','index']},'done'],
            values=['checking_content','checking_index','done'],initial='checking_content',context={},guards={},
            transitions=[{'source':'checking','trigger':'finish','dest':'done'}])
        m['nodes']=[{'id':s,'kind':'state','layer':'state','value':s} for s in m['machine']['values']];m['edges']=[]
        return m

    def test_real_parent_transition_matches_engine(self):
        from transitions.extensions import HierarchicalMachine
        from types import SimpleNamespace
        m=self.hierarchical();holder=SimpleNamespace();chart=m['machine']
        HierarchicalMachine(holder,states=chart['states'],transitions=chart['transitions'],initial=chart['initial'],auto_transitions=False)
        graph=BOStateGraph(m,build_id='b')
        args=dict(instance_id='a',context={},build_id='b')
        graph.bo_observe(**args,state=holder.state,revision=0,evidence_id='s0')
        holder.finish()
        result=graph.bo_observe(**args,state=holder.state,revision=1,evidence_id='s1',event='finish')
        self.assertEqual(result['status'],'observed')

    def test_child_handler_precedes_parent_but_false_guard_falls_back(self):
        m=self.hierarchical();m['machine']['guards']={'child_allowed':'actual'}
        m['machine']['transitions'].append({'source':'checking_content','trigger':'finish','dest':'checking_index','conditions':'child_allowed'})
        graph=BOStateGraph(m,build_id='b')
        for fact,expected in ((True,'shadowed'),(False,'matched')):
            result=graph.bo_candidates('checking_content','finish',guards={'child_allowed':fact})
            self.assertEqual(result['candidates'][0]['result'],expected)

    def test_parallel_and_exclusive_active_configurations(self):
        chart={'states':[{'name':'work','parallel':[{'name':'a','children':['running','done']},{'name':'b','children':['running','done']}]}]}
        active=active_states(chart,['work_a_running','work_b_done'])
        self.assertTrue({'work','work_a','work_b'}<=active)
        for bad in (['work_a_running'],['work_a_running','work_a_done','work_b_running']):
            with self.assertRaises(ValueError): active_states(chart,bad)
        chart['states'][0]['history']=True
        with self.assertRaises(ValueError): active_states(chart,['work_a_running','work_b_running'])

    def test_instance_query_and_export_share_actual_provider(self):
        graph=BOStateGraph(model(),build_id='b')
        machine={'configurations':[{'attempt':'a','phase':'running','state_revision':2,'run_build_id':'b','context':{'slots':1}}]}
        graph.bo_bind_instances(lambda:deepcopy(machine))
        self.assertEqual(graph.bo_instances(),graph.bo_export(runtime={'machine':machine})['instances'])
        machine['configurations'][0]['phase']='done'
        self.assertEqual(graph.bo_instances()[0]['observed']['state'],'done')
        with self.assertRaises(ValueError): graph.bo_observe('a',state='done',context={},revision=3,evidence_id='e',build_id='b')
        machine['configurations'][0].pop('state_revision')
        self.assertEqual(graph.bo_instances()[0]['status'],'partial')

    def test_new_file_is_discovered_without_any_graph_node(self):
        cfg={'code_files':['app.py'],'watch_files':[],'source_scope':{'roots':['.']}}
        (self.root/'app.py').write_text('def run(): return 1\n')
        before=source_inventory(self.root,cfg)
        (self.root/'new_entry.py').write_text('def delete(): return True\n')
        task=maintenance_task(self.root,cfg,before)
        self.assertEqual(task['unregistered_files'],['new_entry.py'])
        self.assertEqual(task['status'],'needs_update')
        cfg['source_scope']['exclude']={'new_entry.py':''}
        with self.assertRaises(ValueError):source_inventory(self.root,cfg)

    def test_project_export_cannot_substitute_a_different_protocol_or_instances(self):
        with self.assertRaisesRegex(ValueError,'export schema'):
            bo_validate_export({'definition':{},'instances':[]})
        graph=BOStateGraph(model(),build_id='b')
        machine={'configurations':[{'attempt':'a','phase':'running','state_revision':2,'run_build_id':'b','context':{'slots':1}}]}
        export=graph.bo_export(runtime={'machine':machine})
        self.assertEqual(bo_validate_export(export),export)
        export['instances']=[]
        export['sha256']=bo_digest({k:v for k,v in export.items() if k!='sha256'})
        with self.assertRaisesRegex(ValueError,'instances differ'):
            bo_validate_export(export)

    def test_scanning_does_not_acknowledge_pending_change(self):
        cfg={'code_files':['app.py'],'watch_files':[]}
        (self.root/'app.py').write_text('x=1\n');(self.root/'sync.json').write_text(json.dumps(cfg))
        command=[sys.executable,'-B','-X','utf8',str(ROOT/'skills/business-observer/scripts/bo_sync.py'),'scan','--root',str(self.root)]
        for _ in range(2):
            output=subprocess.run(command,capture_output=True,text=True,encoding='utf-8',check=True)
            self.assertEqual(json.loads(output.stdout)['status'],'needs_update')

    def test_empty_scope_and_disabled_mapping_cannot_bypass_completion(self):
        cfg=json.loads((ROOT/'examples/delivery/sync.json').read_text(encoding='utf-8'))
        for update in ({'source_scope':{}},{'source_scope':{'roots':['.'],'require_symbol_classification':False}},
                       {'require_mapping_witnesses':False}):
            (self.root/'sync.json').write_text(json.dumps({**cfg,**update}))
            with self.assertRaises(ValueError):config(self.root,'sync.json')
        for roots in ([], '', [None]):
            with self.assertRaises(ValueError):source_inventory(self.root,{'source_scope':{'roots':roots}})

    def test_watcher_refreshes_when_registration_or_acceptance_changes(self):
        cfg={'code_files':['app.py'],'watch_files':[],
             'source_scope':{'roots':['.'],'require_symbol_classification':True}}
        (self.root/'app.py').write_text('def run(): return 1\n')
        (self.root/'new_entry.py').write_text('def submit(): return 2\n')
        (self.root/'sync.json').write_text(json.dumps(cfg))
        log=self.root/'watch.log'
        with log.open('w',encoding='utf-8') as stream:
            process=subprocess.Popen([sys.executable,'-B','-X','utf8',
                str(ROOT/'skills/business-observer/scripts/bo_sync.py'),'watch','--root',str(self.root),'--interval','.1'],
                stdout=stream,stderr=stream)
            def wait_for(predicate):
                deadline=time.monotonic()+8
                while time.monotonic()<deadline:
                    path=self.root/'.stategraph/maintenance.json'
                    if path.exists():
                        value=json.loads(path.read_text(encoding='utf-8'))
                        if predicate(value):return value
                    time.sleep(.05)
                self.fail('Watcher did not update: '+log.read_text(encoding='utf-8'))
            try:
                first=wait_for(lambda v:v['unregistered_files']==['new_entry.py'])
                (self.root/'sync.json').write_text('{')
                wait_for(lambda v:bool(v.get('errors')))
                self.assertIsNone(process.poll())
                cfg['code_files'].append('new_entry.py')
                (self.root/'sync.json').write_text(json.dumps(cfg))
                second=wait_for(lambda v:'unregistered_files' in v and not v['unregistered_files'])
                self.assertEqual(first['source_id'],second['source_id'])
                (self.root/'.stategraph/source-baseline.json').write_text(json.dumps(source_inventory(self.root,cfg)))
                wait_for(lambda v:v['status']=='current')
            finally:
                process.terminate();process.wait(timeout=5)

    def copy_project(self):
        project=self.root/'delivery'
        shutil.copytree(ROOT/'examples/delivery',project,
            ignore=shutil.ignore_patterns('scratch','history','dist','.stategraph','.release','__pycache__'))
        return project

    def test_full_project_gate_rejects_an_unregistered_entry(self):
        project=self.copy_project()
        cfg=config(project,'sync.json')
        self.assertEqual(structural_errors(project,cfg,snapshot(project,cfg)),[])
        (project/'new_api.py').write_text('def publish_without_check(): return True\n')
        errors=structural_errors(project,cfg,snapshot(project,cfg))
        self.assertTrue(any(isinstance(error,dict) and error.get('unregistered_source')=='new_api.py' for error in errors),errors)
        # Merely adding the file to the watch list is insufficient for implementation coverage.
        cfg['watch_files'].append('new_api.py')
        errors=structural_errors(project,cfg,snapshot(project,cfg))
        self.assertTrue(any(isinstance(error,dict) and error.get('unregistered_source')=='new_api.py' for error in errors),errors)

    def test_core_package_keeps_execution_and_excludes_personal_views(self):
        project=self.copy_project()
        private=project/'bo_stategraph/config/views/local.json'
        private.parent.mkdir(parents=True,exist_ok=True);private.write_text('{"note":"personal"}')
        result=subprocess.run([sys.executable,'-B','-X','utf8',str(ROOT/'skills/business-observer/scripts/architecture_guard.py'),
            'package','--root',str(project),'--out','dist/core.zip'],capture_output=True,text=True,encoding='utf-8')
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        with zipfile.ZipFile(project/'dist/core.zip') as package:
            self.assertIn('bo_stategraph/workflow.py',package.namelist())
            self.assertNotIn('bo_stategraph/config/views/local.json',package.namelist())
            self.assertFalse(any(name.startswith('integrations/') for name in package.namelist()))

    def test_zero_modes_or_assertions_cannot_pass(self):
        self.assertTrue(assess_observations({}, {'checks':[{}]}, {}, []))
        self.assertTrue(assess_observations({}, {'checks':[]}, {}, ['on']))

    def test_mapping_can_pass_while_business_rule_fails(self):
        from test_assessment_fixes import mapping_fixture
        m,plan,payload=mapping_fixture()
        payload['runs'][0]['observations']={'state':'deleted'}
        contract={'checks':[{'id':'deny','requirement':'R1','case':'case','path':['state'],'equals':'retained'}]}
        self.assertTrue(assess_mapping(payload,required=True,plan=plan,model=m,build_id='b')['valid'])
        self.assertTrue(assess_observations({},contract,payload,['on']))
        payload['mapping_checks'][0]['mapped']='retained'
        self.assertFalse(assess_mapping(payload,required=True,plan=plan,model=m,build_id='b')['valid'])
        self.assertFalse(assess_mapping({},required=True)['valid'])

    def test_preferences_persist_revision_conflict_and_atomic_failure(self):
        a=Preferences(self.root,'p');b=Preferences(self.root,'p');old=b.read()
        value=a.read();value['entries']['business-observer.layout.v2:p']=json.dumps({'focus':'a'})
        saved=a.save(value)
        self.assertEqual(Preferences(self.root,'p').read(),saved)
        with self.assertRaises(PreferenceConflict):b.save(old)
        with patch('view_preferences.os.replace',side_effect=OSError('disk full')):
            with self.assertRaises(OSError):a.save(saved)
        self.assertEqual(a.read(),saved)
        self.assertFalse(list(a.path.parent.glob('*.tmp')))

    def test_retention_is_bounded_and_reports_eviction(self):
        history=EventHistory(path=self.root/'events.jsonl',limits={'memory_events':2,'memory_seconds':20,'log_bytes':120,'log_backups':2})
        for seq in range(12):history.append({'id':str(seq),'seq':seq})
        self.assertEqual([e['seq'] for e in history.snapshot()],[10,11])
        self.assertEqual(history.health()['evicted_events'],10)
        self.assertLessEqual(len(list(self.root.glob('events.jsonl*'))),3)
        self.assertTrue(all(p.stat().st_size<=120 for p in self.root.glob('events.jsonl*')))
        with patch('bo_retention.time.monotonic',return_value=10**12):self.assertEqual(history.snapshot(),[])

    def test_preferences_reject_non_finite_nested_coordinates(self):
        preferences=Preferences(self.root,'p')
        for invalid in ('NaN','Infinity','-Infinity'):
            value=preferences.read()
            value['entries']['business-observer.layout.v2:p']='{"camera":{"scale":'+invalid+'}}'
            with self.assertRaises(ValueError):preferences.save(value)
        self.assertEqual(preferences.read()['revision'],0)

    def test_upgrade_preserves_project_code_and_refuses_unreviewed_changes(self):
        module=self.root/'bo_stategraph';module.mkdir()
        project=module/'workflow.py';project.write_text('PROJECT_EXECUTOR=1\n')
        preferences=module/'config/views/local.json';preferences.parent.mkdir(parents=True);preferences.write_text('{"mine":true}')
        upgrade_apply(self.root,runtime='observer_runtime')
        self.assertEqual(project.read_text(),'PROJECT_EXECUTOR=1\n')
        self.assertEqual(preferences.read_text(),'{"mine":true}')
        self.assertTrue(upgrade_plan(self.root,runtime='observer_runtime')['valid'])
        runtime=self.root/'observer_runtime/bo_contracts.py';runtime.write_text('# local customization\n')
        self.assertFalse(upgrade_plan(self.root,runtime='observer_runtime')['valid'])
        with self.assertRaisesRegex(ValueError,'local runtime edits'):upgrade_apply(self.root,runtime='observer_runtime')
        self.assertEqual(runtime.read_text(),'# local customization\n')

    def test_upgrade_rolls_back_a_partial_copy(self):
        upgrade_apply(self.root,runtime='observer_runtime')
        manifest=self.root/'bo_stategraph/runtime-version.json'
        before=manifest.read_bytes()
        # A new canonical source changes two files, then the second copy fails.
        import shutil
        source=self.root/'candidate';shutil.copytree(ROOT/'skills/business-observer/scripts',source,ignore=shutil.ignore_patterns('__pycache__'))
        for name in ('bo_contracts.py','bo_stategraph.py'):
            p=source/name;p.write_text(p.read_text(encoding='utf-8')+'\n# candidate\n',encoding='utf-8')
        original=shutil.copyfile
        def fail(src,dst):
            if Path(src)==source/'bo_contracts.py':raise OSError('copy failed')
            return original(src,dst)
        with patch('bo_upgrade.shutil.copyfile',side_effect=fail):
            with self.assertRaises(OSError):upgrade_apply(self.root,runtime='observer_runtime',source=source)
        self.assertEqual(manifest.read_bytes(),before)
        self.assertTrue(upgrade_plan(self.root,runtime='observer_runtime')['valid'])

    def test_old_import_paths_share_the_actual_package_and_validator(self):
        upgrade_apply(self.root,runtime='observer_runtime')
        for command in (
            "from observer_runtime.bo_stategraph import BOStateGraph as old; from bo_stategraph import BOStateGraph; assert old is BOStateGraph; from observer_runtime.bo_contracts import validate_chart as old_v; from bo_stategraph.bo_contracts import validate_chart; assert old_v is validate_chart",
            "import sys; sys.path.insert(0,'observer_runtime'); import bo_stategraph; from bo_stategraph.bo_contracts import validate_chart; assert bo_stategraph.validate_chart is validate_chart; assert 'observer_runtime' not in bo_stategraph.__file__"
        ):
            result=subprocess.run([sys.executable,'-B','-c',command],cwd=self.root,capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
        with self.assertRaisesRegex(ValueError,'one Python package'):
            upgrade_plan(self.root,runtime='observer_runtime',module='nested/package')

    def test_recording_keeps_direct_events_after_ui_history_expires(self):
        history=EventHistory(limits={'memory_events':2})
        view={'authority':{'state':'running','basis':{},'parameters':{}},'model':{'nodes':[]},
            'manifest':{'build_id':'b'},'machine':{'configurations':[]},'binding_status':{'status':'current'},
            'health':{'run_id':'r','attempted':0,'enabled':True,'errors':0,'dropped':0},'events':[]}
        def provider():return {**deepcopy(view),'events':history.snapshot()}
        recorder=Recordings(self.root/'records',provider,{},interval=60,event_source=history)
        try:
            ident=recorder.start()['id']
            for seq in range(1,8):
                view['health']['attempted']=seq
                history.append({'id':str(seq),'seq':seq,'run_id':'r','node':'f','attempt':'a'})
            recorder.stop()
            self.assertEqual([e['seq'] for e in recorder.get(ident)['events']],list(range(1,8)))
            self.assertEqual(len(history.snapshot()),2)
        finally:recorder.close()


if __name__=='__main__': unittest.main()
