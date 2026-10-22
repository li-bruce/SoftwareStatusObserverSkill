"""Inject a missing public runtime projection in an isolated real example.

Business scenarios, expectations, probe requirements and gate implementation stay
unchanged. The sole source edit removes configurations from the observation
command's stategraph_export. The original accepted baseline is retained.
"""
from pathlib import Path
import json
import shutil
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[3]
OUT=Path(__file__).resolve().parent
WORK=ROOT/'.validation/assessment-20261022'
project=WORK/'empty-export-project'
assert not project.exists(), 'Preserve this run; use a fresh audit directory to repeat.'
shutil.copytree(WORK/'source/examples/team-archive',project,
    ignore=shutil.ignore_patterns('__pycache__','*.pyc','data','dist','.validation'))
logs=[]

def run(action,*args):
    argv=[sys.executable,'-B','-X','utf8','observer_runtime/change_sync.py',action,'--root','.',*args]
    result=subprocess.run(argv,cwd=project,capture_output=True,text=True,encoding='utf-8',timeout=180)
    logs.append({'argv':argv,'exit_code':result.returncode,'stdout':result.stdout,'stderr':result.stderr})
    (OUT/'empty-export-gate-commands.json').write_text(json.dumps(logs,ensure_ascii=False,indent=2),encoding='utf-8')
    return result.returncode,json.loads(result.stdout)

status,_=run('begin','--change','.stategraph/audit-empty-export','--request','Audit: omit actual exported instances while preserving scenario witnesses')
assert status==0
path=project/'tooling/observe.py'
source=path.read_text(encoding='utf-8')
before="exported=graph.bo_export(runtime={'machine':bo_machine(runs[0]['authority_snapshot'],before['build_id'])})"
after="exported=graph.bo_export(runtime={'machine':{'configurations':[]}})"
assert source.count(before)==1
path.write_text(source.replace(before,after),encoding='utf-8',newline='\n')
_,impact=run('inspect')
previous=json.loads((project/'.stategraph/refactor-round1/review.json').read_text(encoding='utf-8'))
review={'candidate_id':impact['candidate_id'],'excluded_symbols':previous['excluded_symbols'],
    'requirement_changes':{},'decisions':{name:{'action':'unchanged',
    'reason':'Audit fixture: all business source, graph and required probes unchanged; only observation export deliberately omits instances.'}
    for name in ('business','state_machine','abstraction','probes')}}
(project/'.stategraph/audit-empty-export/review.json').write_text(json.dumps(review,ensure_ascii=False,indent=2),encoding='utf-8')
status,verified=run('verify')
receipt=project/'.stategraph/audit-empty-export'
shutil.copyfile(receipt/'verification.json',OUT/'empty-export-verification.json')
observation=json.loads((receipt/'checks/observations.json').read_text(encoding='utf-8'))
payload=json.loads(observation['stdout'])
result={'verify_exit':status,'verify_valid':verified['valid'],
    'actual_instances_in_first_run':len(payload['runs'][0]['authority_snapshot']['runs']),
    'exported_instances':len(payload['stategraph_export']['instances']),
    'exported_configurations':len(payload['stategraph_export']['runtime']['machine']['configurations']),
    'mapping_witnesses':len(payload['mapping_checks']),'reports':verified['reports'],
    'project':str(project),'only_source_change':'tooling/observe.py: empty public runtime export',
    'checks_and_business_expectations_changed':False}
if status==0:
    result['accept_exit'],_=run('accept')
    result['check_exit'],_=run('check')
(OUT/'empty-export-result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(result,ensure_ascii=False,indent=2))
