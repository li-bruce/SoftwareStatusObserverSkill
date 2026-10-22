"""Read-only design graph and conversation focus, before or during coding.

The user answers in their coding assistant. This module only projects authored
requirements and stores which nodes that conversation is currently discussing.
"""
import argparse
import hashlib
import json
from pathlib import Path

try:
    from .behavior_model import contained
    from .requirements_dialogue import assess, read
    from .sync_io import write
    from .view_preferences import file_lock
except ImportError:
    from behavior_model import contained
    from requirements_dialogue import assess, read
    from sync_io import write
    from view_preferences import file_lock


def bo_digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                    allow_nan=False).encode()).hexdigest()


class BODesign:
    def __init__(self, root, discovery=None):
        self.root = Path(root).absolute().resolve()
        config = self.root / 'sync.json'
        cfg = read(config) if config.exists() else {}
        self.path = contained(self.root, discovery or cfg.get('discovery', 'discovery.json'))

    def document(self):
        doc = read(self.path)
        result = assess(doc)
        if not result['valid']:
            raise ValueError('需求记录无效：' + json.dumps(result['errors'], ensure_ascii=False))
        return doc

    def _identities(self, doc):
        nodes = [n for net in doc['networks'] for n in net['nodes']]
        for n in nodes:
            links = n.get('model_nodes', [])
            if not isinstance(links, list) or any(not isinstance(x, str) or not x.strip() for x in links):
                raise ValueError('设计节点标识无效：' + n['id'])
        return {n['id']: (n.get('model_nodes') or [n['id']]) for n in nodes}

    def snapshot(self):
        if not self.path.exists(): return {'available': False}
        doc = self.document()
        path = contained(self.root, 'bo_stategraph/config/design-focus.json')
        focus = read(path) if path.exists() else {'schema': 1, 'nodes': [], 'label': ''}
        if not isinstance(focus, dict) or focus.get('schema') != 1 or not isinstance(focus.get('nodes'), list) or any(not isinstance(x, str) for x in focus['nodes']) or not isinstance(focus.get('label'), str):
            raise ValueError('对话聚焦配置无效')
        return {'available': True, 'revision': bo_digest(focus), 'nodes': focus['nodes'],
                'label': focus['label'], 'stale': bool(focus.get('discovery_revision') and focus['discovery_revision'] != bo_digest(doc))}

    def focus(self, nodes, label='', decision=None):
        doc = self.document()
        identities = self._identities(doc)
        if decision:
            item = next((d for d in doc['decisions'] if d['id'] == decision), None)
            if item is None: raise ValueError('找不到这个需求问题')
            affected = list(item['affects'])
            for net in doc['networks']:
                for edge in net['edges']:
                    if edge['id'] in affected: affected.extend([edge['from'], edge['to']])
            nodes = [n for n in affected if n in identities]
        ids = sorted({mid for node in nodes for mid in identities.get(node, [node])})
        known = {mid for values in identities.values() for mid in values}
        cfg = read(self.root / 'sync.json') if (self.root / 'sync.json').exists() else {}
        if cfg.get('model'):
            known.update(n['id'] for n in read(contained(self.root, cfg['model']))['nodes'])
        if set(ids) - known: raise ValueError('聚焦节点不存在：' + ', '.join(sorted(set(ids) - known)))
        if len(ids) > 50 or not isinstance(label, str) or len(label) > 120: raise ValueError('局部图最多 50 个节点，说明限 120 字')
        path = contained(self.root, 'bo_stategraph/config/design-focus.json')
        with file_lock(path.with_suffix('.lock')):
            write(path, {'schema': 1, 'nodes': ids, 'label': label.strip(), 'discovery_revision': bo_digest(doc)})
        return self.snapshot()

    def view(self):
        """A declaration-only projection using reserved implementation node IDs."""
        doc = self.document()
        raw = [n for net in doc['networks'] for n in net['nodes']]
        identities = {key: values[0] for key, values in self._identities(doc).items()}
        if len(set(identities.values())) != len(identities):
            raise ValueError('设计节点需有独立主标识；共享关系请用连线表示')
        nodes = []
        for n in raw:
            kind = {'action': 'action', 'condition': 'decision', 'event': 'data'}.get(n['kind'], n['kind'])
            parent = identities.get(n.get('parent'))
            if n.get('parent') and parent is None:
                raise ValueError('设计节点的父节点不存在：' + n['id'])
            nodes.append({'id': identities[n['id']], 'label': n['label'], 'kind': kind,
                          'layer': 'business' if kind == 'action' else 'state' if kind == 'state' else 'design',
                          'summary': n.get('summary', ''), 'origin': 'design', 'capture': {},
                          **({'parent': parent} if parent else {})})
        # Reject containment cycles rather than hiding them as an empty graph.
        parents = {n['id']: n.get('parent') for n in nodes}
        for ident in parents:
            seen = set()
            while ident is not None:
                if ident in seen: raise ValueError('设计节点层级存在循环')
                seen.add(ident); ident = parents.get(ident)
        edges = [{'id': e['id'], 'from': identities[e['from']], 'to': identities[e['to']],
                  'type': {'event': 'flow', 'retry': 'flow', 'cancel': 'flow'}.get(e['relation'], e['relation']),
                  'label': e['label'], 'origin': 'design'} for net in doc['networks'] for e in net['edges']]
        project = read(self.root / 'intent.json').get('project_id') if (self.root / 'intent.json').exists() else None
        project = project or doc.get('project_id') or self.root.name
        machine = {'values': [], 'labels': {}, 'transitions': []}
        return {'stage': 'design', 'layout_id': doc.get('layout_id', project),
                'model': {'project_id': project, 'nodes': nodes, 'edges': edges, 'machine': machine,
                          'graph_roots': [n['id'] for n in nodes if not n.get('parent')],
                          'presentation': {'subject': doc.get('title', '项目设计')}},
                'manifest': {'build_id': bo_digest(doc), 'bindings': {}}, 'binding_status': {'status': 'design'},
                'events': [], 'machine': {'configurations': [], 'current': None, 'journal': []},
                'authority': {'basis': {}, 'parameters': {}}, 'health': {'errors': 0, 'dropped': 0},
                'busy': False, 'historical': False, 'available_cases': ['live']}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('action', choices=['show', 'focus'])
    p.add_argument('--root', default='.')
    p.add_argument('--discovery')
    p.add_argument('--nodes', nargs='*', default=[])
    p.add_argument('--decision')
    p.add_argument('--label', default='')
    a = p.parse_args()
    try:
        design = BODesign(a.root, a.discovery)
        result = design.focus(a.nodes, a.label, a.decision) if a.action == 'focus' else design.snapshot()
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except (OSError, ValueError) as exc:
        print(json.dumps({'valid': False, 'error': str(exc)}, ensure_ascii=False)); return 1
    return 0


if __name__ == '__main__': raise SystemExit(main())
