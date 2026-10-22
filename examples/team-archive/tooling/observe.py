"""Run real scenarios in three observation modes, with version binding."""
import json
from pathlib import Path
import sys
ROOT=Path(__file__).absolute().parents[1]
sys.path.insert(0,str(ROOT))
from observer_runtime.behavior_model import capture
from observer_runtime.mapping_contract import instance_witnesses
from bo_stategraph import BOStateGraph
from bo_stategraph.query import bo_machine


def main():
    model=json.loads((ROOT/"behavior.json").read_text(encoding="utf-8"))
    before=capture(ROOT,model)
    # Business modules load only after the candidate has been bound.
    from bo_stategraph.workflow import definition
    from tooling.scenarios import CASES, execute
    from tooling.size_scenarios import CASES as SIZE_CASES, execute as execute_size
    if capture(ROOT,model)["build_id"]!=before["build_id"]:
        raise RuntimeError("source changed while loading")
    runs=[]
    for mode in ("on","off","fault"):
        for case in CASES:
            runs.append(execute(case,mode,model,before["build_id"]))
        for case in SIZE_CASES:
            runs.append(execute_size(case,mode,model,before["build_id"]))
    graph=BOStateGraph(model,build_id=before['build_id'])
    witnesses=[]
    for run in runs:
        raw=run['authority_snapshot']
        actual={r['id']:{'state':r['phase'],'revision':r['state_revision'],
            'context':{'param_version':r['input']['content_version'],
                'capacity':r['configuration']['resources']['processing_slots']['capacity'],
                'operator_id':r['input']['operator_id'],'document_id':r['input']['document_id']}}
            for r in raw['runs']}
        instances=graph.bo_instances(bo_machine(raw,before['build_id']))
        run['projection']={'build_id':before['build_id'],'machine':bo_machine(raw,before['build_id']), 'instances':instances}
        witnesses.extend(instance_witnesses(instances,actual,case=run['case']+':'+run['mode'],
            source='archive_app.storage.ArchiveStore.snapshot / SQLite'))
        # Compare all activity/resource/wait/join values, not just the coarse phase.
        for instance in instances:
            observed=instance['observed']; original=next(r['configuration'] for r in raw['runs'] if r['id']==observed['instance_id'])
            witnesses.append({'id':run['case']+':'+run['mode']+':'+observed['instance_id']+':activities',
                'source':'SQLite runs.payload.configuration','projection':'bo_instances.configuration',
                'actual':original,'mapped':{k:observed['configuration'].get(k) for k in original}})
    selected=next(r for r in runs if r['case']=='archive_snapshot' and r['mode']=='on')
    exported=graph.bo_export(runtime={'machine':selected['projection']['machine']})
    print(json.dumps({"build_id":before["build_id"],"machine":definition(),"runs":runs,
        'mapping_checks':witnesses,'stategraph_export':exported},ensure_ascii=False))


if __name__=="__main__":
    main()
