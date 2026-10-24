"""Install the locked source parser once; copied runtimes can share this installation."""
from pathlib import Path
import os
import shutil
import subprocess

ROOT=Path(__file__).resolve().parents[1]
ADAPTER=ROOT/'skills/vibelens/scripts/bo_observer/adapters/javascript'

def configure():
    os.environ['BO_ADAPTER_HOME']=str(ADAPTER)

def main():
    npm=shutil.which('npm.cmd' if os.name=='nt' else 'npm')
    if not npm:raise SystemExit('Node >=20 and npm are required for JS/TS/React/Vue source analysis.')
    subprocess.run([npm,'ci','--ignore-scripts','--no-audit','--no-fund'],cwd=ADAPTER,check=True)
    print('Installed locked source adapter:',ADAPTER)
    print('Repository demos and checks share this parser; no application dependency was changed.')

if __name__=='__main__':main()
