"""Repeat the prior real UI acceptance, on a fresh isolated project and database."""
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent


def main():
    project = ROOT/'.validation'/(sys.argv[1] if len(sys.argv)>1 else 'assessment-fixes-ui-01')/'project'
    evidence = OUT/(sys.argv[2] if len(sys.argv)>2 else '.')
    evidence.mkdir(parents=True,exist_ok=True)
    if project.exists(): raise ValueError('Preserve prior results; choose a new isolated project')
    shutil.copytree(ROOT/'examples/team-archive',project,ignore=shutil.ignore_patterns(
        '__pycache__','*.pyc','data','dist','.stategraph','runtime','gate-rehearsal','mutations','local.json'))
    for name in ('ui-test.cjs','ui-resume.cjs'):
        shutil.copyfile(ROOT/'docs/assessment/2026-10-22'/name,evidence/name)
    # Preserve all prior assertions, but wait for an actual persistence receipt
    # before reloading; a selected local option does not mean the write finished.
    script=evidence/'ui-test.cjs'
    text=script.read_text(encoding='utf-8')
    before="const custom=await page.locator('#analysis-view').inputValue();assert(custom.startsWith('custom-'));"
    after=before+"\n  await page.waitForFunction(async()=>{const r=await fetch('/api/preferences',{cache:'no-store'});const saved=await r.json();return Object.values(saved.entries).some(raw=>raw.includes('审查视图'));});"
    assert text.count(before)==1
    script.write_text(text.replace(before,after),encoding='utf-8',newline='\n')
    env=os.environ.copy()
    env['PLAYWRIGHT_MODULE']=str(Path.home()/'.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright')
    helper=Path.home()/'.codex/skills/webapp-testing/scripts/with_server.py'
    for port,script,log in [(8841,'ui-test.cjs','browser-first.log'),(8842,'ui-resume.cjs','browser-restart.log')]:
        env.update(BO_TEST_URL=f'http://127.0.0.1:{port}',BO_UI_OUT=str(evidence/'ui'),BO_UI_RESULT=str(evidence/'ui-result.json'))
        server=subprocess.list2cmdline([sys.executable,'-B','-X','utf8','run.py','--port',str(port),'--delay','3'])
        argv=[sys.executable,str(helper),'--server',server,'--port',str(port),'--timeout','50','--','node',str(evidence/script)]
        with (evidence/log).open('w',encoding='utf-8') as stream:
            done=subprocess.run(argv,cwd=project,env=env,stdout=stream,stderr=subprocess.STDOUT,timeout=240)
        print(script,done.returncode,flush=True)
        if done.returncode: raise SystemExit(done.returncode)


if __name__=='__main__':main()
