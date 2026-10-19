"""Project command entrypoint. Review stays an explicit artifact, never auto-approved."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
RUNTIME=ROOT/'observer_generated/runtime'


def command(script,*args):
    r=subprocess.run([sys.executable,'-B','-X','utf8',str(script),*args],cwd=ROOT,capture_output=True,text=True,encoding='utf-8')
    if r.returncode:
        print(r.stdout);print(r.stderr,file=sys.stderr);raise SystemExit(r.returncode)
    try:return json.loads(r.stdout)
    except ValueError:return {'output':r.stdout}


def archive(label):
    if not label or any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-' for c in label):
        raise ValueError('use a simple version label')
    from tests.observe import observe,loaded,model
    from tests.scenarios import SCENARIOS
    payload=observe()
    views={}
    for run in payload['runs']:
        if run['mode']!='on':continue
        job=run['authority']
        views[run['case']]={'model':model,'manifest':loaded,'events':run['events'],'health':run['health'],
            'authority':{'basis':{k:job[k] for k in ('param_version','epoch','clock')},'parameters':job,
                         'effects':job['effects'],'state':job['state'],'entity':'delivery:1'},
            'machine':{'current':job['state'],'journal':job['journal'],'configurations':job['executions']},'binding_status':{'status':'current'},
            'historical':True,'busy':False,'case_label':SCENARIOS[run['case']][0],
            'case_description':SCENARIOS[run['case']][1],'case_expected':SCENARIOS[run['case']][2]}
    value={'revision':label,'views':views,'sources':{p:(ROOT/p).read_text(encoding='utf-8-sig') for p in model['source_files']}}
    path=ROOT/'history'/f'{label}.json';path.parent.mkdir(exist_ok=True)
    if path.exists():raise ValueError('history is immutable; choose a new label')
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8',newline='\n')
    return {'archive':str(path),'cases':len(views),'build_id':loaded['build_id']}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('action',choices=['graph','inspect','verify','accept','check','ownership','core','archive'])
    p.add_argument('--reason');p.add_argument('--label');p.add_argument('--out',default='dist/delivery-core.zip')
    a=p.parse_args()
    if a.action=='graph':
        if not a.reason:p.error('--reason is required after reviewing the change')
        command(ROOT/'tooling/build_graph.py')
        result=command(RUNTIME/'architecture_guard.py','seal','--root',str(ROOT),'--reason',a.reason)
        result={'valid':result['valid'],'regenerated':result['sealed']}
    elif a.action=='archive':
        command(RUNTIME/'change_sync.py','check','--root',str(ROOT))
        result=archive(a.label)
    elif a.action in ('ownership','core'):
        if a.action=='core':command(RUNTIME/'change_sync.py','check','--root',str(ROOT))
        args=['check'] if a.action=='ownership' else ['package','--out',a.out]
        result=command(RUNTIME/'architecture_guard.py',*args,'--root',str(ROOT))
        result={'valid':result['valid'],'files':len(result['ownership']),'package':result.get('package')}
    else:result=command(RUNTIME/'change_sync.py',a.action,'--root',str(ROOT))
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
