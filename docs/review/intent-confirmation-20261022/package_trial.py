"""Preserve actual trial evidence alongside the separately frozen runnable source."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import zipfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', type=Path, default=Path(__file__).resolve().parents[4] / 'project-flow-trial-20261022')
    parser.add_argument('--label', required=True)
    parser.add_argument('--screenshot-source', default='evidence/runtime-frames')
    args = parser.parse_args()
    out = Path(__file__).parent
    archive = out / 'snapshots' / (args.label + '-evidence.zip')
    if archive.exists():
        raise FileExistsError(archive)
    files = []
    for folder in ['evidence', '.stategraph', 'dialogue']:
        files.extend(p for p in (args.project / folder).rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix not in {'.pyc', '.lock'})
    files.extend(p for p in args.project.iterdir() if p.is_file() and p.suffix in {'.md', '.json'})
    hashes = {}
    with zipfile.ZipFile(archive, 'x', compression=zipfile.ZIP_DEFLATED) as zipped:
        for path in sorted(set(files)):
            name = path.relative_to(args.project).as_posix()
            data = path.read_bytes()
            hashes[name] = hashlib.sha256(data).hexdigest()
            zipped.writestr('project/' + name, data)
    result = {'archive': archive.name, 'archive_sha256': hashlib.sha256(archive.read_bytes()).hexdigest(), 'file_count': len(hashes), 'files': hashes, 'scope': 'Synthetic trial records, failures, checks, screenshots and synthetic view copies from gate rehearsal; no live demo database'}
    (out / 'snapshots' / (args.label + '-evidence.json')).write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf8')
    screens = out / 'screenshots' / args.label
    screens.mkdir(parents=True, exist_ok=False)
    source = (args.project / args.screenshot_source).resolve()
    if not source.is_relative_to(args.project.resolve()):
        raise ValueError('Screenshots must belong to the trial project')
    for path in source.glob('*.png'):
        shutil.copyfile(path, screens / path.name)
    if args.screenshot_source == 'evidence/runtime-frames':
        shutil.copyfile(args.project / 'evidence/app-normal.png', screens / 'app.png')
        shutil.copyfile(args.project / 'evidence/app-320.png', screens / 'app-320.png')
    print(json.dumps({k: v for k, v in result.items() if k != 'files'}))


if __name__ == '__main__':
    main()
