"""Recording boundary, source identity and failure-isolation regressions."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import tempfile
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).absolute().parents[1]
choices = [ROOT/"skills/business-observer/scripts/recording_session.py",
           ROOT/"observer_runtime/recording_session.py",
           ROOT/"observer_generated/runtime/recording_session.py"]
spec = importlib.util.spec_from_file_location("recording_under_test", next(p for p in choices if p.exists()))
sys.path.insert(0, str(Path(spec.origin).parent))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class RecordingTests(unittest.TestCase):
    def setUp(self):
        scratch = ROOT/"scratch/recording-tests"
        scratch.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=scratch)
        assert Path(self.temp.name).resolve().is_relative_to(scratch.resolve())
        self.view = {
            "authority":{"state":"created","parameters":{"param_version":1,"content":"PRIVATE"},
                         "basis":{"param_version":1,"epoch":0},"effects":[{"content":"PRIVATE"}]},
            "model":{"nodes":[],"presentation":{"recording":{"parameters":["param_version"],"command_fields":["capacity"]}}}, "manifest":{"build_id":"b1"},
            "machine":{"current":"created","configurations":[],"journal":[]},
            "binding_status":{"status":"current"}, "historical":False,
            "health":{"run_id":"producer1","attempted":0,"enabled":True,"errors":0,"dropped":0},
            "events":[],
        }
        self.rec = module.Recordings(self.temp.name,lambda:deepcopy(self.view),
                                     {"core.py":"version_one"},interval=60)

    def tearDown(self):
        self.rec.close()
        self.temp.cleanup()

    def event(self,seq):
        self.view["health"]["attempted"]=seq
        self.view["events"].append({"run_id":"producer1","id":f"e{seq}","seq":seq,
                                   "node":"check","attempt":"a","inputs":{},"outputs":{}})

    def test_start_stop_boundaries_and_bound_source(self):
        self.event(1)
        started=self.rec.start()
        self.assertEqual(self.rec.start()["id"],started["id"])
        self.event(2)
        self.rec.command("run",{"content":"PRIVATE","capacity":1},{"ok":True})
        self.rec.stop()
        self.event(3)
        self.rec.sample()
        saved=self.rec.get(started["id"])
        self.assertEqual([e["seq"] for e in saved["events"]],[2])
        self.assertEqual(saved["sources"],{"core.py":"version_one"})
        self.assertEqual(len(saved["context"]["events"]),1)
        self.assertNotIn("PRIVATE",json.dumps(saved))
        self.assertEqual(saved["commands"][0]["values"],{"capacity":1})
        self.assertEqual(saved["status"],"stopped")
        self.assertEqual(saved["gaps"],[])

    def test_empty_record_does_not_invent_events(self):
        ident=self.rec.start()["id"];self.rec.stop()
        self.assertEqual(self.rec.get(ident)["events"],[])

    def test_exact_runtime_frames_identity_scope_and_selected_values(self):
        self.view['model']['nodes']=[{'id':'printer'}]
        self.view['runtime_frames']={'schema':'stategraph-runtime-frames/v1','frames':[]}
        ident=self.rec.start()['id']
        self.event(1);self.event(2)
        for event in self.view['events']:event['revision']=event['seq']
        first={'event_id':'e1','revision':1,'run_id':'producer1','build_id':'b1',
               'machine':{'current':'printing','state_revision':1,'configurations':[],
                          'shared_resources':{'printer':{'available':0}}},
               'authority':deepcopy(self.view['authority'])}
        self.view['runtime_frames']['frames']=[first,{**first,'event_id':'e2','revision':2,'run_id':'other'},
                                               {**first,'event_id':'outside'}]
        self.rec.sample()
        # An already accepted historical fact cannot be overwritten later.
        first['machine']['current']='future'
        self.rec.stop();saved=self.rec.get(ident)
        self.assertEqual(len(saved['runtime_frames']['frames']),1)
        self.assertEqual(saved['runtime_frames']['frames'][0]['machine']['current'],'printing')
        self.assertNotIn('PRIVATE',json.dumps(saved['runtime_frames']))
        self.assertTrue(any('different process, build, or revision' in gap for gap in saved['gaps']))
        self.assertTrue(any('Conflicting runtime snapshots' in gap for gap in saved['gaps']))

    def test_process_change_interrupts_without_joining_events(self):
        ident=self.rec.start()["id"]
        self.view["health"]["run_id"]="producer2"
        self.rec.sample()
        saved=self.rec.get(ident)
        self.assertEqual(saved["status"],"interrupted")
        self.assertTrue(saved["gaps"])
        self.assertIsNone(self.rec.active)

    def test_new_build_clears_current_list_and_rejects_old_replay(self):
        ident=self.rec.start()['id']; self.rec.stop()
        original=(Path(self.temp.name)/(ident+'.json')).read_bytes()
        self.view['manifest']['build_id']='b2'
        self.assertEqual(self.rec.list()['recordings'],[])
        with self.assertRaisesRegex(ValueError,'earlier graph version'):self.rec.get(ident)
        # Private original evidence is not rewritten or recursively deleted.
        self.assertEqual((Path(self.temp.name)/(ident+'.json')).read_bytes(),original)
        new=self.rec.start()['id']; self.rec.stop()
        self.assertEqual([v['id'] for v in self.rec.list()['recordings']],[new])

    def test_graph_only_change_interrupts_capture_and_clears_list(self):
        ident=self.rec.start()['id']
        self.view['model']['nodes'].append({'id':'new-feature'})
        self.assertIsNone(self.rec.list()['active'])
        self.assertEqual(self.rec.list()['recordings'],[])
        self.assertEqual(self.rec.cached[ident]['status'],'interrupted')
        new=self.rec.start()['id']; self.assertNotEqual(new,ident)

    def test_same_graph_restart_retains_current_recordings(self):
        ident=self.rec.start()['id']; self.rec.stop(); self.rec.close()
        self.view['health']['run_id']='producer2'
        self.rec=module.Recordings(self.temp.name,lambda:deepcopy(self.view),{},interval=60)
        self.assertEqual([v['id'] for v in self.rec.list()['recordings']],[ident])
        self.assertEqual(self.rec.get(ident)['status'],'stopped')

    def test_old_records_cannot_starve_current_list_limit(self):
        ident=self.rec.start()['id']; self.rec.stop()
        value=self.rec.get(ident)
        for i in range(51):
            obsolete=deepcopy(value); obsolete['id']=f'{i:032x}'
            obsolete['build_id']='old'; obsolete['context']['manifest']['build_id']='old'
            self.rec._write(obsolete)
        self.assertEqual([v['id'] for v in self.rec.list()['recordings']],[ident])

    def test_sequence_and_sink_gaps_visible(self):
        ident=self.rec.start()["id"]
        self.event(2);self.view["health"]["errors"]=1;self.rec.stop()
        self.assertGreaterEqual(len(self.rec.get(ident)["gaps"]),2)

    def test_save_failure_does_not_raise_into_business(self):
        ident=self.rec.start()["id"];self.event(1)
        with patch.object(self.rec,"_write",side_effect=OSError("disk full")):
            self.rec.command("run",{},{"ok":True})
            self.rec.sample()
        saved=self.rec.get(ident)
        self.assertEqual(saved["commands"][0]["result"],{"ok":True})
        self.assertEqual(saved["status"],"interrupted")
        self.assertIn("disk full",saved["gaps"][0])

    def test_limits_and_missing_record_validation(self):
        self.rec.max_events=1
        ident=self.rec.start()["id"];self.event(1);self.event(2);self.rec.sample()
        saved=self.rec.get(ident)
        self.assertEqual(len(saved["events"]),1)
        self.assertEqual(saved["status"],"limited")
        with self.assertRaises(ValueError):self.rec.get("../core.py")
        self.view["binding_status"]["status"]="stale"
        with self.assertRaises(ValueError):self.rec.start()

    def test_restart_marks_unfinished_record(self):
        ident=self.rec.start()["id"]
        # Simulate abrupt termination from the last saved on-disk state.
        self.rec.active=None
        self.rec.close()
        self.rec=module.Recordings(self.temp.name,lambda:deepcopy(self.view),{},interval=60)
        self.assertEqual(self.rec.get(ident)["status"],"interrupted")

    def test_memory_cache_bounded_and_disk_history_remains(self):
        first=None
        for _ in range(12):
            ident=self.rec.start()["id"];first=first or ident;self.rec.stop()
        self.assertLessEqual(len(self.rec.cached),8)
        self.assertEqual(len(self.rec.list()["recordings"]),12)
        self.assertEqual(self.rec.get(first)["status"],"stopped")

    def focused(self):
        self.view['model']={'nodes':[{'id':'flow'}, {'id':'check','parent':'flow'},
            {'id':'field','parent':'check'}, {'id':'other','parent':'flow'}],
            'machine':{'execution':{'parent':'flow'}}}
        calls=[]
        self.rec.bo_scope_setter=calls.append
        return calls

    def test_focused_descendants_boundary_and_stop_restore(self):
        calls=self.focused()
        ident=self.rec.start(scope={'mode':'focused','roots':['check']})['id']
        self.assertEqual(calls[-1],['check','field','flow'])
        self.event(1);self.event(2);self.view['events'][-1]['node']='other'
        self.rec.stop();value=self.rec.get(ident)
        self.assertEqual([e['seq'] for e in value['events']],[1])
        self.assertEqual(value['scope_excluded'],1)
        self.assertEqual(value['gaps'],[])
        self.assertEqual(value['capture']['boundary_nodes'],['flow'])
        self.assertIsNone(calls[-1])

    def test_focused_invalid_unavailable_and_save_failure_restore(self):
        with self.assertRaises(ValueError):self.rec.start(scope={'mode':'focused','roots':['check']})
        calls=self.focused()
        for roots in ([],['missing'],['check',None]):
            with self.assertRaises(ValueError):self.rec.start(scope={'mode':'focused','roots':roots})
        with patch.object(self.rec,'_write',side_effect=OSError('disk full')):
            with self.assertRaises(OSError):self.rec.start(scope={'mode':'focused','roots':['check']})
        self.assertIsNone(calls[-1]);self.assertIsNone(self.rec.active)

    def test_focus_skips_builder_and_does_not_leak_across_stop(self):
        probe_path=Path(spec.origin).with_name('semantic_probe.py')
        probe_spec=importlib.util.spec_from_file_location('focused_probe',probe_path)
        probe=importlib.util.module_from_spec(probe_spec);probe_spec.loader.exec_module(probe)
        facts=[];built=[]
        pins=probe.Pins({'revision':1,'nodes':[{'id':n,'capture':{'out':{'ok':'boolean'}}} for n in ('a','b')]},'b',sink=lambda text:facts.append(json.loads(text)))
        try:
            pins.bo_set_scope(['a']);trace=pins.attempt('test')
            def payload():built.append(True);return {'outputs':{'ok':True}}
            self.assertIsNone(trace.record('b','return',{},payload))
            self.assertEqual(built,[])
            trace.record('a','return',{},payload);pins.bo_set_scope(None);trace.record('b','return',{},payload);pins.flush()
            self.assertEqual([e['node'] for e in facts],['a','b'])
            self.assertEqual(len(built),2);self.assertEqual(pins.health()['filtered'],1)
        finally:pins.close()


if __name__=="__main__":
    unittest.main()
