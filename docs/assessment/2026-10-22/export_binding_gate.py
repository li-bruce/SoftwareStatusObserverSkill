"""Positive/negative control for the public runtime export in the real gate.

Only the selected snapshot expression in the observation command changes.
The positive control exports a real populated scenario. The negative control
replaces that exact projection with an empty configuration list. All scenarios,
checks, probe requirements, mapping witnesses and business expectations stay.
"""
from pathlib import Path
import json
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
WORK = ROOT / '.validation/assessment-20261022'
PROJECT = WORK / 'export-binding-project'
assert not PROJECT.exists(), 'Preserve this run; use a fresh audit directory.'
shutil.copytree(WORK / 'source/examples/team-archive', PROJECT,
               ignore=shutil.ignore_patterns('__pycache__', '*.pyc', 'data', 'dist', '.validation'))
logs, results = [], []
source_path = PROJECT / 'tooling/observe.py'
source = source_path.read_text(encoding='utf-8')
original = "exported=graph.bo_export(runtime={'machine':bo_machine(runs[0]['authority_snapshot'],before['build_id'])})"
positive = "exported=graph.bo_export(runtime={'machine':bo_machine(next(r['authority_snapshot'] for r in runs if r['authority_snapshot']['runs']),before['build_id'])})"
negative = "exported=graph.bo_export(runtime={'machine':{'configurations':[]}})"
assert source.count(original) == 1
old_review = json.loads((PROJECT / '.stategraph/refactor-round1/review.json').read_text(encoding='utf-8'))


def run(action, *args):
    argv = [sys.executable, '-B', '-X', 'utf8', 'observer_runtime/change_sync.py', action, '--root', '.', *args]
    completed = subprocess.run(argv, cwd=PROJECT, capture_output=True, text=True, encoding='utf-8', timeout=180)
    logs.append({'argv': argv, 'exit_code': completed.returncode, 'stdout': completed.stdout, 'stderr': completed.stderr})
    (OUT / 'export-binding-commands.json').write_text(json.dumps(logs, ensure_ascii=False, indent=2), encoding='utf-8')
    return completed.returncode, json.loads(completed.stdout)


for label, expression in [('positive', positive), ('negative', negative)]:
    change = '.stategraph/audit-export-' + label
    status, _ = run('begin', '--change', change, '--request', 'Audit public export ' + label + ' control')
    assert status == 0
    source_path.write_text(source.replace(original, expression), encoding='utf-8', newline='\n')
    _, impact = run('inspect')
    review = {'candidate_id': impact['candidate_id'], 'excluded_symbols': old_review['excluded_symbols'],
              'requirement_changes': {}, 'decisions': {name: {'action': 'unchanged',
                  'reason': 'Audit fixture: only the selected public export snapshot changes. Business code, graph, assertions and probes stay unchanged.'}
                  for name in ('business', 'state_machine', 'abstraction', 'probes')}}
    receipt = PROJECT / change
    (receipt / 'review.json').write_text(json.dumps(review, ensure_ascii=False, indent=2), encoding='utf-8')
    status, verified = run('verify')
    shutil.copyfile(receipt / 'verification.json', OUT / ('export-' + label + '-verification.json'))
    observation = json.loads((receipt / 'checks/observations.json').read_text(encoding='utf-8'))
    payload = json.loads(observation['stdout'])
    selected = next(r for r in payload['runs'] if r['authority_snapshot']['runs'])
    result = {'control': label, 'verify_exit': status, 'verify_valid': verified['valid'],
              'selected_scenario': {'case': selected['case'], 'mode': selected['mode'],
                                    'actual_instances': len(selected['authority_snapshot']['runs'])},
              'exported_instances': len(payload['stategraph_export']['instances']),
              'exported_configurations': len(payload['stategraph_export']['runtime']['machine']['configurations']),
              'mapping_witnesses': len(payload['mapping_checks']), 'reports': verified['reports']}
    if status == 0:
        result['accept_exit'], _ = run('accept')
        result['check_exit'], _ = run('check')
    results.append(result)
    (OUT / 'export-binding-result.json').write_text(json.dumps(results, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False, indent=2), flush=True)
    assert status == 0, 'Inspect this failure before drawing any conclusion.'
