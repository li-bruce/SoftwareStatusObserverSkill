"""Read-only audit counterexamples. Writes only this audit's result and temporary fixtures.

Run from the repository root: python -B -X utf8 docs/assessment/2026-10-21/reproduce.py
These are observations of limitations, not replacement product acceptance tests.
"""
from copy import deepcopy
from datetime import datetime, timezone
import importlib.metadata
import json
from pathlib import Path
import sys
import tempfile
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'skills/business-observer/scripts'))
from bo_stategraph import BOStateGraph, bo_value_errors
from statechart_contract import validate_chart
from execution_contract import validate_configuration
from behavior_model import validate, capture, check
from change_sync import config, assess_observations
from transitions.extensions import HierarchicalMachine


def diagnostic(call):
    try:
        value = call()
        return {'accepted': True, 'value': value if isinstance(value, (dict, list, str, int, type(None))) else type(value).__name__}
    except Exception as exc:
        return {'accepted': False, 'error': type(exc).__name__ + ': ' + str(exc)}


def simple_model():
    return {'machine': {'engine': 'transitions', 'version': importlib.metadata.version('transitions'),
        'state_type': 'str enum', 'states': ['pending', 'done'], 'values': ['pending', 'done'],
        'initial': 'pending', 'events': {'finish': {'payload': {}}},
        'context': {'slots': {'type': 'integer', 'min': 0}}, 'guards': {},
        'transitions': [{'source': 'pending', 'dest': 'done', 'trigger': 'finish'}]},
        'nodes': [{'id': s, 'kind': 'state', 'layer': 'state', 'value': s} for s in ('pending', 'done')],
        'edges': [{'id': 'finish', 'from': 'pending', 'to': 'done', 'type': 'flow'}], 'scope': {}}


findings = []
for name, update in [('undefined_target', {'dest': 'absent'}), ('undefined_guard', {'conditions': 'absent'})]:
    model = simple_model()
    model['machine']['transitions'][0].update(update)
    findings.append({'id': name, 'independent_module': diagnostic(lambda: BOStateGraph(model, build_id='audit')),
                     'project_validator': diagnostic(lambda: validate_chart(model))})

archive_root = ROOT / 'examples/team-archive'
archive = json.loads((archive_root / 'behavior.json').read_text(encoding='utf-8'))
cycle = deepcopy(archive)
cycle['nodes'][0]['parent'] = cycle['nodes'][0]['id']
findings.append({'id': 'parent_cycle', 'independent_module': diagnostic(lambda: BOStateGraph(cycle, build_id='audit')),
                 'project_validator': diagnostic(lambda: validate(archive_root, cycle))})

model = simple_model()
model['machine'].update(states=[{'name': 'active', 'children': ['a', 'b']}, 'done'],
    values=['active_a', 'active_b', 'done'], initial='active_a',
    transitions=[{'source': 'active', 'dest': 'done', 'trigger': 'finish'}])
model['nodes'] = [{'id': s, 'kind': 'state', 'layer': 'state', 'value': s} for s in model['machine']['values']]
model['edges'] = []
graph = BOStateGraph(model, build_id='audit')
engine = HierarchicalMachine(states=model['machine']['states'], transitions=model['machine']['transitions'],
    initial='active_a', auto_transitions=False)
before = graph.bo_observe('instance', state=engine.state, context={'slots': 1}, revision=0, evidence_id='first', build_id='audit')
engine.finish()
after = graph.bo_observe('instance', state=engine.state, context={'slots': 1}, revision=1,
    evidence_id='second', build_id='audit', event='finish')
findings.append({'id': 'hierarchical_transition', 'declaration_check': validate_chart(model),
    'actual_engine_state': engine.state, 'observer_status': after['status'], 'observer_errors': after['errors'],
    'observer_candidates': after['transition_check']['candidates']})

spec = archive['machine']['execution']
cfg = {'attempt': 'audit-run', 'param_version': 1, 'revision': 0, 'phase': archive['machine']['initial'],
    'activities': {a['id']: 'pending' for a in spec['activities']},
    'resources': {r['id']: {'capacity': r['min'], 'available': r['min'], 'holders': []} for r in spec['resources']},
    'join': {'state': 'waiting', 'pending': spec['join']['requires']}, 'journal': []}
validate_configuration(archive, cfg)
cfg['resources'][spec['resources'][0]['id']]['available'] = -1


def sample(spec):
    return {'integer': lambda: spec.get('min', 0), 'number': lambda: spec.get('min', 0),
        'boolean': lambda: False, 'string': lambda: 'audit', 'array': lambda: [],
        'object': lambda: {}, 'enum': lambda: spec['values'][0]}[spec['type']]()


graph = BOStateGraph(archive, build_id='audit')
observed = graph.bo_observe('audit-run', state=archive['machine']['initial'],
    context={k: sample(s) for k, s in archive['machine']['context'].items()}, revision=0,
    evidence_id='invalid-resource', build_id='audit', configuration=cfg)
findings.append({'id': 'invalid_activity_configuration', 'independent_status': observed['status'],
    'independent_errors': observed['errors'], 'project_validator': diagnostic(lambda: validate_configuration(archive, cfg))})

contract = {'checks': [{'id': 'actual_effect', 'case': 'finish', 'requirement': 'R1', 'path': ['effects'], 'equals': 1}]}
model = simple_model()
payload = {'machine': model['machine'], 'runs': [
    {'case': 'finish', 'mode': mode, 'observations': {'effects': 0}, 'events': [{'node': 'finish', 'phase': 'commit'}]}
    for mode in ('on', 'off', 'fault')]}
required = [{'case': 'finish', 'node': 'finish', 'phase': 'commit'}]
with tempfile.TemporaryDirectory(prefix='bo-audit-', dir=ROOT / '.validation') as folder:
    root = Path(folder)
    original = json.loads((archive_root / 'sync.json').read_text(encoding='utf-8'))
    original['probe_modes'] = []
    (root / 'sync.json').write_text(json.dumps(original), encoding='utf-8')
    config_result = diagnostic(lambda: config(root, 'sync.json'))
    config_result.pop('value', None)
    findings.append({'id': 'empty_probe_modes', 'configuration_accepted': config_result,
        'normal_errors': assess_observations(model, contract, payload, ['on', 'off', 'fault'], required),
        'empty_modes_errors': assess_observations(model, contract, payload, [], required)})

    # New source files are outside the fingerprint until explicitly enrolled.
    (root / 'app.py').write_text('def execute():\n    return 1\n', encoding='utf-8')
    (root / 'intent.json').write_text(json.dumps({'requirements': [{'id': 'R1', 'status': 'confirmed', 'source': 'synthetic audit fixture'}]}), encoding='utf-8')
    scoped = {'schema_version': 3, 'revision': '1', 'intent': 'intent.json', 'source_files': ['app.py'],
        'nodes': [{'id': 'call', 'kind': 'function', 'label': 'execute', 'summary': 'synthetic call', 'source': {'path': 'app.py', 'symbol': 'execute'}}],
        'edges': [{'id': 'same', 'from': 'call', 'to': 'call', 'type': 'flow', 'evidence': 'synthetic'}],
        'overview': [{'node': 'call'}], 'scope': {'unknowns': ['unselected source files']}}
    baseline = capture(root, scoped)
    (root / 'new_entry.py').write_text('def new_entry():\n    return "not enrolled"\n', encoding='utf-8')
    findings.append({'id': 'unlisted_source', 'new_file': 'new_entry.py', 'binding_check': check(root, scoped, baseline),
        'scope': 'This proves lack of new-file discovery, not that a watched edit is missed.'})

mini_root = ROOT / 'examples/python-modes'
mini_model = json.loads((mini_root / 'bo_stategraph/model.json').read_text(encoding='utf-8'))
findings.append({'id': 'mini_schema_interoperability', 'declared_schema': mini_model['schema_version'],
    'independent_module': diagnostic(lambda: BOStateGraph(mini_model, build_id='audit')),
    'v3_validator': diagnostic(lambda: validate(mini_root, mini_model))})
findings.append({'id': 'strict_enum_type', 'input': True, 'spec': {'type': 'enum', 'values': [1]},
    'errors': bo_value_errors(True, {'type': 'enum', 'values': [1]}, 'flag')})

live = {'endpoint': 'http://localhost:8824/api/stategraph'}
try:
    with urlopen(live['endpoint'], timeout=10) as response:
        exported = json.load(response)
    runtime = exported.get('runtime', {})
    live.update(build_id=exported.get('build_id'), binding=exported.get('binding'),
        nodes=len(exported['model']['nodes']), edges=len(exported['model']['edges']),
        independent_instances=len(exported.get('instances', [])),
        runtime_configurations=len(runtime.get('machine', {}).get('configurations', [])),
        runtime_events=len(runtime.get('events', [])),
        current_state=runtime.get('machine', {}).get('current'))
except Exception as exc:
    live['error'] = str(exc)
result = {'checked_at': datetime.now(timezone.utc).isoformat(), 'python': sys.version,
    'transitions': importlib.metadata.version('transitions'), 'findings': findings, 'live_read_only': live}
(Path(__file__).parent / 'reproductions.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(result, ensure_ascii=False, indent=2))
