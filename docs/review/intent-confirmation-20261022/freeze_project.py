"""Freeze trial source bytes and hashes without test databases, caches or personal views."""
import argparse
import hashlib
import json
from pathlib import Path
import zipfile


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project',type=Path,default=Path(__file__).resolve().parents[4]/'project-flow-trial-20261022')
    parser.add_argument('--label',required=True)
    args=parser.parse_args()
    out=Path(__file__).parent/'snapshots';out.mkdir(exist_ok=True)
    target=out/(args.label+'.zip')
    if target.exists():raise FileExistsError(target)
    exclude={'.git','.venv','__pycache__','.stategraph','.pytest_cache','node_modules','data','dist','evidence','release'}
    files={p.relative_to(args.project).as_posix():p for p in args.project.rglob('*') if p.is_file() and not any(part in exclude for part in p.relative_to(args.project).parts) and not p.relative_to(args.project).as_posix().startswith('bo_stategraph/config/views/') and p.suffix not in {'.lock','.pyc','.sqlite','.sqlite3'}}
    before={name:hashlib.sha256(p.read_bytes()).hexdigest() for name,p in files.items()}
    with zipfile.ZipFile(target,'x',compression=zipfile.ZIP_DEFLATED) as archive:
        for name,path in sorted(files.items()):
            data=path.read_bytes()
            if hashlib.sha256(data).hexdigest()!=before[name]:raise RuntimeError('Source changed during snapshot: '+name)
            archive.writestr('project/'+name,data)
    unchanged=all(hashlib.sha256(path.read_bytes()).hexdigest()==before[name] for name,path in files.items())
    result={'source':str(args.project),'archive':target.name,'file_count':len(files),'files':before,'source_unchanged_during_snapshot':unchanged,'archive_sha256':hashlib.sha256(target.read_bytes()).hexdigest()}
    (out/(args.label+'.json')).write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(json.dumps({'file_count':len(files),'unchanged':unchanged,'archive_sha256':result['archive_sha256']},ensure_ascii=True))
    if not unchanged:raise SystemExit(1)


if __name__=='__main__':main()
