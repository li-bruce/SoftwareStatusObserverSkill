import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[3]
OUT=Path(__file__).resolve().parent / sys.argv[1]
WORK=ROOT/'.validation'/('web-lifecycle-'+sys.argv[1]);OUT.mkdir(parents=True)
skill=ROOT/'skills/business-observer'
for name in ('delivery','team-archive'):
    def ignore(folder, names):
        return [n for n in names if n in ('__pycache__','data','scratch','dist','.stategraph','gate-rehearsal','mutations','local.json') or n=='runtime' and Path(folder).name=='review']
    shutil.copytree(ROOT/'examples'/name,WORK/name,ignore=ignore)
env=os.environ.copy();env.update(PLAYWRIGHT_MODULE=str(Path.home()/'.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright'),
    BO_UI_OUT=str(OUT),BO_PYTHON=sys.executable,BO_SKILL=str(skill))
helper=Path.home()/'.codex/skills/webapp-testing/scripts/with_server.py'
for mode,port,name,args in [('design',8853,'team-archive',[str(skill/'scripts/bo_web.py'),'serve','--root','.']),
                          ('archive',8854,'team-archive',['run.py','--delay','0.05']),
                          ('delivery',8855,'delivery',['integrations/bo_server.py'])]:
    project=WORK/name
    if mode=='design':args=[str(skill/'scripts/bo_web.py'),'serve','--root',str(project)]
    env.update(BO_PROJECT=str(project),BO_TEST_URL=f'http://127.0.0.1:{port}',BO_LIFECYCLE=mode)
    server=subprocess.list2cmdline([sys.executable,'-B','-X','utf8',*args,*([str(port)] if mode=='delivery' else ['--port',str(port)])])
    with (OUT/(mode+'.log')).open('w',encoding='utf-8') as stream:
        done=subprocess.run([sys.executable,str(helper),'--server',server,'--port',str(port),'--timeout','40','--','node',str(OUT.parent/'lifecycle-ui.cjs')],cwd=project,env=env,stdout=stream,stderr=subprocess.STDOUT,timeout=160)
    print(mode,done.returncode,flush=True)
    if done.returncode:raise SystemExit(done.returncode)
