"""Check the shipped native application and actual React/Vue handlers in both modes."""
from copy import deepcopy
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
from setup_adapters import configure

ROOT=Path(__file__).resolve().parents[1]
EXAMPLE=ROOT/'examples/multilanguage'
sys.path.insert(0,str(ROOT/'skills/vibelens/scripts'))
from behavior_model import capture
from code_structure import scan
from bo_sync import source_inventory
from implementation_coverage import inventory_errors,static_errors,runtime_errors
from bo_observer.protocol import validate_project,validate_event,validate_snapshot
from bo_stategraph import BOStateGraph
from bo_observer.adapters.python.bo_probe import BOProbe
from bo_observer.adapters.python.bo_executor import BOExecutor
from bo_observer.delivery.architecture_guard import inspect as inspect_architecture


def verify():
    configure()
    settings=EXAMPLE/'.stategraph/collector.json'
    temporary_settings=not settings.exists()
    if temporary_settings:
        settings.parent.mkdir(parents=True,exist_ok=True)
        settings.write_text('{}\n',encoding='utf-8')
    try:
        architecture=inspect_architecture(EXAMPLE,json.loads((EXAMPLE/'ownership.json').read_text(encoding='utf-8')))
        assert architecture['valid'],architecture['errors']
    finally:
        if temporary_settings:settings.unlink()
    project=json.loads((EXAMPLE/'bo_stategraph/project.json').read_text(encoding='utf-8'))
    validate_project(project);model=project['model'];build=capture(EXAMPLE,model)['build_id']
    cfg=json.loads((EXAMPLE/'source-scope.json').read_text(encoding='utf-8'))
    inventory=source_inventory(EXAMPLE,cfg);index=scan(EXAMPLE,inventory['files'])
    errors=inventory_errors({**cfg,'stategraph':True},inventory)+index['errors']+static_errors(model['implementation'],model,index)
    assert not errors,errors
    spec=importlib.util.spec_from_file_location('native_job',EXAMPLE/'src/job.py')
    job=importlib.util.module_from_spec(spec);spec.loader.exec_module(job)
    process=subprocess.run(['node','tooling/test.mjs'],cwd=EXAMPLE,env={**os.environ,'BO_TEST_BUILD':build},capture_output=True,text=True,encoding='utf-8',timeout=60)
    assert process.returncode==0,process.stdout+process.stderr
    reports=json.loads(process.stdout)
    for report in reports:
        p=deepcopy(project);p['selection']['mode']=report['development']
        for mode in ('on','off','fault'):
            events=[]
            def sink(body,kind):
                if mode=='fault':raise OSError('observation failure')
                if kind=='events':events.append(body)
            probe=BOProbe(p,build,enabled=mode!='off',sink=sink)
            executor=BOExecutor(model['machine'],{'available':lambda ctx,payload:ctx['slots']>0}) if report['development']=='drive' else None
            state='pending';states=[]
            try:
                for event,slots in [('start',0),('resume',1),('finish',1)]:
                    before=state;actual=job.advance(state,event,slots,executor);state=actual['state'];states.append(state)
                    probe.record('py.advance','change',lambda before=before,event=event,slots=slots,state=state:{'inputs':{'state':before,'event':event,'slots':slots,'mode':report['development']},'outputs':{'state':state}})
                probe.flush()
                assert states==['waiting','running','done'],states
                assert [e['outputs']['state'] for e in events]==(states if mode=='on' else [])
            finally:probe.close()
            report['runs'].append({'case':'python','mode':mode,'events':events,'observations':{'states':states}})
        for run in report['runs']:
            for event in run['events']:validate_event(event,p,build)
            snapshots=run.get('snapshots',[])
            events={e['id']:e for e in run['events']}
            assert {e['id'] for e in events.values() if 'revision' in e}=={s['evidence_id'] for s in snapshots}, 'state event lacks its actual snapshot'
            observed=BOStateGraph(model,build_id=build,mode=report['development'])
            for snapshot in snapshots:
                validate_snapshot(snapshot,p,build)
                event=events[snapshot['evidence_id']]
                assert event['revision']==snapshot['revision'] and event['outputs']['state']==snapshot['state']
                result=observed.bo_observe(snapshot['run_id']+':'+snapshot['instance_id'],**{k:snapshot[k] for k in ('state','context','revision','evidence_id','build_id','configuration','event','guards','payload')})
                assert result['accepted'] and result['status']=='observed',result
        checked=runtime_errors(model['implementation'],model,{'build_id':build,'runs':report['runs']})
        assert not checked['errors'],checked
        report['mapping']=checked
    evidence={'valid':True,'build_id':build,'source_symbols':len(index['symbols']),'reports':reports,'architecture':architecture,
        'scope':'Real native Python/JS execution and compiled React/Vue DOM handlers. HTTP transport has separate integration tests. Finite scenarios do not establish all program behavior.'}
    out=ROOT/'.validation/multilanguage-acceptance.json';out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(evidence,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'valid':True,'development_modes':len(reports),'cases':sum(len(r['runs']) for r in reports),'symbols':len(index['symbols']),'build_id':build,'evidence':str(out)}))
    return evidence

if __name__=='__main__':verify()
