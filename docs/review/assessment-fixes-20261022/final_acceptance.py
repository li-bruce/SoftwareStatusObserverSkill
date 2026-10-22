"""Run the last source revision through normal gates, then freeze passed receipts."""
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[3]
OUT=Path(__file__).resolve().parent


def main():
    commands=[
        ('sync-final',['tools/sync_runtime.py']),
        ('modes-model-final',['examples/python-modes/build_model.py']),
        ('delivery-model-final',['examples/delivery/tooling/dev.py','graph','--reason','R1-R6 final: reviewed strict frame identity validation']),
        ('archive-model-final',['examples/team-archive/tooling/build_model.py']),
        ('archive-seal-final',['examples/team-archive/observer_runtime/architecture_guard.py','seal','--root','examples/team-archive','--reason','R1-R6 final: reviewed strict frame identity validation']),
        ('stage05',['docs/review/assessment-fixes-20261022/verify_examples.py','stage05']),
        ('full-acceptance-complete',['tools/verify.py']),
        ('freeze-results',['docs/review/assessment-fixes-20261022/freeze_results.py']),
        ('fresh-release',['docs/review/assessment-fixes-20261022/fresh_release.py'])
    ]
    results=[]
    for label,args in commands:
        started=time.monotonic()
        with (OUT/(label+'.log')).open('w',encoding='utf-8') as stream:
            done=subprocess.run([sys.executable,'-B','-X','utf8',*args],cwd=ROOT,stdout=stream,stderr=subprocess.STDOUT)
        result={'label':label,'arguments':args,'exit_code':done.returncode,'seconds':round(time.monotonic()-started,3)}
        results.append(result)
        (OUT/'final-commands.json').write_text(json.dumps(results,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        print(json.dumps(result,ensure_ascii=False),flush=True)
        if done.returncode:raise SystemExit(done.returncode)


if __name__=='__main__':main()
