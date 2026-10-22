import json
import os
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[3]
OUT=Path(__file__).resolve().parent / sys.argv[1]
PROJECT=ROOT/'.validation'/('web-design-'+sys.argv[1])
if PROJECT.exists():raise ValueError('Choose a fresh trial name; preserve failures')
PROJECT.mkdir(parents=True);OUT.mkdir(parents=True)
skill=ROOT/'skills/business-observer'
doc=json.loads((skill/'assets/discovery.example.json').read_text(encoding='utf-8'))
doc.update(project_id='download-demo',layout_id='download-demo',title='数据下载')
(PROJECT/'discovery.json').write_text(json.dumps(doc,ensure_ascii=False,indent=2),encoding='utf-8')
env=os.environ.copy();env.update(PLAYWRIGHT_MODULE=str(Path.home()/'.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright'),
    BO_UI_OUT=str(OUT),BO_DESIGN_PROJECT=str(PROJECT),BO_TEST_URL='http://127.0.0.1:8843',BO_PYTHON=sys.executable,BO_SKILL=str(skill))
helper=Path.home()/'.codex/skills/webapp-testing/scripts/with_server.py'
server=subprocess.list2cmdline([sys.executable,'-B','-X','utf8',str(skill/'scripts/bo_web.py'),'serve','--root',str(PROJECT),'--port','8843'])
with (OUT/'browser.log').open('w',encoding='utf-8') as stream:
    done=subprocess.run([sys.executable,str(helper),'--server',server,'--port','8843','--timeout','30','--','node',str(OUT.parent/'design-ui.cjs')],cwd=ROOT,env=env,stdout=stream,stderr=subprocess.STDOUT,timeout=150)
print('design UI',done.returncode,OUT)
raise SystemExit(done.returncode)
