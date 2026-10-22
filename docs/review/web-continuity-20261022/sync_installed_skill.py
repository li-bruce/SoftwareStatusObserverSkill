"""Update only the installed copy matching the preserved pre-repair Skill."""
import hashlib
import json
from pathlib import Path
import shutil
import sys

ROOT=Path(__file__).resolve().parents[3]
OUT=Path(__file__).resolve().parent
SOURCE=ROOT/'skills/business-observer'
TARGET=Path.home()/'.codex/skills/business-observer'


def digest(path): return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    old=json.loads((OUT/'before.json').read_text(encoding='utf-8'))['installed']
    changes=[]
    for path in sorted(SOURCE.rglob('*')):
        if not path.is_file() or '__pycache__' in path.parts: continue
        relative=path.relative_to(SOURCE); target=TARGET/relative
        actual=digest(target) if target.exists() else None
        expected=digest(path)
        if actual==expected:continue
        if actual!=old.get(relative.as_posix()):
            raise ValueError('Installed file has independent changes; stop: '+str(relative))
        changes.append({'file':relative.as_posix(),'before':actual,'after':expected})
    if '--apply' in sys.argv:
        backup=ROOT/'.validation/web-continuity-installed-backup'
        for change in changes:
            relative=Path(change['file']);target=TARGET/relative
            if target.exists():
                saved=backup/relative;saved.parent.mkdir(parents=True,exist_ok=True)
                if saved.exists() and digest(saved)!=change['before']: raise ValueError('Backup already exists with different bytes')
                shutil.copyfile(target,saved)
            target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(SOURCE/relative,target)
        assert all(digest(SOURCE/c['file'])==digest(TARGET/c['file']) for c in changes)
    result={'target':str(TARGET),'applied':'--apply' in sys.argv,'changes':changes}
    (OUT/('installation-applied.json' if result['applied'] else 'installation-plan.json')).write_text(
        json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'files_to_update':len(changes),'applied':result['applied']},ensure_ascii=False))


if __name__=='__main__':main()
