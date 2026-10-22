"""Shared, application-independent model and value contracts.

The project checker, standalone module and exports use these same rules.
Runtime violations are diagnostics; callers must preserve the actual facts.
"""
import math


def value_errors(value, spec, name):
    kind = spec.get('type')
    matches = {
        'integer': type(value) is int,
        'number': type(value) in (int, float) and math.isfinite(value),
        'boolean': type(value) is bool,
        'string': isinstance(value, str),
        'array': isinstance(value, list),
        'object': isinstance(value, dict),
        'enum': any(type(value) is type(item) and value == item for item in spec.get('values', [])),
    }
    if not matches.get(kind, False):
        return [f'{name}: expected {kind}']
    errors = []
    if kind in ('integer', 'number'):
        if 'min' in spec and value < spec['min']: errors.append(f'{name}: below min')
        if 'max' in spec and value > spec['max']: errors.append(f'{name}: above max')
    if kind == 'array' and spec.get('items'):
        for i, item in enumerate(value):
            errors.extend(value_errors(item, spec['items'], f'{name}[{i}]'))
    if kind == 'object':
        for key in spec.get('required', []):
            if key not in value: errors.append(f'{name}.{key}: missing')
        for key, item in spec.get('properties', {}).items():
            if key in value: errors.extend(value_errors(value[key], item, f'{name}.{key}'))
    return errors


def state_tree(chart):
    """Return actual engine names and ancestry; underscores are not split heuristically."""
    states, parents = {}, {}
    separator = chart.get('separator', '_')
    if separator != '_':
        raise ValueError('unsupported state separator: ' + str(separator))
    def descend(items, parent=None):
        for item in items:
            data = {'name': item} if isinstance(item, str) else item
            name = (parent + separator if parent else '') + data['name']
            if name in states: raise ValueError('duplicate state name')
            if data.get('history'):
                raise ValueError('history states require a supported engine adapter')
            states[name], parents[name] = data, parent
            descend(data.get('parallel') or data.get('children') or [], name)
    descend(chart['states'])
    return states, parents


def active_states(chart, value):
    states, parents = state_tree(chart)
    leaves = []
    def collect(item):
        if isinstance(item, list):
            for child in item: collect(child)
        else: leaves.append(item)
    collect(value)
    if not leaves or len(set(leaves)) != len(leaves) or any(s not in states for s in leaves):
        raise ValueError('unknown or duplicate active state')
    result = set(leaves)
    for leaf in leaves:
        parent = parents[leaf]
        while parent:
            result.add(parent)
            parent = parents[parent]
    # Concurrent leaves are legal only in distinct regions of a parallel state.
    # A parent plus its active child is not a second active leaf.
    for parent in [None, *states]:
        children = [s for s, p in parents.items() if p == parent and s in result]
        parallel = parent is not None and bool(states[parent].get('parallel'))
        if len(children) > 1 and not parallel:
            raise ValueError('exclusive states cannot be active together')
        if parent in result and parallel:
            declared = [s for s, p in parents.items() if p == parent]
            if set(children) != set(declared):
                raise ValueError('parallel configuration is missing an active region')
        if parent in leaves and children:
            raise ValueError('active configuration repeats an ancestor')
    return result


def validate_graph(model):
    if model.get('schema_version') == 3:
        for key in ('revision', 'intent', 'source_files', 'nodes', 'edges', 'overview', 'scope'):
            if not model.get(key): raise ValueError('missing ' + key)
    elif model.get('schema_version') not in (None, 'bo-model/v1'):
        raise ValueError('unsupported model schema')
    nodes = {n['id']: n for n in model.get('nodes', [])}
    if not nodes or len(nodes) != len(model['nodes']): raise ValueError('invalid node identities')
    for node in nodes.values():
        seen = {node['id']}
        parent = node.get('parent')
        while parent:
            if parent not in nodes or parent in seen: raise ValueError('missing parent or hierarchy cycle')
            seen.add(parent)
            parent = nodes[parent].get('parent')
        if model.get('schema_version') == 3:
            if node.get('kind') not in {'action', 'function', 'decision', 'wait', 'effect', 'data', 'state'}:
                raise ValueError('invalid node kind')
            if not node.get('label') or not node.get('summary'):
                raise ValueError('node lacks developer explanation')
            if node['kind'] not in {'data', 'state'} and not node.get('source'):
                raise ValueError('executable node lacks source: ' + node['id'])
    edges = set()
    for edge in model.get('edges', []):
        if edge['id'] in edges or edge['from'] not in nodes or edge['to'] not in nodes:
            raise ValueError('duplicate/dangling edge')
        edges.add(edge['id'])
        if model.get('schema_version') == 3 and (edge.get('type') not in
                {'flow', 'data', 'guard', 'contains', 'resource', 'join'} or not edge.get('evidence')):
            raise ValueError('edge needs type and provenance')
        if edge.get('type') in ('resource', 'join') and not model.get('machine', {}).get('execution'):
            raise ValueError('resource and join edges need an executable activity declaration')
    for item in model.get('overview', []):
        if item['node'] not in nodes: raise ValueError('unknown overview node')
    return nodes


def validate_chart(model, runtime_definition=None):
    validate_graph(model)
    chart = model['machine']
    # Compact models are explicit bo-model/v1 or legacy unversioned declarations.
    fields = ('states', 'values', 'transitions', 'events', 'initial', 'context')
    if model.get('schema_version') == 3:
        fields += ('engine', 'version', 'state_type')
    for key in fields:
        if key not in chart or chart[key] is None: raise ValueError('missing statechart field: ' + key)
    states, _ = state_tree(chart)
    values = set(chart['values'])
    if not values or len(values) != len(chart['values']): raise ValueError('duplicate or missing state values')
    if not values <= states.keys(): raise ValueError('unknown persisted state value')
    if chart['initial'] not in states: raise ValueError('unknown initial state')
    for name, spec in chart['context'].items():
        if spec.get('type') not in {'integer', 'number', 'boolean', 'string', 'enum', 'array', 'object'}:
            raise ValueError('unknown context type: ' + name)
        if spec['type'] == 'enum' and not spec.get('values'): raise ValueError('enum needs values')
        if 'min' in spec and 'max' in spec and spec['min'] > spec['max']: raise ValueError('invalid bounds')
    for transition in chart['transitions']:
        event = transition.get('trigger')
        if event not in chart['events'] or not isinstance(chart['events'][event].get('payload'), dict):
            raise ValueError('transition event needs payload declaration')
        sources = transition['source']
        sources = sources if isinstance(sources, list) else [sources]
        if any(s != '*' and s not in states for s in sources) or (
                transition['dest'] is not None and transition['dest'] not in states):
            raise ValueError('dangling transition')
        for field in ('conditions', 'unless'):
            refs = transition.get(field, [])
            refs = refs if isinstance(refs, list) else [refs]
            if set(refs) - set(chart.get('guards', {})): raise ValueError('undefined guard')
    represented = {n['value'] for n in model['nodes'] if n.get('layer') == 'state'}
    if values != represented: raise ValueError('persisted states and graph projection differ')
    if runtime_definition is not None and chart != runtime_definition:
        raise ValueError('graph and runtime statechart declarations differ')
    try:
        from .execution_contract import validate_execution_graph
    except ImportError:
        from execution_contract import validate_execution_graph
    validate_execution_graph(model)
    return {'valid': True, 'states': len(values), 'events': len(chart['events']),
            'runtime_definition_compared': runtime_definition is not None}
