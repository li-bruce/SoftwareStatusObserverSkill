"""Compare mapped observations with independently read implementation facts.

No desired business outcome belongs here. A faithfully displayed defect can pass
this check while the separately authored business contract fails.
"""
import json


def instance_witnesses(instances, actual, *, case, source):
    """actual is read from the application's store by the scenario runner."""
    mapped = {i['observed']['instance_id']: i['observed'] for i in instances}
    result = [{'id': case + ':instances', 'source': source, 'projection': 'bo_instances.instance_id',
               'actual': sorted(actual), 'mapped': sorted(mapped)}]
    for ident, fields in actual.items():
        for name, value in fields.items():
            result.append({'id': f'{case}:{ident}:{name}', 'source': source,
                'projection': 'bo_instances.' + name, 'actual': value, 'mapped': mapped.get(ident, {}).get(name)})
    return result


def assess(payload, *, required=False):
    checks = payload.get('mapping_checks', [])
    errors = []
    if required and not checks: errors.append('no implementation mapping witnesses')
    seen = set()
    for check in checks:
        ident = check.get('id')
        if not ident or ident in seen:
            errors.append('missing or duplicate mapping check identity')
        seen.add(ident)
        if not check.get('source') or not check.get('projection'):
            errors.append({'check': ident, 'error': 'source and projection provenance required'})
        if 'actual' not in check or 'mapped' not in check:
            errors.append({'check': ident, 'error': 'missing actual or mapped value'})
            continue
        encode = lambda value: json.dumps(value, sort_keys=True, allow_nan=False, ensure_ascii=False)
        if encode(check['actual']) != encode(check['mapped']):
            errors.append({'check': ident, 'error': 'mapped value differs from implementation',
                           'actual': check['actual'], 'mapped': check['mapped']})
    return {'valid': not errors, 'errors': errors, 'checks': len(checks),
            'scope': 'Explicit implementation witnesses; unexercised behavior remains unknown.'}
