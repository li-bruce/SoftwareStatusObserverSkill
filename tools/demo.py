"""Restore the reviewed release baseline and run the local example."""
import argparse
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT/'examples/delivery'


def run(*args):
    subprocess.run([sys.executable, '-B', '-X', 'utf8', *map(str, args)], cwd=EXAMPLE, check=True)


def prepare():
    (EXAMPLE/'scratch').mkdir(exist_ok=True)
    state = EXAMPLE/'.stategraph'
    if not (state/'active.json').exists():
        if state.exists() and any(state.iterdir()):
            raise SystemExit('An incomplete local change exists. Inspect .stategraph before proceeding.')
        # A fixed, reviewed release snapshot. Never synthesize approval for edited code.
        shutil.copytree(EXAMPLE/'.release/stategraph', state, dirs_exist_ok=True)
        manifest = EXAMPLE/'observer_generated/manifest.json'
        if not manifest.exists():
            shutil.copyfile(EXAMPLE/'.release/manifest.json', manifest)
    run('tooling/dev.py', 'check')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8797)
    parser.add_argument('--prepare-only', action='store_true')
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error('port must be between 1 and 65535')
    prepare()
    if not args.prepare_only:
        try:
            run('integrations/bo_server.py', args.port)
        except KeyboardInterrupt:
            pass


if __name__ == '__main__':
    main()
