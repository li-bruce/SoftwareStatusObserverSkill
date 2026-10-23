"""Validate portable links while retaining hash-bound historical transcripts."""
import hashlib
import json
from pathlib import Path, PurePosixPath, PureWindowsPath
import re
import zipfile


def _contained(root, name):
    path = (root / name).resolve()
    path.relative_to(root.resolve())
    return path


def document_link_errors(root, sources):
    root = Path(root).resolve()
    catalog = root / 'docs/review/historical-links.json'
    records = json.loads(catalog.read_text(encoding='utf-8')) if catalog.exists() else {'documents': []}
    approved = {}
    errors = []
    for entry in records['documents']:
        source = _contained(root, entry['path'])
        if hashlib.sha256(source.read_bytes()).hexdigest() != entry['sha256']:
            errors.append(f'Historical transcript changed: {entry["path"]}')
            continue
        targets = set(re.findall(r'\]\(([^)]+)\)', source.read_text(encoding='utf-8')))
        for reference in entry['references']:
            target = reference['target']
            if target not in targets or not reference.get('context'):
                errors.append(f'Invalid historical reference: {entry["path"]} -> {target}')
                continue
            if 'archive' in reference:
                archive = _contained(root, reference['archive'])
                with zipfile.ZipFile(archive) as bundle:
                    if reference['member'] not in bundle.namelist():
                        errors.append(f'Historical archive member missing: {reference["member"]}')
                        continue
            elif not reference.get('external_only'):
                errors.append(f'Historical reference has no provenance: {target}')
                continue
            approved.setdefault(source, set()).add(target)
    for source in sources:
        source = Path(source).resolve()
        for target in re.findall(r'\]\(([^)]+)\)', source.read_text(encoding='utf-8')):
            if target.startswith(('http:', 'https:', '#', 'mailto:')) or '<' in target:
                continue
            if target in approved.get(source, set()):
                continue
            target = target.split('#')[0]
            if not target:
                continue
            # A file on the maintainer's machine cannot make a public link valid.
            if PureWindowsPath(target).is_absolute() or PurePosixPath(target).is_absolute():
                errors.append(f'Nonportable link: {source.relative_to(root)} -> {target}')
                continue
            try:
                resolved = (source.parent / target).resolve()
                resolved.relative_to(root)
            except ValueError:
                errors.append(f'Link escapes repository: {source.relative_to(root)} -> {target}')
                continue
            if not resolved.exists():
                errors.append(f'{source.relative_to(root)} -> {target}')
    return errors
