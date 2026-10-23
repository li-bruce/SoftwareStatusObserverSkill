"Check complete internal state, resource waiting, joins, and run isolation."
from copy import deepcopy
import json
from pathlib import Path
import sys
import threading
import unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from bo_stategraph.workflow import ActivityExecution,advance
from app.checks import run_checks
from app.service import Delivery
from app.store import Store
from observer_generated.runtime.execution_contract import validate_configuration,validate_execution_graph


class ExecutionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.model=json.loads((ROOT/'observer_generated/behavior.json').read_text(encoding='utf-8'))

    def test_capacity_must_be_one_or_two(self):
        "Boolean, fractional, zero, and out-of-range capacities must be rejected."
        for value in (0,3,True,1.0,'2'):
            with self.assertRaises(ValueError):ActivityExecution(value)

    def test_all_internal_states_exist_before_work_starts(self):
        state=ActivityExecution().snapshot()
        self.assertEqual(state['activities'],{'checksum':'pending','privacy':'pending'})
        self.assertEqual(state['join']['pending'],['checksum','privacy'])
        self.assertEqual(state['resources']['workers']['available'],2)

    def test_lifecycle_cannot_skip_unfinished_checks(self):
        execution=ActivityExecution(attempt='A',param_version=3)
        with self.assertRaises(ValueError):advance('checking','checked',execution.snapshot(),attempt='A',param_version=3)
        result=run_checks("Public sample",execution=execution)
        self.assertEqual(advance('checking','checked',result['execution'],attempt='A',param_version=3),'ready')
        for attempt,version in [('B',3),('A',4)]:
            with self.assertRaises(ValueError):advance('checking','checked',result['execution'],attempt=attempt,param_version=version)

    def test_cannot_join_or_finish_before_start(self):
        execution=ActivityExecution()
        with self.assertRaises(ValueError):execution.join()
        with self.assertRaises(ValueError):execution.finish('privacy',True)
        execution.start('checksum')
        with self.assertRaises(ValueError):execution.start('checksum')
        execution.finish('checksum',True)
        with self.assertRaises(ValueError):execution.join()

    def test_two_slots_allow_both_checks_to_be_running(self):
        barrier=threading.Barrier(2)
        result=run_checks("Public sample",task_hook=lambda _:barrier.wait(3))
        self.assertTrue(result['passed'])
        self.assertTrue(any(set(e['after']['activities'].values())=={'running'} for e in result['execution']['journal']))
        self.assertEqual(result['execution']['resources']['workers']['available'],2)

    def test_one_slot_waits_until_the_first_check_returns_it(self):
        waiting=threading.Event();frames=[];lock=threading.Lock();first=[True]
        def progress(event,state):
            frames.append(state)
            if event=='wait':waiting.set()
        def hook(_):
            with lock:initial=first[0];first[0]=False
            if initial:self.assertTrue(waiting.wait(3),"The second check must report waiting for a slot")
        result=run_checks("Public sample",capacity=1,progress=progress,task_hook=hook)
        self.assertTrue(waiting.is_set());self.assertTrue(result['passed'])
        self.assertTrue(any(set(s['activities'].values())=={'running','waiting'} for s in frames))
        self.assertTrue(all(list(s['activities'].values()).count('running')<=1 for s in frames))
        self.assertEqual(result['execution']['resources']['workers']['available'],1)
        # The renderer test reads these actual state updates, not a hand-drawn route.
        state={**result['execution'],'phase':'completed','disposition':'current'}
        fixture={'model':self.model,'events':[],'manifest':{'bindings':{},'build_id':'test'},
                 'machine':{'current':'completed','journal':[],'configurations':[state]},'binding_status':{'status':'current'},
                 'authority':{'basis':{'param_version':1},'parameters':{'attempt':'direct','param_version':1,'executions':[state]}}}
        (ROOT/'scratch/graph-fixture.json').write_text(json.dumps(fixture,ensure_ascii=False),encoding='utf-8')

    def test_worker_error_returns_its_slot_and_blocks_delivery(self):
        def hook(activity):
            if activity=='checksum':raise OSError("Test check failure")
        result=run_checks("Public sample",capacity=1,task_hook=hook)
        self.assertFalse(result['passed']);self.assertEqual(result['execution']['activities']['checksum'],'failed')
        self.assertEqual(result['execution']['resources']['workers']['available'],1)
        self.assertEqual(result['execution']['join']['state'],'rejected')

    def test_sensitive_marker_is_a_rejected_result_not_a_running_check(self):
        result=run_checks("SECRET: synthetic test content")
        self.assertEqual(result['execution']['activities']['privacy'],'rejected')
        self.assertEqual(result['execution']['join']['state'],'rejected')
        self.assertFalse(result['passed'])

    def test_a_return_value_cannot_replace_actual_activity_completion(self):
        store=Store();app=Delivery(store);app.command('grant',id='G',expires=200)
        app.checker=lambda *args,**kw:{'passed':True,'checksum':'fake','safe':True,'tasks':{}}
        try:
            result=app.execute();self.assertEqual(result['state'],'failed');self.assertEqual(result['effects'],[])
            self.assertEqual(set(result['execution']['activities'].values()),{'cancelled'})
        finally:store.close()

    def test_every_running_instance_remains_queryable_after_edit(self):
        "Old and new runs each retain two activities; old completion cannot overwrite new state."
        store=Store();app=Delivery(store);app.command('grant',id='G1',expires=200)
        barriers={'public sample':threading.Barrier(3),"New content":threading.Barrier(3)}
        gates={k:threading.Event() for k in barriers};errors=[]
        def checker(content,**kwargs):
            def hook(_):barriers[content].wait(4);gates[content].wait(5)
            return run_checks(content,task_hook=hook,**kwargs)
        app.checker=checker
        def prepare():
            try:app.prepare()
            except Exception as exc:errors.append(str(exc))
        old=threading.Thread(target=prepare);new=None;old.start()
        try:
            barriers['public sample'].wait(4)
            old_id=store.snapshot()['attempt']
            app.command('edit',content="New content");app.command('grant',id='G2',expires=200)
            new=threading.Thread(target=prepare);new.start();barriers["New content"].wait(4)
            current=store.snapshot();self.assertEqual(len(current['executions']),2)
            self.assertEqual(sum(list(r['activities'].values()).count('running') for r in current['executions']),4)
            self.assertEqual(current['executions'][0]['attempt'],old_id)
            self.assertEqual(current['executions'][0]['disposition'],'superseded')
            self.assertNotEqual(current['attempt'],old_id)
            for run in current['executions']:self.assertTrue(validate_configuration(self.model,run)['valid'])
            gates['public sample'].set();old.join(5)
            self.assertFalse(old.is_alive());self.assertEqual(store.snapshot()['state'],'checking')
            self.assertEqual([r['attempt'] for r in store.snapshot()['executions']],
                             [r['attempt'] for r in current['executions']],
                             "State updates must not reorder the run list")
            self.assertEqual(set(store.snapshot()['execution']['activities'].values()),{'running'})
            gates["New content"].set();new.join(5)
            self.assertFalse(new.is_alive());self.assertEqual(errors,[])
            result=app.commit();self.assertEqual([a['version'] for a in result['effects']],[2])
            self.assertEqual(len(result['executions']),2)
        finally:
            for gate in gates.values():gate.set()
            old.join(5)
            if new:new.join(5)
            store.close()

    def test_old_worker_error_cannot_fail_a_new_successful_run(self):
        store=Store();app=Delivery(store);app.command('grant',id='G1',expires=200)
        started=threading.Event();release=threading.Event();errors=[]
        def checker(content,**kwargs):
            if content=='public sample':started.set();release.wait(5);raise OSError("Old check failed")
            return run_checks(content,**kwargs)
        app.checker=checker
        def old_run():
            try:app.prepare()
            except Exception as exc:errors.append(str(exc))
        old=threading.Thread(target=old_run);old.start()
        try:
            self.assertTrue(started.wait(3));app.command('edit',content="New content");app.command('grant',id='G2',expires=200)
            self.assertEqual(app.execute()['state'],'completed')
            release.set();old.join(5);self.assertEqual(errors,[]);self.assertEqual(store.snapshot()['state'],'completed')
        finally:release.set();old.join(5);store.close()

    def test_graph_uses_the_actual_activity_and_resource_ids(self):
        self.assertTrue(validate_execution_graph(self.model)['valid'])
        broken=deepcopy(self.model)
        edge=next(e for e in broken['edges'] if e['type']=='resource');edge['units']=2
        with self.assertRaises(ValueError):validate_execution_graph(broken)

    def test_old_execute_cannot_submit_a_new_version_prepared_by_someone_else(self):
        "An old check-and-commit request cannot commit a newer check-only run."
        store=Store();app=Delivery(store);app.command('grant',id='G1',expires=200)
        started=threading.Event();release=threading.Event();errors=[]
        def checker(content,**kwargs):
            if content=='public sample':started.set();release.wait(4)
            return run_checks(content,**kwargs)
        app.checker=checker
        def old_execute():
            try:app.execute()
            except Exception as exc:errors.append(str(exc))
        old=threading.Thread(target=old_execute);old.start()
        try:
            self.assertTrue(started.wait(3));app.command('edit',content="New content");app.command('grant',id='G2',expires=200)
            self.assertEqual(app.prepare()['state'],'ready')
            release.set();old.join(5);self.assertEqual(errors,[])
            result=store.snapshot();self.assertEqual(result['state'],'ready');self.assertEqual(result['effects'],[])
            self.assertEqual([a['version'] for a in app.commit()['effects']],[2])
        finally:release.set();old.join(5);store.close()

    def test_restart_marks_unfinished_records_as_interrupted(self):
        "After restart, persisted running records cannot impersonate live worker threads."
        import tempfile
        with tempfile.TemporaryDirectory(dir=ROOT/'scratch') as folder:
            path=str(Path(folder)/'unfinished.sqlite');first=Store(path)
            state=ActivityExecution(attempt='old').snapshot()
            with first.transaction():
                first.put_execution({**state,'phase':'checking','disposition':'current'})
                job=first.get();job.update(state='checking',attempt='old',execution=state);first.put(job)
            first.close();second=Store(path)
            try:
                result=second.snapshot();self.assertEqual(result['state'],'failed')
                self.assertEqual(result['executions'][0]['disposition'],'interrupted')
                self.assertEqual(result['executions'][0]['activities'],state['activities'])
            finally:second.close()

    def test_missing_internal_activity_is_rejected(self):
        state=run_checks("Public sample")['execution'];state['activities'].pop('privacy')
        with self.assertRaises(ValueError):validate_configuration(self.model,state)

    def test_invented_slot_return_is_rejected(self):
        state=run_checks("Public sample")['execution']
        self.assertTrue(validate_configuration(self.model,state)['valid'])
        state['journal'][0]['after']['resources']['workers']['available']+=1
        with self.assertRaises(ValueError):validate_configuration(self.model,state)

    def test_ready_state_requires_completed_internal_state(self):
        state=ActivityExecution().snapshot();state['phase']='ready'
        with self.assertRaises(ValueError):validate_configuration(self.model,state)

    def test_all_join_cannot_be_replaced_with_any(self):
        broken=deepcopy(self.model);broken['machine']['execution']['join']['policy']='any'
        with self.assertRaises(ValueError):validate_execution_graph(broken)

    def test_lifecycle_guard_cannot_be_removed(self):
        broken=deepcopy(self.model)
        next(t for t in broken['machine']['transitions'] if t['trigger']=='checked').pop('conditions')
        with self.assertRaises(ValueError):validate_execution_graph(broken)


if __name__=='__main__':unittest.main()
