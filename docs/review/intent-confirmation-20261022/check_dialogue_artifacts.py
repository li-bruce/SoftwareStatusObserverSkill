"""Independently check the concrete recorded clarification sequence of this trial."""
import argparse
import importlib.util
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', type=Path, default=Path(__file__).resolve().parents[4] / 'project-flow-trial-20261022')
    args = parser.parse_args()
    results = []
    snapshots = [json.loads((args.project / f'evidence/round-{i:03}/discovery.snapshot.json').read_text(encoding='utf-8-sig')) for i in (1, 2, 3)]
    validator_path = Path(__file__).resolve().parents[3] / 'skills/business-observer/scripts/requirements_dialogue.py'
    spec = importlib.util.spec_from_file_location('trial_dialogue_validator', validator_path)
    validator = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(validator)
    decisions = [{d['id']: d for d in doc['decisions']} for doc in snapshots]
    def check(name, ok, evidence):
        results.append({'check': name, 'passed': bool(ok), 'evidence': evidence})
    check('initial_ambiguities_remain_open', all(decisions[0][i]['status'] == 'open' and decisions[0][i]['blocking'] for i in ('D1','D2','D3')), 'round-001')
    check('answered_questions_closed', all(decisions[1][i]['status'] == 'resolved' for i in ('D1','D2','D3')), 'round-002')
    check('new_execution_authority_is_open', decisions[1]['D4']['status'] == 'open' and decisions[1]['D4']['blocking'], 'round-002')
    check('ambiguous_reply_not_fabricated_as_answer', decisions[2]['D4']['status'] == 'open' and not decisions[2]['D4'].get('resolution'), 'round-003')
    check('answered_questions_not_repeated', all(decisions[2][i]['asked_in'] == decisions[1][i]['asked_in'] == decisions[0][i]['asked_in'] for i in ('D1','D2','D3')), 'rounds 001-003')
    nodes = [{n['id'] for net in doc['networks'] for n in net['nodes']} for doc in snapshots]
    check('graph_identity_preserved', nodes[0] <= nodes[1] == nodes[2], 'rounds 001-003')
    check('only_execution_authority_node_added', nodes[1]-nodes[0] == {'execute_permission'}, 'round-002 minus round-001')
    for i in (1,2,3):
        gate = json.loads((args.project / f'evidence/round-{i:03}/discovery-completion-check.json').read_text(encoding='utf-8-sig'))
        check(f'round_{i}_unfinished_gate_not_passed', not gate['ready'] and bool(gate['blocked']), f'round-{i:03}/discovery-completion-check.json')
        actual = validator.assess(snapshots[i-1])
        check(f'round_{i}_independent_validator_blocks', actual['valid'] and not actual['ready'] and actual['blocked'] == gate['blocked'], f'recomputed from round-{i:03}/discovery.snapshot.json')
    report={'scope':'Stored records and identity, not automated proof of natural-language meaning','checks':results,'passed':all(x['passed'] for x in results)}
    (Path(__file__).parent/'dialogue-artifact-checks.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(json.dumps({'passed':report['passed'],'checks':len(results)}))
    raise SystemExit(0 if report['passed'] else 1)


if __name__ == '__main__':
    main()
