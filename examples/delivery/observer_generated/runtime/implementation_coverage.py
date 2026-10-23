"""Source-first feature coverage; independent of the current graph selection.

This checks explicit source/feature/parameter/event obligations. It does not infer
business meaning from names, or claim semantic completeness of arbitrary Python.
"""
from __future__ import annotations
import re
from copy import deepcopy
from pathlib import PurePosixPath
try:
    from .semantic_probe import selected
except ImportError:
    from semantic_probe import selected

SCHEMA = 'bo-implementation/v1'
SECRET = re.compile(r'password|passwd|secret|token|cookie', re.I)
CONTEXT = {'self', 'cls', 'events', 'observer', 'trace', 'response',
           'progress', 'task_hook', 'parent_call_id', 'basis', 'call_id', 'parent', 'source_event', 'db'}


def functional_symbols(index):
    return {k: v for k, v in index.get('symbols', {}).items() if v['kind'] == 'function'}


def inventory_errors(cfg,inventory):
    errors=[]
    if cfg.get('stategraph'):
        if '.' not in cfg.get('source_scope',{}).get('roots',['.']):
            errors.append('implementation inventory must scan the project root; use explicit infrastructure exclusions')
        for path,declarations in inventory.get('excluded_entrypoints',{}).items():
            errors.append({'excluded_application_entrypoint':path,'declarations':declarations})
        for path in inventory.get('excluded_implementations',[]):
            errors.append({'excluded_application_implementation':path,'action':'inventory its functions and map them; only infrastructure can be excluded'})
        for path in sorted(set(inventory.get('files',{}))-set(cfg.get('code_files',[]))):
            errors.append({'unregistered_source':path,'action':'map implementation or record an explicit scope exclusion'})
    return errors


def infrastructure(symbol, category):
    path = PurePosixPath(symbol['path'])
    name = symbol['symbol'].split('.')[-1]
    if category == 'construction':
        return name in {'__init__', '__enter__', '__exit__'}
    return category == 'observer' and (path.stem.startswith(('bo_', 'observer_'))
        or path.name == 'ports.py' or path.name == 'run.py'
        or name.startswith('bo_') or any(part.startswith('BO') for part in symbol['symbol'].split('.')))


def static_errors(plan, model, index):
    errors = []
    if not isinstance(plan, dict) or plan.get('schema') != SCHEMA:
        return ['implementation coverage requires a bo-implementation/v1 inventory; existing graph nodes are not an inventory']
    if not isinstance(plan.get('features'), list) or not all(isinstance(f,dict) for f in plan['features']):
        return ['implementation features must be an array of objects']
    for section in ('support','excluded'):
        if not isinstance(plan.get(section,{}),dict) or not all(isinstance(v,dict) for v in plan.get(section,{}).values()):
            return ['implementation '+section+' must map source identities to objects']
    for f in plan['features']:
        if not all(isinstance(f.get(k,[]),list) and all(isinstance(x,str) for x in f.get(k,[])) for k in ('nodes','sources','requirements')):
            return ['feature nodes, sources and requirements must be string arrays']
        if not all(isinstance(f.get(k,[]),list) and all(isinstance(x,dict) for x in f.get(k,[])) for k in ('parameters','cases')):
            return ['feature parameters and cases must be object arrays']
    symbols = functional_symbols(index)
    nodes = {n['id']: n for n in model['nodes']}
    features = plan.get('features', [])
    if not features or len({f.get('id') for f in features}) != len(features):
        errors.append('implementation coverage needs unique, nonempty features')
    classified, covered_nodes = set(), set()
    for feature in features:
        fid = feature.get('id')
        owned = feature.get('nodes', [])
        entries = feature.get('sources', [])
        if not fid or not feature.get('label') or not owned or not entries:
            errors.append({'invalid_feature': fid})
        for node in owned:
            if node not in nodes:
                errors.append({'feature_missing_node': fid, 'node': node})
        covered_nodes.update(owned)
        if not any(any(nodes.get(n, {}).get('capture', {}).values()) for n in owned):
            errors.append({'feature_has_no_observed_values': fid})
        business_node = nodes.get(feature.get('business_node'), {})
        if not business_node or (business_node.get('layer') != 'business' and 'business' not in business_node.get('semantic_roles', [])):
            errors.append({'feature_missing_business_projection': fid})
        cases = feature.get('cases', [])
        if not cases or any(not c.get('case') or c.get('node') not in owned or not c.get('phase') for c in cases):
            errors.append({'feature_missing_runtime_cases': fid})
        parameters = feature.get('parameters', [])
        identities = [(p.get('source'), p.get('name')) for p in parameters]
        if len(identities) != len(set(identities)):
            errors.append({'duplicate_parameter_disposition': fid})
        expected = set()
        for sid in entries:
            if sid not in symbols:
                errors.append({'feature_missing_source': fid, 'symbol': sid})
                continue
            classified.add(sid)
            expected.update((sid, p['name']) for p in symbols[sid]['parameters'] if p['name'] not in {'self', 'cls'})
            if not any(n.get('source') == {'path': symbols[sid]['path'], 'symbol': symbols[sid]['symbol']}
                       for n in nodes.values()):
                errors.append({'feature_source_not_in_graph': fid, 'symbol': sid})
        for source, name in sorted(expected - set(identities)):
            errors.append({'uncovered_parameter': name, 'symbol': source, 'feature': fid})
        for p in parameters:
            if (p.get('source'), p.get('name')) not in expected:
                errors.append({'stale_parameter_disposition': p, 'feature': fid})
            policy = p.get('policy', 'value')
            if policy == 'context':
                if p.get('name') not in CONTEXT or not p.get('reason', '').strip():
                    errors.append({'invalid_context_parameter': p, 'feature': fid})
                continue
            if policy not in {'value', 'derived', 'redacted'} or (policy != 'value' and not p.get('reason', '').strip()):
                errors.append({'invalid_parameter_policy': p, 'feature': fid})
            capture = nodes.get(p.get('node'), {}).get('capture', {}).get(p.get('direction', 'in'), {})
            if p.get('node') not in owned or p.get('field') not in capture:
                errors.append({'parameter_without_capture': p, 'feature': fid})
            if SECRET.search(p.get('name', '')) and policy not in {'derived', 'redacted'}:
                errors.append({'sensitive_parameter_requires_safe_projection': p.get('name'), 'feature': fid})
            if SECRET.search(p.get('name', '')) and policy == 'derived' and capture.get(p.get('field')) not in ('boolean','number'):
                errors.append({'sensitive_projection_must_be_presence_or_length': p.get('name'), 'feature': fid})
    for sid, item in plan.get('support', {}).items():
        if sid not in symbols or not isinstance(item, dict) or item.get('node') not in nodes or not item.get('reason', '').strip():
            errors.append({'invalid_support_mapping': sid})
        else:
            classified.add(sid)
            if symbols[sid].get('entrypoints'):
                errors.append({'entrypoint_requires_feature': sid, 'entrypoints': symbols[sid]['entrypoints']})
    # Exclusions are limited to infrastructure. Observable endpoints cannot be
    # waived with a review sentence or called a generic helper.
    for sid, item in plan.get('excluded', {}).items():
        if sid not in symbols or not isinstance(item, dict) or not infrastructure(symbols[sid],item.get('category')) or not item.get('reason', '').strip():
            errors.append({'invalid_implementation_exclusion': sid})
        else:
            classified.add(sid)
            if symbols[sid].get('entrypoints'):
                errors.append({'entrypoint_cannot_be_excluded': sid})
        if sid in symbols and symbols[sid].get('entrypoints') and not any(isinstance(e,dict) and e.get('entrypoint_cannot_be_excluded')==sid for e in errors):
            errors.append({'entrypoint_cannot_be_excluded': sid})
    for sid in sorted(set(symbols) - classified):
        errors.append({'unclassified_implementation': sid})
    for node in nodes.values():
        if any(node.get('capture', {}).values()) and node['id'] not in covered_nodes:
            errors.append({'capture_without_feature': node['id']})
    return errors


def main():
    import argparse
    import json
    from pathlib import Path
    try:
        from .behavior_model import read, contained
        from .bo_sync import source_inventory
        from .code_structure import scan
    except ImportError:
        from behavior_model import read, contained
        from bo_sync import source_inventory
        from code_structure import scan
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=['inventory','check'])
    parser.add_argument('--root',required=True)
    parser.add_argument('--config',default='sync.json')
    parser.add_argument('--observations')
    parser.add_argument('--out')
    args=parser.parse_args();root=Path(args.root).resolve()
    cfg=read(contained(root,args.config));inventory=source_inventory(root,cfg)
    index=scan(root,inventory['files'])
    if args.command=='inventory':
        value={'inventory':inventory,'symbols':functional_symbols(index),'unresolved_calls':index['unresolved'],'errors':index['errors']}
    else:
        model=read(contained(root,cfg['model']));plan=model.get('implementation')
        errors=inventory_errors(cfg,inventory)+index['errors']+static_errors(plan,model,index)
        value={'valid':not errors,'errors':errors}
        if args.observations and not errors:
            value['runtime']=runtime_errors(plan,model,read(contained(root,args.observations)))
            value['valid']=not value['runtime']['errors']
    text=json.dumps(value,ensure_ascii=False,indent=2)
    if args.out:
        target=contained(root,args.out);target.parent.mkdir(parents=True,exist_ok=True)
        target.write_text(text+'\n',encoding='utf-8',newline='\n')
        print(json.dumps({'written':args.out,'valid':value.get('valid',not value.get('errors'))}))
    else: print(text)
    return 0 if value.get('valid',not value.get('errors')) else 1


def runtime_errors(plan, model, payload):
    errors, count = [], 0
    nodes = {n['id']: n for n in model['nodes']}
    for feature in plan.get('features', []):
        seen = set()
        for case in feature.get('cases', []):
            runs = [r for r in payload.get('runs', []) if r.get('mode') == 'on' and r.get('case') == case['case']]
            events = [e for r in runs for e in r.get('events', []) if e.get('node') == case['node'] and e.get('phase') == case['phase']]
            if len(runs) != 1 or not events:
                errors.append({'feature_event_missing': feature['id'], **case})
            for event in events:
                count += 1
                if payload.get('build_id') and event.get('build_id') != payload['build_id']:
                    errors.append({'feature_event_build_mismatch': feature['id'], 'case': case['case']})
                for p in feature.get('parameters', []):
                    if p.get('policy')=='redacted' and p.get('node')==event['node']:
                        value=event.get('inputs' if p.get('direction','in')=='in' else 'outputs',{}).get(p.get('field'))
                        if value not in (None,'[REDACTED]'):
                            errors.append({'unredacted_parameter':p.get('name'),'node':event['node']})
                for direction, key in [('in', 'inputs'), ('out', 'outputs')]:
                    fields = event.get(key, {})
                    for field, value in fields.items():
                        seen.add((event['node'], direction, field))
                        spec = nodes.get(event['node'], {}).get('capture', {}).get(direction, {})
                        if field not in spec:
                            errors.append({'undeclared_feature_field': field, 'node': event['node']})
                        else:
                            try:
                                if selected(value, spec[field]) != value:
                                    raise ValueError('undeclared nested fields')
                            except (ValueError, TypeError) as exc:
                                errors.append({'invalid_feature_value': field, 'node': event['node'], 'error': str(exc)})
                # Optional independent value witnesses compare real function/
                # HTTP/storage observations with captured values, not two probes.
                for witness in case.get('values', []):
                    try:
                        actual = runs[0]['observations']
                        for part in witness['path']:
                            actual = actual[part]
                        captured = event['inputs' if witness.get('direction', 'in') == 'in' else 'outputs'][witness['field']]
                        if type(actual) is not type(captured) or actual != captured:
                            raise ValueError('captured value differs from independent observation')
                    except (KeyError, IndexError, TypeError, ValueError) as exc:
                        errors.append({'feature_value_mismatch': feature['id'], 'case': case['case'], 'field': witness.get('field'), 'error': str(exc)})
        for nid in feature.get('nodes', []):
            for direction, fields in nodes.get(nid, {}).get('capture', {}).items():
                for field in fields:
                    if (nid, direction, field) not in seen:
                        errors.append({'feature_field_not_observed': feature['id'], 'node': nid, 'direction': direction, 'field': field})
    return {'errors': errors, 'events_checked': count, 'features': len(plan.get('features', []))}


def protected_errors(before, after, moves=None, allowed_requirements=(), requirement_changes=None):
    if not before:
        return []
    if not after:
        return ['implementation coverage contract was removed']
    # A source deletion is handled by the source/intent migration review. Keeping
    # a feature while deleting its observation obligations is never an upgrade.
    errors = []
    before=deepcopy(before)
    replacements={old: new['path']+'::'+new['symbol'] for old,new in (moves or {}).items()}
    for feature in before.get('features', []):
        feature['sources']=[replacements.get(s,s) for s in feature.get('sources', [])]
        for parameter in feature.get('parameters', []):
            parameter['source']=replacements.get(parameter.get('source'),parameter.get('source'))
    old = {f['id']: f for f in before.get('features', [])}
    new = {f['id']: f for f in after.get('features', [])}
    for fid, feature in old.items():
        requirements=set(feature.get('requirements', []))
        if requirements and requirements<=set(allowed_requirements) and all((requirement_changes or {}).get(r,'').strip() for r in requirements):
            continue  # Only a requirement change recorded before coding can revise these obligations.
        if fid not in new:
            errors.append({'removed_feature_coverage': fid})
            continue
        for part in ['nodes', 'sources', 'parameters', 'cases']:
            for item in feature.get(part, []):
                if item not in new[fid].get(part, []):
                    errors.append({'weakened_feature_coverage': fid, 'part': part, 'removed': item})
    return errors


def protected_captures(before, after, allowed_requirements=(), requirement_changes=None):
    errors=[]
    old_nodes={n['id']:n for n in before.get('nodes',[])}
    new_nodes={n['id']:n for n in after.get('nodes',[])}
    for feature in (before.get('implementation') or {}).get('features',[]):
        requirements=set(feature.get('requirements',[]))
        if requirements and requirements<=set(allowed_requirements) and all((requirement_changes or {}).get(r,'').strip() for r in requirements):continue
        for nid in feature.get('nodes',[]):
            for direction,fields in old_nodes.get(nid,{}).get('capture',{}).items():
                for field,spec in fields.items():
                    if not preserves_spec(spec,new_nodes.get(nid,{}).get('capture',{}).get(direction,{}).get(field)):
                        errors.append({'weakened_feature_capture':feature['id'],'node':nid,'direction':direction,'field':field})
    return errors


def preserves_spec(old,new):
    if isinstance(old,dict):return isinstance(new,dict) and all(k in new and preserves_spec(v,new[k]) for k,v in old.items())
    if isinstance(old,list):return isinstance(new,list) and len(new)==len(old) and all(preserves_spec(a,b) for a,b in zip(old,new))
    return old==new


if __name__=='__main__':
    raise SystemExit(main())
