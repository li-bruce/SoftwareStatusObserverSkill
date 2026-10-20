"""Validate an exported statechart contract, optionally against the runtime definition.

This checks declaration consistency, not guard truth, transactionality or equivalence.
"""
import argparse
import json
from pathlib import Path


def validate_chart(model, runtime_definition=None):
    chart=model['machine']
    for key in ('engine','version','states','values','transitions','context','state_type','events','initial'):
        if not chart.get(key):raise ValueError('missing statechart field: '+key)
    values=set(chart['values'])
    if len(values)!=len(chart['values']):raise ValueError('duplicate state values')
    names=set()
    def descend(items,prefix=''):
        for item in items:
            name=prefix+(item if isinstance(item,str) else item['name'])
            if name in names:raise ValueError('duplicate state name')
            names.add(name)
            if isinstance(item,dict) and item.get('children'):
                descend(item['children'],name+'_')
    descend(chart['states'])
    if not values<=names:raise ValueError('unknown persisted state value')
    if chart['initial'] not in names:raise ValueError('unknown initial state')
    for name,spec in chart['context'].items():
        if spec.get('type') not in {'integer','number','boolean','string','enum','array','object'}:
            raise ValueError('unknown context type: '+name)
        if spec['type']=='enum' and not spec.get('values'):raise ValueError('enum needs values')
        if 'min' in spec and 'max' in spec and spec['min']>spec['max']:raise ValueError('invalid bounds')
    for t in chart['transitions']:
        if not isinstance(t.get('trigger'),str):raise ValueError('transition needs event name')
        if t['trigger'] not in chart['events'] or not isinstance(chart['events'][t['trigger']].get('payload'),dict):
            raise ValueError('transition event needs payload declaration')
        sources=t['source'] if isinstance(t['source'],list) else [t['source']]
        if any(s!='*' and s not in names for s in sources) or (t['dest'] is not None and t['dest'] not in names):
            raise ValueError('dangling transition')
        for field in ('conditions','unless'):
            refs=t.get(field,[]);refs=refs if isinstance(refs,list) else [refs]
            if set(refs)-set(chart.get('guards',{})):raise ValueError('undefined guard')
    represented={n['value'] for n in model['nodes'] if n.get('layer')=='state'}
    if values!=represented:raise ValueError('persisted states and graph projection differ')
    if runtime_definition is not None and chart!=runtime_definition:
        raise ValueError('graph and runtime statechart declarations differ')
    return {'valid':True,'states':len(values),'events':len({t['trigger'] for t in chart['transitions']}),
            'runtime_definition_compared':runtime_definition is not None}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('model');args=parser.parse_args()
    print(json.dumps(validate_chart(json.loads(Path(args.model).read_text(encoding='utf-8')))))
