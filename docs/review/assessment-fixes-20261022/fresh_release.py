"""Restore only the shipped receipt in a fresh local copy and check its binding."""
import json
from pathlib import Path
import shutil
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[3]
OUT=Path(__file__).resolve().parent


def main():
    target=ROOT/'.validation'/(sys.argv[1] if len(sys.argv)>1 else 'assessment-fixes-fresh-release')
    if target.exists():raise ValueError('Preserve previous evidence; use a new directory')
    results=[]
    for name,runtime,manifest in [('delivery','observer_generated/runtime','observer_generated/manifest.json'),
                                 ('team-archive','observer_runtime','manifest.json')]:
        project=target/name
        def ignore(folder,names):
            skipped=shutil.ignore_patterns('__pycache__','*.pyc','.stategraph','data','dist','scratch','local.json')(folder,names)
            if Path(folder).name=='review':skipped.update({'runtime','mutations','gate-rehearsal'} & set(names))
            return skipped
        shutil.copytree(ROOT/'examples'/name,project,ignore=ignore)
        (project/manifest).unlink(missing_ok=True)
        shutil.copytree(project/'.release/stategraph',project/'.stategraph')
        shutil.copyfile(project/'.release/manifest.json',project/manifest)
        argv=[sys.executable,'-B','-X','utf8',runtime+'/change_sync.py','check','--root','.']
        done=subprocess.run(argv,cwd=project,capture_output=True,text=True,encoding='utf-8',timeout=60)
        result={'example':name,'exit_code':done.returncode,'stdout':done.stdout,'stderr':done.stderr}
        if done.stdout:result['result']=json.loads(done.stdout)
        results.append(result)
        (OUT/'fresh-release-results.json').write_text(json.dumps(results,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        assert done.returncode==0, result
    print(json.dumps(results,ensure_ascii=False))


if __name__=='__main__':main()
