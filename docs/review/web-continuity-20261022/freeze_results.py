"""Freeze passed receipts and source hashes, preserving older release stages."""
import gzip
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[3]
OUT=Path(__file__).resolve().parent


def read(path):return json.loads(path.read_text(encoding='utf-8'))
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    summary={}
    for name,runtime,manifest in [('delivery','observer_generated/runtime','observer_generated/manifest.json'),
                                 ('team-archive','observer_runtime','manifest.json')]:
        project=ROOT/'examples'/name
        done=subprocess.run([sys.executable,'-B','-X','utf8',runtime+'/change_sync.py','check','--root','.'],
                            cwd=project,capture_output=True,text=True,encoding='utf-8',check=True)
        active=read(project/'.stategraph/active.json')['change']
        assert active=='.stategraph/web-continuity'
        stage=project/active
        receipt=read(stage/'verification.json');assert receipt['valid']
        for artifact in ('acceptance.json','whitebox.json'):
            original=OUT/'before'/name/artifact
            actual=project/(read(project/'sync.json')['acceptance' if artifact=='acceptance.json' else 'whitebox'])
            assert original.read_bytes()==actual.read_bytes(), 'An original expectation changed: '+str(actual)
        for artifact in ('baseline.json','review.json','verification.json','accepted.json','impact.json','structure.json','checks/whitebox.json'):
            target=project/'.release/stategraph/web-continuity'/artifact
            target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(stage/artifact,target)
        for artifact in ('active.json','source-baseline.json','maintenance.json'):
            shutil.copyfile(project/'.stategraph'/artifact,project/'.release/stategraph'/artifact)
        shutil.copyfile(project/manifest,project/'.release/manifest.json')
        evidence=OUT/'final'/name;evidence.mkdir(parents=True,exist_ok=True)
        for artifact in ('verification.json','accepted.json','review.json'):
            shutil.copyfile(stage/artifact,evidence/artifact)
        for raw in sorted((stage/'checks').glob('*.json')):
            with gzip.open(evidence/(raw.name+'.gz'),'wb') as stream:stream.write(raw.read_bytes())
        summary[name]={'check':json.loads(done.stdout),'accepted':read(stage/'accepted.json'),
                       'reports':receipt['reports'],'original_expectations_preserved':True,
                       'expectation_hashes':{p.name:sha(p) for p in (OUT/'before'/name).glob('*.json')}}
    product={}
    for folder in ('skills/business-observer','examples/delivery/bo_stategraph','examples/team-archive/bo_stategraph',
                   'examples/python-modes','tools','tests'):
        for path in (ROOT/folder).rglob('*'):
            if path.is_file() and not any(p in ('__pycache__','.stategraph','local.json') for p in path.parts):
                product[path.relative_to(ROOT).as_posix()]=sha(path)
    (OUT/'final/summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    (OUT/'final/product-sha256.json').write_text(json.dumps(product,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({name: {'candidate':value['accepted']['candidate_id'],'preserved':True} for name,value in summary.items()}))


if __name__=='__main__':main()
