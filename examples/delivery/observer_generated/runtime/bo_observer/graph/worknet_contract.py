"""Validate selected bounded P/T-net declarations and actual firing journals.

Replay checks token accounting and declared guards, not arbitrary action semantics.
"""
def validate_net(definition, runtime=None, snapshot=None):
    places=definition['places']
    if len(places)!=len(set(places)) or not places:raise ValueError('invalid places')
    transitions={t['id']:t for t in definition['transitions']}
    if len(transitions)!=len(definition['transitions']):raise ValueError('duplicate transition')
    for t in transitions.values():
        for field in ('consume','produce'):
            if not isinstance(t[field],dict):raise ValueError('arcs must map places to weights')
            for p,w in t[field].items():
                if p not in places or type(w) is not int or w<1:raise ValueError('invalid weighted arc')
    for resource in definition.get('resources',[]):
        if set(resource['places'])-set(places):raise ValueError('resource invariant references unknown place')
    if runtime is not None and runtime!=definition:raise ValueError('graph and runtime work-net declarations differ')
    if not snapshot:return {'valid':True,'firings':0}
    def check(marking):
        if set(marking)!=set(places) or any(type(v) is not int or v<0 for v in marking.values()):
            raise ValueError('invalid marking')
        for r in definition.get('resources',[]):
            capacity=snapshot[r['capacity_field']]
            if type(capacity) is not int or not definition['capacity']['min']<=capacity<=definition['capacity']['max']:
                raise ValueError('invalid resource capacity')
            if sum(marking[p] for p in r['places'])!=capacity:raise ValueError('resource conservation violated: '+r['id'])
    current={p:0 for p in places}
    for p,value in definition['initial'].items():current[p]=snapshot[value] if isinstance(value,str) else value
    check(current)
    for event in snapshot['journal']:
        if event['before']!=current:raise ValueError('firing journal is discontinuous')
        t=transitions[event['transition']]
        if t.get('guard') and not event.get('guards',{}).get(t['guard']):raise ValueError('fired without guard')
        if any(current[p]<w for p,w in t['consume'].items()):raise ValueError('fired without tokens')
        for p,w in t['consume'].items():current[p]-=w
        for p,w in t['produce'].items():current[p]+=w
        if current!=event['after']:raise ValueError('firing does not match declared arcs')
        check(current)
    if current!=snapshot['marking']:raise ValueError('snapshot differs from journal')
    enabled=[name for name,t in transitions.items() if all(current[p]>=w for p,w in t['consume'].items())
             and (not t.get('guard') or snapshot.get('guards',{}).get(t['guard'],False))]
    if sorted(enabled)!=sorted(snapshot['enabled']):raise ValueError('enabled transitions differ from marking and guards')
    return {'valid':True,'firings':len(snapshot['journal'])}


if __name__=='__main__':
    import argparse
    import json
    from pathlib import Path
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--model',required=True);p.add_argument('--observations')
    a=p.parse_args()
    try:
        model=json.loads(Path(a.model).read_text(encoding='utf-8-sig'))
        results=[validate_net(model['worknet'])]
        if a.observations:
            payload=json.loads(Path(a.observations).read_text(encoding='utf-8-sig'))
            if not payload.get('worknet'):raise ValueError('runtime worknet definition is required')
            results.append(validate_net(model['worknet'],payload['worknet']))
            results += [validate_net(model['worknet'],snapshot=r.get('worknet')) for r in payload['runs']]
        print(json.dumps({'valid':True,'checks':results}));raise SystemExit(0)
    except (OSError,ValueError,KeyError,TypeError) as exc:
        print(json.dumps({'valid':False,'error':str(exc)}));raise SystemExit(1)
