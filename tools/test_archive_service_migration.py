"""Compare the retained service and migrated coordinator using actual SQLite/workers."""
import importlib.util
import json
from pathlib import Path
import re
import sys

ROOT=Path(__file__).resolve().parents[1]
PROJECT=ROOT/'examples/team-archive'
sys.path.insert(0,str(PROJECT))
from archive_app.service import ArchiveService
from tooling import scenarios
from test_workflow_migration import translated_prose

spec=importlib.util.spec_from_file_location('archive_app.pre_refactor',ROOT/'tests/fixtures/pre_refactor/archive_service.py')
legacy=importlib.util.module_from_spec(spec)
spec.loader.exec_module(legacy)
model=json.loads((PROJECT/'behavior.json').read_text(encoding='utf-8'))


def canonical(value):
    # Retain all fields and effects; normalize generated IDs and reviewed
    # language-only display/reason changes against the unchanged legacy fixture.
    return re.sub(r'\b[0-9a-f]{12}\b','<generated-id>',json.dumps(translated_prose(value),sort_keys=True,ensure_ascii=False))


def signature(result):
    facts=result['authority_snapshot']
    return {'observations':result['observations'],
            'runs':[{'phase':run['phase'], 'input':run['input'],
                     'stop_reason':run['stop_reason'],'resume_required':run['resume_required'],
                     'configuration':{key:run['configuration'][key] for key in
                        ('activities','resources','join','results','discarded','wait_reasons')},
                     'phase_journal':[(step['event'],step['source'],step['target']) for step in run['phase_journal']]}
                    for run in facts['runs']],
            'archives':facts['archives']}


def main():
    for case in scenarios.CASES:
        results=[]
        for service in (legacy.ArchiveService,ArchiveService):
            scenarios.ArchiveService=service
            result=scenarios.execute(case,'off',model,'migration-comparison')
            results.append(canonical(signature(result)))
        if results[0]!=results[1]:
            raise AssertionError(case+' differs between old and migrated service\n'+ '\n'.join(results))
    print(f'PASS: {len(scenarios.CASES)} old/new SQLite and worker scenarios; states, activities, resource ownership, effects and observed values match.')


if __name__=='__main__': main()
