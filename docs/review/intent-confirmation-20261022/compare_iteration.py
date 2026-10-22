"""Compare the iteration with the frozen accepted initial source; preserve old assertions."""
import argparse
import hashlib
import json
from pathlib import Path
import zipfile


def contains_original(old, new):
    if isinstance(old, dict):
        return isinstance(new, dict) and all(k in new and contains_original(v, new[k]) for k, v in old.items())
    if isinstance(old, list):
        return isinstance(new, list) and all(any(contains_original(v, candidate) for candidate in new) for v in old)
    return type(old) is type(new) and old == new


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', type=Path, default=Path(__file__).resolve().parents[4] / 'project-flow-trial-20261022')
    parser.add_argument('--label', required=True)
    args = parser.parse_args()
    here = Path(__file__).parent
    out = here / 'execution' / args.label
    out.mkdir(parents=True, exist_ok=False)
    checks = []
    details = {}
    with zipfile.ZipFile(here / 'snapshots/02-initial-repaired.zip') as archive:
        old_bytes = {name.removeprefix('project/'): archive.read(name) for name in archive.namelist()}
    def before(name):
        return json.loads(old_bytes[name])
    def now(name):
        return json.loads((args.project / name).read_text(encoding='utf-8-sig'))
    def check(name, result, **evidence):
        checks.append({'name': name, 'passed': bool(result), **evidence})
    old_model, model = before('behavior.json'), now('behavior.json')
    old_nodes = {n['id']: n for n in old_model['nodes']}
    nodes = {n['id']: n for n in model['nodes']}
    check('existing_graph_node_ids_retained', set(old_nodes) <= set(nodes), before=len(old_nodes), after=len(nodes), missing=sorted(set(old_nodes)-set(nodes)))
    changed_bindings = [ident for ident, node in old_nodes.items() if ident not in nodes or node.get('source') != nodes[ident].get('source')]
    check('existing_source_anchors_retained', not changed_bindings, changed=changed_bindings)
    old_edges = {e['id'] for e in old_model['edges'] if e.get('origin') != 'python-ast'}
    check('authored_edge_ids_retained', old_edges <= {e['id'] for e in model['edges']})
    check('declared_machine_not_silently_replaced', old_model['machine'] == model['machine'])
    check('original_business_case_expectations_preserved', contains_original(before('tests/cases.json'), now('tests/cases.json')), before_cases=len(before('tests/cases.json')), after_cases=len(now('tests/cases.json')))
    for filename, key in [('acceptance.json','checks'), ('acceptance.json','model_checks'), ('whitebox.json','checks'), ('mapping.json','fields'), ('mapping.json','cases')]:
        old, new = before(filename).get(key), now(filename).get(key)
        check(filename + ':' + key + ':old_assertions_preserved', contains_original(old,new), before_count=len(old) if old is not None else 0, after_count=len(new) if new is not None else 0)
    check('existing_capture_fields_not_removed', contains_original(old_nodes['derive_project']['capture'], nodes['derive_project']['capture']))
    details['derive_capture_before'] = old_nodes['derive_project']['capture']
    details['derive_capture_after'] = nodes['derive_project']['capture']
    details['derive_labels_before'] = {n:old_nodes[n]['label'] for n in ['derive_project','project_derived']}
    details['derive_labels_after'] = {n:nodes[n]['label'] for n in ['derive_project','project_derived']}
    details['new_graph_node_ids'] = sorted(set(nodes)-set(old_nodes))
    changed = []
    for name, data in old_bytes.items():
        path = args.project / name
        if not path.exists():
            changed.append({'path':name, 'change':'deleted'})
        elif path.read_bytes() != data:
            changed.append({'path':name, 'change':'modified', 'before_sha256':hashlib.sha256(data).hexdigest(), 'after_sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
    details['changed_existing_files'] = changed
    report = {'scope':'Stable graph identities and previous assertions; authorized R2 meaning changes reviewed separately', 'checks':checks, 'details':details, 'passed':all(c['passed'] for c in checks)}
    (out/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(json.dumps({'passed':report['passed'],'checks':len(checks),'failed':[c['name'] for c in checks if not c['passed']]}))
    raise SystemExit(0 if report['passed'] else 1)


if __name__ == '__main__':
    main()
