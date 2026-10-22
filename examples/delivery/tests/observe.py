"""Emit observations by executing the real program, not by consulting acceptance.json."""
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from observer_generated.runtime.behavior_model import capture
from observer_generated.runtime.mapping_contract import instance_witnesses
from bo_stategraph import BOStateGraph
from bo_stategraph.query import bo_machine

model=json.loads((ROOT/'observer_generated/behavior.json').read_text(encoding='utf-8'))
loaded=capture(ROOT,model)  # Bind before importing the business modules.
from bo_stategraph.workflow import definition
from tests.scenarios import CASES,exercise


def observe():
    runs=[exercise(case,model,loaded['build_id'],mode) for case in CASES for mode in ('on','off','fault')]
    if capture(ROOT,model)['build_id']!=loaded['build_id']:
        raise RuntimeError('source changed during execution')
    graph=BOStateGraph(model,build_id=loaded['build_id'])
    witnesses=[]
    for run in runs:
        raw=run['authority']
        machine=bo_machine(raw)
        run['projection']={'build_id':loaded['build_id'],'machine':machine,'instances':graph.bo_instances(machine)}
        actual={c['attempt']:{'state':c['phase'],'configuration':c,'revision':c['state_revision']} for c in raw['executions']}
        witnesses.extend(instance_witnesses(run['projection']['instances'],actual,
            case=run['case']+':'+run['mode'],source='app.store.Store.snapshot / SQLite'))
    selected=next(r for r in runs if r['case']=='normal' and r['mode']=='on')
    exported=graph.bo_export(runtime={'machine':selected['projection']['machine']})
    return {'build_id':loaded['build_id'],'machine':definition(),'runs':runs,
            'mapping_checks':witnesses,'stategraph_export':exported}


if __name__=='__main__':
    print(json.dumps(observe(),ensure_ascii=False))
