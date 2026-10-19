"""Produce a renderer fixture from actual execution, independent of test order."""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tests.observe import model, loaded
from tests.scenarios import exercise


def main():
    run = exercise('resource_wait', model, loaded['build_id'])
    job = run['authority']
    view = {'model': model, 'manifest': loaded, 'events': run['events'],
            'health': run['health'], 'binding_status': {'status': 'current'},
            'machine': {'current': job['state'], 'journal': job['journal'], 'configurations': job['executions']},
            'authority': {'basis': {k: job[k] for k in ('param_version', 'epoch', 'clock')},
                          'parameters': job, 'effects': job['effects'], 'state': job['state']}}
    (ROOT/'scratch').mkdir(exist_ok=True)
    (ROOT/'scratch/graph-fixture.json').write_text(json.dumps(view, ensure_ascii=False), encoding='utf-8')
    print(json.dumps({'valid': True, 'fixture': 'scratch/graph-fixture.json'}))


if __name__ == '__main__':
    main()
