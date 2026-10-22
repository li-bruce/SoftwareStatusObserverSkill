"""Independently compare the live export, saved recording and current delivery gate."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import urllib.request


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', type=Path, default=Path(__file__).resolve().parents[4] / 'project-flow-trial-20261022')
    parser.add_argument('--url', default='http://127.0.0.1:8870')
    parser.add_argument('--recording', required=True)
    parser.add_argument('--label', required=True)
    args = parser.parse_args()
    out = Path(__file__).parent / 'execution' / args.label
    out.mkdir(parents=True, exist_ok=False)
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    def get(path):
        with opener.open(args.url + path, timeout=10) as response:
            return json.load(response)
    def read(path):
        return json.loads(path.read_text(encoding='utf-8-sig'))
    export = get('/api/stategraph/export')
    record = get('/api/recordings/' + args.recording)
    frames = {f['event_id']: f for f in export['runtime']['runtime_frames']['frames']}
    checks = []
    def check(name, ok, **evidence):
        checks.append({'name': name, 'passed': bool(ok), **evidence})
    check('live_model_equals_current_declaration', export['model'] == read(args.project / 'behavior.json'))
    recorded = record['runtime_frames']['frames']
    check('public_export_preserves_recorded_frames', bool(recorded) and all(frames.get(f['event_id']) == f for f in recorded), compared_frames=len(recorded))
    check('recording_has_no_known_gap', record['gaps'] == [], gaps=record['gaps'])
    active = read(args.project / '.stategraph/active.json')['change']
    verification = read(args.project / active / 'verification.json')
    accepted = read(args.project / active / 'accepted.json')
    check('accepted_verification_passes', verification['valid'], reports=verification['reports'], candidate_id=verification['candidate_id'])
    result = subprocess.run([sys.executable, '-B', '-X', 'utf8', 'tooling/gate.py'], cwd=args.project, capture_output=True, text=True, encoding='utf8')
    (out / 'gate.stdout.log').write_text(result.stdout, encoding='utf8')
    (out / 'gate.stderr.log').write_text(result.stderr, encoding='utf8')
    check('current_source_and_architecture_gate', result.returncode == 0, exit_code=result.returncode)
    for name, value in [('verification.json', verification), ('accepted.json', accepted)]:
        (out / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf8')
    report = {'scope': 'Current local source, declaration, exact recorded frames and configured checks', 'active_change': active, 'checks': checks, 'passed': all(c['passed'] for c in checks)}
    (out / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf8')
    print(json.dumps({'passed': report['passed'], 'checks': len(checks), 'failed': [c['name'] for c in checks if not c['passed']]}))
    raise SystemExit(0 if report['passed'] else 1)


if __name__ == '__main__':
    main()
