"""Explicit source-identity moves without weakening protected observations.

Only source locations can be rebound. Assertions, node/phase requirements and
business expectations remain unchanged and still run against the new source.
"""
from copy import deepcopy


def source_key(source):
    if not isinstance(source, dict) or set(source) != {'path', 'symbol'}:
        return None
    if any(not isinstance(v, str) or not v.strip() for v in source.values()):
        return None
    return source['path'] + '::' + source['symbol']


def source_moves(review, base, current):
    entries = review.get('source_moves', [])
    if not isinstance(entries, list):
        return {}, ['source_moves must be an explicit list']
    moves, targets, errors = {}, set(), []
    old_symbols = base.get('structure', {}).get('symbols', {})
    new_symbols = current.get('structure', {}).get('symbols', {})
    new_nodes = {n['id']: n for n in current.get('model', {}).get('nodes', [])}
    for entry in entries:
        if not isinstance(entry, dict):
            errors.append('source move needs from, to and reason')
            continue
        old, new = source_key(entry.get('from')), source_key(entry.get('to'))
        reason = entry.get('reason')
        if (not old or not new or old == new or old not in old_symbols or new not in new_symbols
                or not isinstance(reason, str) or not reason.strip()):
            errors.append({'invalid_source_move': entry})
            continue
        if old in moves or new in targets:
            errors.append({'ambiguous_source_move': entry})
            continue
        # Authored graph identities must follow the moved symbol. Generated AST
        # helpers can be regenerated with their own local IDs.
        anchors = [n for n in base.get('model', {}).get('nodes', [])
                   if n.get('origin') != 'python-ast' and source_key(n.get('source')) == old]
        if any(source_key(new_nodes.get(n['id'], {}).get('source')) != new for n in anchors):
            errors.append({'source_move_lost_graph_identity': entry})
            continue
        moves[old] = deepcopy(entry['to'])
        targets.add(new)
    return moves, errors


def rebind_probe(probe, moves):
    value = deepcopy(probe)
    if isinstance(value, dict) and value.get('symbol') in moves:
        value['symbol'] = source_key(moves[value['symbol']])
    return value


def rebind_whitebox(item, moves):
    value = deepcopy(item)
    key = source_key(value.get('source'))
    if key in moves:
        value['source'] = deepcopy(moves[key])
    return value
