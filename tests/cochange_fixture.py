"""Isolate the shipped example for change-check regression tests."""
import json
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT/'skills/business-observer/scripts'


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')


def prepare(dest):
    shutil.copytree(ROOT/'examples/delivery', dest,
                    ignore=shutil.ignore_patterns('__pycache__', '*.pyc', '.stategraph', '.release',
                                                 'scratch', 'history', 'dist', 'manifest.json'))
    (dest/'scratch').mkdir(exist_ok=True)
    return dest


def sync(root, action, *extra):
    run = subprocess.run([sys.executable, '-B', '-X', 'utf8', str(SCRIPTS/'change_sync.py'),
                          action, '--root', str(root), *extra], cwd=root,
                         capture_output=True, text=True, encoding='utf-8')
    try:
        return run.returncode, json.loads(run.stdout)
    except ValueError:
        raise AssertionError({'stdout': run.stdout, 'stderr': run.stderr})


def review(root):
    # Synthetic review for failure-injection tests only; never used by installation.
    _, impact = sync(root, 'inspect')
    change = json.loads((root/'.stategraph/active.json').read_text())['change']
    release = ROOT/'examples/delivery/.release/stategraph'
    active = Path(json.loads((release/'active.json').read_text())['change']).name
    shipped = json.loads((release/active/'review.json').read_text(encoding='utf-8'))
    # This fixture changes only dialogue data. Reuse the actual reviewed symbol
    # classification for byte-identical source; new or edited source gets no waiver.
    exclusions = {symbol: reason for symbol, reason in shipped['excluded_symbols'].items()
                  if (root/symbol.split('::')[0]).read_bytes() ==
                     (ROOT/'examples/delivery'/symbol.split('::')[0]).read_bytes()}
    save(root/change/'review.json', {
        'candidate_id': impact['candidate_id'],
        'decisions': {part: {'action': 'unchanged', 'reason': 'Synthetic test retains the shipped delivery rules and implementation.'}
                      for part in ('business', 'state_machine', 'abstraction', 'probes')},
        'excluded_symbols': exclusions, 'requirement_changes': {}})
    return impact
