"""Copy the complete Skill into a project, without replacing existing files."""
import argparse
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', type=Path, required=True, help='Existing project directory')
    args = parser.parse_args()
    project = args.project.expanduser().absolute().resolve()
    if not project.is_dir():
        parser.error('The target project directory must exist.')
    target = project/'.agents/skills/business-observer'
    if target.exists():
        parser.error('Skill already exists. Review the installed version before replacing it.')
    shutil.copytree(ROOT/'skills/business-observer', target,
                    ignore=shutil.ignore_patterns('__pycache__', '*.pyc', 'node_modules'))
    print(f'Installed: {target}')
    print('Open a new conversation in the target project and use $business-observer.')


if __name__ == '__main__':
    main()
