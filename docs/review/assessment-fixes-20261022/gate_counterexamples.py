"""Keep the real accepted baseline, inject omissions, then repair the same stage."""
import json
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent


def main():
    global OUT
    if len(sys.argv)>2:
        OUT=OUT/sys.argv[2]
        OUT.mkdir(parents=True,exist_ok=True)
    project = ROOT / '.validation' / sys.argv[1] / 'gate-project'
    if project.exists(): raise ValueError('Choose a fresh evidence directory')
    source = ROOT / 'examples/team-archive'
    shutil.copytree(source, project, ignore=shutil.ignore_patterns(
        '__pycache__','*.pyc','data','dist','runtime','gate-rehearsal','mutations','local.json'))
    logs, results = [], []
    def run(command, *args):
        argv = [sys.executable,'-B','-X','utf8','observer_runtime/change_sync.py',command,'--root','.',*args]
        done = subprocess.run(argv,cwd=project,capture_output=True,text=True,encoding='utf-8',timeout=360)
        response = json.loads(done.stdout)
        logs.append({'argv':argv[4:],'exit_code':done.returncode,'result':response,'stderr':done.stderr})
        (OUT/'counterexample-commands.json').write_text(json.dumps(logs,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        return done.returncode,response
    assert run('check')[0] == 0
    stage = '.stategraph/repaired-export-check'
    assert run('begin','--change',stage,'--request','Inspect mapping omission detection and repair without changing any business expectation')[0] == 0
    previous = json.loads((project/'.stategraph/assessment-fixes/review.json').read_text(encoding='utf-8'))
    def review():
        _, impact = run('inspect')
        value = {**previous,'candidate_id':impact['candidate_id']}
        (project/stage/'review.json').write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    mapping_file = project/'mapping.json'; mapping = mapping_file.read_text(encoding='utf-8')
    observer_file = project/'tooling/observe.py'; observer = observer_file.read_text(encoding='utf-8')
    for label in ('dropped_field','new_unregistered_function','empty_public_export','repaired'):
        mapping_file.write_text(mapping,encoding='utf-8',newline='\n')
        observer_file.write_text(observer,encoding='utf-8',newline='\n')
        extra = project/'archive_app/new_unmapped.py'
        if extra.exists(): extra.unlink()  # Only this harness-created file, in the isolated project.
        if label == 'dropped_field':
            value = json.loads(mapping); value['fields'] = [f for f in value['fields'] if f['id'] != 'operator_id']
            mapping_file.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        elif label == 'new_unregistered_function':
            extra.write_text('def choose_destination(project):\n    return project["parent"]\n',encoding='utf-8')
        elif label == 'empty_public_export':
            original = "exported=graph.bo_export(runtime={'machine':selected['projection']['machine']})"
            assert observer.count(original) == 1
            observer_file.write_text(observer.replace(original,"exported=graph.bo_export(runtime={'machine':{'configurations':[]}})"),encoding='utf-8',newline='\n')
        review()
        code, receipt = run('verify')
        accepted, _ = run('accept')
        checked, _ = run('check')
        expected = label == 'repaired'
        assert (code == 0) == expected and (accepted == 0) == expected and (checked == 0) == expected
        result = {'case':label,'verify_exit':code,'accept_exit':accepted,'check_exit':checked,
                  'reports':receipt.get('reports'),'errors':receipt.get('errors')}
        if label in ('empty_public_export','repaired'):
            raw=json.loads((project/stage/'checks/observations.json').read_text(encoding='utf-8'))
            payload=json.loads(raw['stdout'])
            result.update(witnesses=len(payload['mapping_checks']),
                          exported_instances=len(payload['stategraph_export']['instances']),
                          required_runs=len(payload['runs']))
        shutil.copyfile(project/stage/'verification.json',OUT/('counterexample-'+label+'.json'))
        results.append(result)
        (OUT/'counterexample-results.json').write_text(json.dumps(results,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        print(json.dumps(result,ensure_ascii=False),flush=True)


if __name__ == '__main__': main()
