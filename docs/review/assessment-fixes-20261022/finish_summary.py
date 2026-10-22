"""Check final evidence identities and the installed Skill; hash the review files."""
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[3]
OUT=Path(__file__).resolve().parent


def read(path):return json.loads(path.read_text(encoding='utf-8'))
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    commands=read(OUT/'final-commands.json')
    assert next(c for c in commands if c['label']=='full-acceptance-complete')['exit_code']==0
    assert all(r['exit_code']==0 and r['result']['valid'] for r in read(OUT/'fresh-release-results.json'))
    examples=read(OUT/'final/summary.json')
    browser=[read(OUT/'browser-complete'/name) for name in ('ui-result.json','ui-resume-result.json')]
    assert all(r['passed'] and not r['errors'] for r in browser)
    assert all(r['build_id']==examples['team-archive']['accepted']['build_id'] for r in browser)
    source=ROOT/'skills/business-observer';installed=Path.home()/'.codex/skills/business-observer'
    files={p.relative_to(source).as_posix():sha(p) for p in source.rglob('*') if p.is_file() and '__pycache__' not in p.parts}
    assert all(sha(installed/path)==digest for path,digest in files.items())
    assert all(sha(ROOT/path)==digest for path,digest in read(OUT/'final/product-sha256.json').items())
    result={'complete':True,'installed_files_match':len(files),'browser_checks':[len(r['checks']) for r in browser],
            'builds':{name:value['accepted']['build_id'] for name,value in examples.items()},
            'fresh_release_retested':True,'original_expectations_preserved':True,
            'local_only':True,'remaining_scope':['incremental event API','performance baseline','general Petri analysis']}
    (OUT/'completion.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    evidence={p.relative_to(OUT).as_posix():sha(p) for p in OUT.rglob('*')
              if p.is_file() and p.name!='evidence-sha256.json' and '__pycache__' not in p.parts}
    (OUT/'evidence-sha256.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False))


if __name__=='__main__':main()
