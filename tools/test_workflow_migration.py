"""Compare retained pre-refactor executors with the independent module."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]

def load(name,path):
    if path.parent.name == 'bo_stategraph':
        # Load the real package so its shared validators remain active. Each
        # example gets a separate namespace; the legacy file stays unchanged.
        package = '_migration_' + name
        package_spec = importlib.util.spec_from_file_location(package, path.parent/'__init__.py',
                                                             submodule_search_locations=[str(path.parent)])
        package_module = importlib.util.module_from_spec(package_spec)
        sys.modules[package] = package_module
        package_spec.loader.exec_module(package_module)
        name = package + '.workflow'
    spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module

def normalize(value):
    return json.loads(json.dumps(value).replace('app/workflow.py','bo_stategraph/workflow.py').replace('archive_bo_stategraph','bo_stategraph'))


class MigrationTests(unittest.TestCase):
    def test_complete_definitions_are_preserved(self):
        for name,project in [('delivery','delivery'),('archive','team-archive')]:
            old=load('old_'+name,ROOT/f'tests/fixtures/pre_refactor/{name}_workflow.py')
            new=load('new_'+name,ROOT/f'examples/{project}/bo_stategraph/workflow.py')
            self.assertEqual(normalize(old.definition()),normalize(new.definition()))

    def test_delivery_results_resources_rejection_and_cancellation(self):
        versions=[load('delivery_'+name,path) for name,path in [('old',ROOT/'tests/fixtures/pre_refactor/delivery_workflow.py'),('new',ROOT/'examples/delivery/bo_stategraph/workflow.py')]]
        for capacity in (1,2):
            for outcome in ('success','reject','error','abort'):
                results=[]
                for module in versions:
                    execution=module.ActivityExecution(capacity,attempt='a',param_version=3)
                    states=[module.advance('draft','start')]
                    with self.assertRaises(ValueError):module.advance('checking','checked',execution.snapshot(),attempt='a',param_version=3)
                    if outcome=='abort':execution.abort()
                    else:
                        for activity in ('checksum','privacy'):
                            execution.start(activity)
                            execution.finish(activity,outcome!='reject',error=outcome=='error')
                        joined=execution.join()
                        if joined:states.append(module.advance('checking','checked',execution.snapshot(),attempt='a',param_version=3))
                    results.append({'states':states,'execution':execution.snapshot()})
                self.assertEqual(*results)

    def test_archive_wait_resume_join_and_cancel(self):
        versions=[load('archive_'+name,path) for name,path in [('old',ROOT/'tests/fixtures/pre_refactor/archive_workflow.py'),('new',ROOT/'examples/team-archive/bo_stategraph/workflow.py')]]
        for outcome in ('success','cancel','reject'):
            results=[]
            for module in versions:
                run={'id':'a','phase':'created','phase_journal':[],'configuration':module.initial_configuration('a',1,1)}
                module.change_phase(run,'begin',{'allowed':True},1)
                module.activity_step(run,'start','content_check',2)
                module.activity_step(run,'wait','index_check',3)
                if outcome=='cancel':
                    module.change_phase(run,'stop',{},4)
                    with self.assertRaises(ValueError):module.activity_step(run,'abort','checks_join',5)
                    module.activity_step(run,'finish','content_check',6,'succeeded')
                    module.activity_step(run,'abort','checks_join',7)
                    module.change_phase(run,'cancel_done',{'settled':True},8)
                else:
                    module.activity_step(run,'finish','content_check',4,'succeeded')
                    module.activity_step(run,'start','index_check',5)
                    module.activity_step(run,'finish','index_check',6,'succeeded' if outcome=='success' else 'rejected')
                    module.activity_step(run,'join','checks_join',7)
                    module.change_phase(run,'checked' if outcome=='success' else 'reject',{'allowed':True,'all_passed':outcome=='success','checks_failed':outcome=='reject'},8)
                results.append(run)
            self.assertEqual(*results)


if __name__=='__main__':unittest.main()
