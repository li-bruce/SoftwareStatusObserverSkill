"""Bind final receipts and archive without editing source, baseline or expectations."""
import hashlib
import json
import shutil
import zipfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'review/round-04'


def read(name):
    return json.loads((ROOT / name).read_text(encoding='utf-8-sig'))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


baseline = read('.stategraph/maintenance-02/baseline.json')
prior = read('review/candidate-4/stage.json')
accepted = read('.stategraph/maintenance-02/accepted.json')
verified = read('.stategraph/maintenance-02/verification.json')
review = read('.stategraph/maintenance-02/review.json')
browser = read('review/public-viewer/browser-report.json')
live = read('review/round-04/live-service.json')
model = read('behavior.json')
sync = read('sync.json')
plan = read('review/round-04/public-upgrade-plan.json')
public = read('bo_stategraph/runtime-version.json')
mutations = read('review/round-04/mutations.json')
assert baseline['id'] == prior['candidate_id']
assert digest(ROOT / '.stategraph/implementation-01/baseline.json') == prior['original_baseline_sha256']
assert digest(ROOT / 'review/candidate-4/accepted-source.zip') == prior['accepted_source_zip_sha256']
with zipfile.ZipFile(ROOT / 'review/candidate-4/accepted-source.zip') as archive:
    for name, expected in baseline['files'].items():
        assert hashlib.sha256(archive.read(name)).hexdigest() == expected, name
    for key, name in [('model', 'behavior.json'), ('intent', 'intent.json'),
                      ('acceptance', 'acceptance.json'), ('whitebox', 'whitebox.json')]:
        assert baseline[key] == json.loads(archive.read(name)), key

current_acceptance = read('acceptance.json')
current_whitebox = read('whitebox.json')
for check in baseline['acceptance']['checks']:
    assert check in current_acceptance['checks'], check
for check in baseline['whitebox']['checks']:
    assert check in current_whitebox['checks'], check
moves = {(m['from']['path'], m['from']['symbol']): m['to'] for m in review['source_moves']}
assert len(moves) == len(review['source_moves']) == 22
for rule in baseline['whitebox']['rules']:
    rebound = dict(rule)
    source = rule['source']
    rebound['source'] = moves.get((source['path'], source['symbol']), source)
    assert rebound in current_whitebox['rules'], rule['id']
for probe in baseline['verification_contract']['required_probes']:
    rebound = dict(probe)
    old = tuple(probe['symbol'].split('::', 1))
    if old in moves:
        to = moves[old]
        rebound['symbol'] = to['path'] + '::' + to['symbol']
    assert rebound in sync['required_probes'], probe
assert baseline['verification_contract']['required_runtime_probes'] == sync['required_runtime_probes']
assert sync['stategraph']['development_mode'] == sync['stategraph']['execution_mode'] == 'observe'
assert (ROOT / 'app/workflow.py').exists() and not (ROOT / 'bo_stategraph/workflow.py').exists()
assert verified['valid'] and browser['valid'] and mutations['valid']
assert accepted['candidate_id'] == verified['candidate_id'] == review['candidate_id']
assert accepted['build_id'] == browser['build_id'] == live['build_id']
assert live['binding'] == 'current' and live['port_errors'] == 0
assert live['execution_mode'] == 'observe' and live['event_count'] == live['frame_count']
assert plan['valid'] and not plan['changes'] and not plan['conflicts']
for name, expected in public['files'].items():
    assert digest(ROOT / name) == expected, name

for filename in ['browser-report.json', 'browser-1440.png', 'browser-390.png', 'browser-320.png']:
    shutil.copy2(ROOT / 'review/public-viewer' / filename, OUT / filename)
for filename in ['baseline.json', 'review.json', 'impact.json', 'verification.json']:
    shutil.copy2(ROOT / '.stategraph/maintenance-02' / filename, OUT / filename)
test = json.loads(read('.stategraph/maintenance-02/checks/test-1.json')['stdout'])
(OUT / 'test-project.json').write_text(json.dumps(test, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
assert test['valid'] and test['scenarios'] == 69 and test['state_frames'] == 2013
for mutation in mutations['mutations']:
    assert mutation['stale_gate_exit'] != 0 and mutation['mapping']['valid']
    assert mutation['business_errors'] and mutation['expected_contract_unchanged']

sources = set(model['source_files']) | set(sync['code_files']) | set(sync['watch_files'])
sources.update(['sync.json', 'behavior.json', 'manifest.json', 'intent.json', 'discovery.json',
                'acceptance.json', 'whitebox.json', 'README.md', 'review/README.md',
                '.stategraph/active.json', '.stategraph/source-baseline.json', '.stategraph/maintenance.json',
                '.stategraph/implementation-01/baseline.json'])
sources.update(p.relative_to(ROOT).as_posix() for p in (ROOT / '.stategraph/maintenance-02').rglob('*') if p.is_file())
sources.update(p.relative_to(ROOT).as_posix() for p in OUT.iterdir()
               if p.is_file() and p.suffix in {'.json', '.jsonl', '.md', '.py', '.png'}
               and p.name not in {'stage.json'})
archive_path = OUT / 'accepted-source.zip'
with zipfile.ZipFile(archive_path, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
    for name in sorted(sources):
        archive.write(ROOT / name, name)
with zipfile.ZipFile(archive_path) as archive:
    assert archive.testzip() is None
    for name in sources:
        assert archive.read(name) == (ROOT / name).read_bytes(), name

evidence_names = ['accept.json', 'check-console.jsonl', 'verify-final.json', 'verification.json',
                  'baseline.json', 'review.json', 'impact.json', 'test-project.json', 'browser-report.json',
                  'browser-1440.png', 'browser-390.png', 'browser-320.png', 'mutations.json',
                  'live-service.json', 'public-upgrade-plan.json', 'dialogue.md', 'failures.md']
stage = {
    'status': 'accepted', 'recorded_at': datetime.now(timezone.utc).isoformat(),
    'source_candidate': 'candidate-7', **accepted,
    'development_mode': 'observe', 'execution_mode': 'observe',
    'previous_candidate_id': baseline['id'], 'baseline_files_match_previous_archive': len(baseline['files']),
    'baseline_model_intent_acceptance_whitebox_match_previous_archive': True,
    'maintenance_baseline_sha256': digest(ROOT / '.stategraph/maintenance-02/baseline.json'),
    'original_baseline_sha256': prior['original_baseline_sha256'], 'original_baseline_preserved': True,
    'previous_accepted_archive_preserved': True,
    'preserved_acceptance_checks': len(baseline['acceptance']['checks']),
    'preserved_whitebox_checks': len(baseline['whitebox']['checks']),
    'preserved_whitebox_rules_with_source_moves': len(baseline['whitebox']['rules']),
    'preserved_required_probes_with_source_moves': len(baseline['verification_contract']['required_probes']),
    'preserved_required_runtime_probes': len(sync['required_runtime_probes']),
    'source_moves': len(moves), 'public_files_exact_hash_match': len(public['files']),
    'public_upgrade_plan_empty': True,
    'business_assertions': verified['reports']['business']['assertions'],
    'mapping_witnesses': verified['reports']['mapping']['witnesses'],
    'scenario_runs': test['scenarios'], 'transaction_frames': test['state_frames'],
    'browser_checks': len(browser['checks']),
    'same_build_for_live_browser_and_accepted': True, 'live_service': live,
    'mutations': [{'name': m['mutation'], 'stale_gate_rejected': m['stale_gate_exit'] != 0,
                   'remapped_mapping_valid': m['mapping']['valid'],
                   'unchanged_expectation_failures': len(m['business_errors'])} for m in mutations['mutations']],
    'evidence_sha256': {n: digest(OUT / n) for n in evidence_names},
    'accepted_source_zip_sha256': digest(archive_path), 'archived_files': len(sources),
    'boundary': 'Simulated stakeholder; synthetic devices and identities; scripted browser acceptance, not human usability or physical printer validation.'
}
(OUT / 'stage.json').write_text(json.dumps(stage, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps({k: stage[k] for k in ['status', 'candidate_id', 'build_id', 'source_moves',
      'baseline_files_match_previous_archive', 'public_files_exact_hash_match', 'business_assertions',
      'mapping_witnesses', 'scenario_runs', 'transaction_frames', 'browser_checks', 'mutations',
      'accepted_source_zip_sha256', 'archived_files']}, ensure_ascii=False))
