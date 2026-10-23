"""Run the native React/Vue demo and the independent Python graph service."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time
from urllib.request import urlopen
from setup_adapters import configure

ROOT=Path(__file__).resolve().parents[1]
EXAMPLE=ROOT/'examples/multilanguage'


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--mode',required=True,choices=['drive','observe'],help='Explicit choice for this synthetic demo')
    p.add_argument('--graph-port',type=int,default=8855);p.add_argument('--app-port',type=int,default=8850)
    a=p.parse_args()
    if not all(1<=port<=65535 for port in (a.graph_port,a.app_port)) or a.graph_port==a.app_port:p.error('use two distinct valid ports')
    configure()
    if not (EXAMPLE/'node_modules/vite/bin/vite.js').exists():
        raise SystemExit('Run npm ci --prefix examples/multilanguage first.')
    file=EXAMPLE/'bo_stategraph/project.json';project=json.loads(file.read_text(encoding='utf-8'))
    project['selection']={'mode':a.mode,'source':'user','answer':"Demo command explicitly selects "+a.mode+"(synthetic test project)",'locator':'tools/multilanguage_demo.py --mode '+a.mode}
    file.write_text(json.dumps(project,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    children=[]
    options={'creationflags':subprocess.CREATE_NO_WINDOW} if sys.platform=='win32' else {}
    try:
        children.append(subprocess.Popen([sys.executable,'-B','-X','utf8',str(ROOT/'skills/business-observer/scripts/bo.py'),'serve','--root',str(EXAMPLE),'--port',str(a.graph_port),'--origin',f'http://127.0.0.1:{a.app_port}'],cwd=ROOT,**options))
        deadline=time.monotonic()+15
        graph_ready=False
        while time.monotonic()<deadline:
            if children[0].poll() is not None:break
            try:
                with urlopen(f'http://127.0.0.1:{a.graph_port}/api/bo/health',timeout=.5) as response:
                    if json.load(response)['project_id']==project['project_id']:
                        graph_ready=True
                        break
            except OSError:time.sleep(.1)
        if not graph_ready:
            # Native business execution must still work on a first launch when
            # the observer is unavailable. Never reuse stale connection tokens.
            if children[0].poll() is None:
                children[0].terminate()
                children[0].wait(timeout=5)
            settings=EXAMPLE/'.stategraph/collector.json'
            settings.parent.mkdir(parents=True,exist_ok=True)
            settings.write_text(json.dumps({'enabled':False,'build_id':'observation-unavailable','endpoint':None,'token':None})+'\n',encoding='utf-8')
            print('Observation unavailable. The application remains usable; restart after fixing the graph service to enable capture.',flush=True)
        children.append(subprocess.Popen([shutil.which('node') or 'node',str(EXAMPLE/'node_modules/vite/bin/vite.js'),'--config','tooling/vite.config.mjs','--host','127.0.0.1','--port',str(a.app_port)],cwd=EXAMPLE,**options))
        print(f'Application: http://127.0.0.1:{a.app_port}/',flush=True)
        if graph_ready:print(f'Graph: http://127.0.0.1:{a.graph_port}/graph',flush=True)
        print('Ctrl+C stops processes started by this launcher.',flush=True)
        while children[-1].poll() is None:
            if graph_ready and children[0].poll() is not None:
                print('Observer stopped. Business execution continues; new observation facts may be lost.',flush=True)
                graph_ready=False
            time.sleep(.25)
        if children[-1].returncode:raise RuntimeError('Application process stopped unexpectedly')
    except KeyboardInterrupt:pass
    finally:
        for child in children:
            if child.poll() is None:child.terminate()
        for child in children:
            try:child.wait(timeout=5)
            except subprocess.TimeoutExpired:child.kill();child.wait()

if __name__=='__main__':main()
