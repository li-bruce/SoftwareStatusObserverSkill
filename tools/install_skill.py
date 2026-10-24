"""Install VibeLens, preserving existing files and explicit legacy-migration backups."""
import argparse
from datetime import datetime, timezone
from pathlib import Path
import shutil
import tempfile
import uuid

ROOT = Path(__file__).resolve().parents[1]
SKILL_NAME = 'vibelens'
LEGACY_NAME = 'business-observer'


def install(skills_directory, *, migrate_legacy=False):
    """Stage the complete Skill, then retain any old installation outside discovery."""
    directory = Path(skills_directory).expanduser().absolute().resolve()
    target = directory / SKILL_NAME
    legacy = directory / LEGACY_NAME
    if target.exists():
        raise ValueError('VibeLens already exists. Review the installed version before replacing it.')
    if legacy.exists() and not migrate_legacy:
        raise ValueError('An existing business-observer installation was found. Use --migrate-legacy to retain it as a backup and install VibeLens.')
    if migrate_legacy and not legacy.exists():
        raise ValueError('No business-observer installation exists in the selected skills directory.')
    if legacy.exists() and (not legacy.is_dir() or legacy.resolve() != legacy):
        raise ValueError('The legacy installation must be a regular directory inside the selected skills directory.')

    directory.mkdir(parents=True, exist_ok=True)
    backup = None
    # Finish copying before moving the old installation. A failed copy leaves it usable.
    with tempfile.TemporaryDirectory(prefix='.vibelens-install-', dir=directory.parent) as temporary:
        staged = Path(temporary) / SKILL_NAME
        shutil.copytree(ROOT / 'skills' / SKILL_NAME, staged,
                        ignore=shutil.ignore_patterns('__pycache__', '*.pyc', 'node_modules'))
        if migrate_legacy:
            suffix = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + uuid.uuid4().hex[:8]
            backup = directory.parent / 'skill-backups' / (LEGACY_NAME + '-' + suffix)
            backup.parent.mkdir(parents=True, exist_ok=True)
            legacy.rename(backup)
        try:
            if target.exists():
                raise ValueError('VibeLens appeared during installation; existing files were preserved.')
            staged.rename(target)
        except Exception:
            if backup is not None and not legacy.exists():
                backup.rename(legacy)
            raise
    return target, backup


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    location = parser.add_mutually_exclusive_group(required=True)
    location.add_argument('--project', type=Path, help='Existing project directory')
    location.add_argument('--skills-dir', type=Path, help='Agent skills directory, such as ~/.codex/skills')
    parser.add_argument('--migrate-legacy', action='store_true',
                        help='Back up business-observer outside the skills directory before installing VibeLens')
    args = parser.parse_args()
    if args.project:
        project = args.project.expanduser().absolute().resolve()
        if not project.is_dir():
            parser.error('The target project directory must exist.')
        skills_directory = project / '.agents/skills'
    else:
        skills_directory = args.skills_dir
    try:
        target, backup = install(skills_directory, migrate_legacy=args.migrate_legacy)
    except (ValueError, OSError) as error:
        parser.error(str(error))
    print(f'Installed: {target}')
    if backup is not None:
        print(f'Previous installation preserved: {backup}')
        print('Project runtimes and personal graph settings were not changed.')
    print('Open a new conversation in the target project and use $vibelens.')


if __name__ == '__main__':
    main()
