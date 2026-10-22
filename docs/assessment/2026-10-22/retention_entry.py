"""Compare the documented Pins(path=...) entry with the bounded adapter."""
from pathlib import Path
import json
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'skills/business-observer/scripts'))
from semantic_probe import Pins
from bo_retention import EventHistory

project = Path(tempfile.mkdtemp(prefix='retention-entry-', dir=ROOT / '.validation/assessment-20261022'))
config = project / 'bo_stategraph/config/retention.json'
config.parent.mkdir(parents=True)
config.write_text(json.dumps({'memory_events': 2, 'memory_seconds': 60, 'log_bytes': 1024, 'log_backups': 1}), encoding='utf-8')
model = {'revision': 1, 'nodes': [{'id': 'value', 'capture': {'out': {'count': 'number'}}}]}
results = []
for bounded in (False, True):
    path = project / ('bounded.jsonl' if bounded else 'documented.jsonl')
    history = EventHistory(project_root=project, path=path) if bounded else None
    pins = Pins(model, 'audit', path=path, sink=(lambda text: history.append(json.loads(text))) if bounded else None)
    trace = pins.attempt('synthetic')
    for count in range(25):
        trace.record('value', 'return', {}, lambda n=count: {'outputs': {'count': n}})
    assert pins.flush()
    pins.close()
    results.append({'entry': 'EventHistory sink' if bounded else 'documented Pins(path=...)',
                    'configured_log_bytes': 1024, 'primary_file_bytes': path.stat().st_size,
                    'file_count': len(list(project.glob(path.name + '*'))),
                    'events_written': pins.health()['written'], 'health': history.health() if history else pins.health()})
(OUT / 'retention-entry-result.json').write_text(json.dumps(results, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps(results, ensure_ascii=False, indent=2))
