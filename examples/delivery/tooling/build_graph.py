"""Project-owned business grouping; executable activities are projected in place."""
import json
from pathlib import Path
import sys
import shutil
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from bo_stategraph.workflow import definition
from observer_generated.runtime.code_structure import scan,enrich


def build():
    revision=json.loads((ROOT/'intent.json').read_text(encoding='utf-8'))['revision']
    machine=definition();execution=machine['execution'];nodes=[];edges=[]
    def node(id,label,symbol,parent=None,kind='function',path='app/service.py',inputs=None,outputs=None,**extras):
        nodes.append({'id':id,'label':label,'summary':extras.pop('summary',label),'kind':kind,
            'layer':'program' if parent else 'business','source':{'path':path,'symbol':symbol},
            'capture':{'in':inputs or {},'out':outputs or {}},**({'parent':parent} if parent else {}),**extras})
    node('flow.input',"Read the current content",'Delivery.prepare',summary="Read text and parameter version")
    node('flow.permission',"Check execution permission",'authorized',summary="The actor has an execution role and at least one valid authorization")
    node('flow.checks',"Check content",'run_checks',path='app/checks.py',summary="Both checks must pass before committing",
         outputs={'revision':'number','activity':'string','event':'string'})
    node('flow.commit',"Commit delivery",'Delivery.commit',summary="Recheck authorization and parameter version before commit")
    node('flow.wait',"Wait or retry",'Delivery.command',summary="Retry checks after authorization or content changes")
    node('read',"Read input",'Delivery.prepare','flow.input',kind='action',outputs={'param_version':'number','length':'number'})
    node('execute',"Check and commit the requested version",'Delivery.execute','flow.input',kind='action',
         inputs={'expected_version':'number'},summary="This command commits only the content version selected at start")
    node('authorize',"Evaluate authorization",'authorized','flow.permission',kind='decision',
         inputs={'role':'string','grants':'number'},outputs={'allowed':'boolean','evaluated_grants':['string']},predicate='engineer AND ANY eligible grant')
    node('grant',"Evaluate one authorization",'eligible_grant','flow.permission',kind='decision',
         inputs={'grant_id':'string','grant_version':'number','param_version':'number','clock':'number','expires':'number'},
         outputs={'allowed':'boolean','evaluated':['string'],
                  'conditions':{k:'boolean' for k in ('project','actor','version','not_revoked','not_expired')}},
         summary="Keep actual evaluated conditions; skipped short-circuit conditions have no result")
    for resource in execution['resources']:
        node(resource['id'],resource['label'],'ActivityExecution.start',execution['parent'],path='bo_stategraph/workflow.py',
             kind='data',execution_role='resource',summary="Each check acquires one slot and releases it on completion")
    for activity in execution['activities']:
        checksum=activity['id']=='checksum'
        node(activity['id'],activity['label'],activity['source']['symbol'],execution['parent'],
             path=activity['source']['path'],execution_role='activity',inputs={'length':'number'},
             outputs={'state':'string',**({'checksum':'string'} if checksum else {'safe':'boolean'})},
             summary="Compute the text SHA-256 digest" if checksum else "Check for the SECRET: marker")
    join=execution['join']
    node(join['id'],join['label'],'ActivityExecution.join',execution['parent'],kind='decision',path='bo_stategraph/workflow.py',
         execution_role='join',outputs={'passed':'boolean','tasks':['string']},predicate='ALL checks passed',
         summary="Wait for both checks; continue only if both pass")
    for id,label,symbol,parent,path in [
        ('execution.init',"Create this run's activity configuration",'ActivityExecution.__init__','workers','bo_stategraph/workflow.py'),
        ('execution.finish',"Record result and release the slot",'ActivityExecution.finish','workers','bo_stategraph/workflow.py'),
        ('execution.invariant',"Verify available and occupied slots",'ActivityExecution.invariant','workers','bo_stategraph/workflow.py'),
        ('execution.snapshot',"Read complete internal state",'ActivityExecution.snapshot','workers','bo_stategraph/workflow.py'),
        ('execution.progress',"Persist this run's state",'Delivery.execution_progress','workers','app/service.py'),
        ('execution.abort',"Cancel checks that have not started",'ActivityExecution.abort','join','bo_stategraph/workflow.py'),
        ('execution.lookup',"Find a specific run",'Store.execution','execution.progress','app/store.py'),
        ('execution.save',"Persist a specific run",'Store.put_execution','execution.progress','app/store.py'),
        ('execution.update',"Update a specific run's phase",'Store.update_execution','execution.progress','app/store.py'),
        ('execution.all',"Query all runs",'Store.snapshot','execution.progress','app/store.py')]:
        node(id,label,symbol,parent,path=path)
    node('recheck',"Recheck before commit",'Delivery.commit','flow.commit',kind='decision',outputs={'allowed':'boolean','version_ok':'boolean'})
    node('commit',"Persist delivery",'Delivery.commit','flow.commit',kind='effect',outputs={'version':'number','checksum':'string'})
    node('effect.storage',"Insert delivery record",'Store.artifact','commit',path='app/store.py',analysis_level='advanced')
    node('job.storage',"Save task parameters",'Store.put','flow.input',path='app/store.py',analysis_level='advanced')
    for ident,label,symbol in [('execution.record',"Persist the complete instance",'execution_record'),
            ('execution.advance',"Advance and persist the phase",'advance_record'),
            ('execution.recover',"Mark interrupted instances",'recover_records')]:
        node(ident,label,symbol,'flow.checks',path='bo_stategraph/workflow.py',analysis_level='advanced')
    node('transition.storage',"Record actual transition",'Store.record_transition','execution.advance',path='app/store.py',analysis_level='advanced')
    node('wait',"Explain why execution cannot continue",'Delivery.prepare','flow.wait',kind='wait',outputs={'reason':'string'})
    node('change',"Edit, cancel, or restore authorization",'Delivery.command','flow.wait',kind='action',outputs={'action':'string','state':'string'})
    for state in machine['values']:
        group='input' if state=='draft' else 'checks' if state=='checking' else 'commit' if state in ('ready','completed') else 'wait'
        node('state.'+state,machine['labels'][state],'advance','flow.'+group,kind='state',path='bo_stategraph/workflow.py',layer='state',value=state)
    def edge(a,b,type,label,**extra):
        edges.append({'id':a+'>'+b+':'+type,'from':a,'to':b,'type':type,'label':label,
                      'evidence':'executable declaration' if type in ('resource','join') else 'business mapping and source binding',**extra})
    for a,b,type,label in [('read','authorize','data',"Use this run's parameters"),('grant','authorize','data',"Any valid authorization permits execution"),('authorize','checksum','guard',"Execution permission granted"),
        ('authorize','privacy','guard',"Execution permission granted"),('join','recheck','guard',"Both checks passed"),
        ('recheck','commit','guard',"Current permission and version remain valid"),('authorize','wait','flow',"No valid authorization"),
        ('recheck','wait','flow',"Permission or version changed"),('change','read','flow',"Read content again")]:edge(a,b,type,label)
    for a in execution['activities']:
        for rid,units in a['requires'].items():edge(rid,a['id'],'resource',f'Acquire {units} slots; release on completion',units=units)
        edge(a['id'],join['id'],'join',"Wait for this check to finish")
    for n in nodes:
        if n.get('parent'):edge(n['parent'],n['id'],'contains',"Inspect internals")
    files=sorted(p.relative_to(ROOT).as_posix() for folder in ('app','integrations') for p in (ROOT/folder).glob('*.py'))
    files+=[p.relative_to(ROOT).as_posix() for p in (ROOT/'bo_stategraph').glob('*.py')]
    files+=['tooling/build_graph.py','requirements.txt','observer_generated/runtime/recording_session.py','observer_generated/runtime/bo_stategraph.py',
            'observer_generated/runtime/bo_design.py','observer_generated/runtime/bo_web.py',
            'observer_generated/runtime/observation_scope.py']
    files += [p.relative_to(ROOT).as_posix() for p in (ROOT/'integrations/bo_view').glob('*') if p.suffix in ('.js','.html','.css')]
    roots=['flow.input','flow.permission','flow.checks','flow.commit','flow.wait']
    model={'schema_version':3,'revision':revision,'intent':'intent.json','source_files':files,'nodes':nodes,'edges':edges,
           'overview':[{'node':n,'x':i*400,'y':0} for i,n in enumerate(roots)],'graph_roots':roots,'machine':machine,
           'presentation':{'subject':"Data delivery",'layout_id':'delivery-example','execution_projection':'inline',
                           'default_expanded':['flow.checks']},
           'scope':{'observable':['declared activity instances, capacity and waiting','authorization and parameter versions','committed SQLite effects'],
                    'unknowns':['unselected ordinary function locals','external services','process-crash worker restoration']}}
    model.setdefault('presentation', {})['recording']={'parameters': ['param_version', 'attempt', 'capacity', 'clock', 'epoch'], 'command_fields': ['id', 'project', 'version', 'role', 'expires', 'capacity', 'clock', 'expected_version']}
    for node in model['nodes']:
        if node['id'] in ['authorize', 'recheck', 'grant']: node['semantic_roles']=['permission']
        if node.get('execution_role') in ('resource','join'): node['analysis_level']='advanced'
    cfg=json.loads((ROOT/'sync.json').read_text(encoding='utf-8'))
    model['source_files']=sorted(set(model['source_files']+cfg['code_files']))
    model['implementation']=json.loads((ROOT/'implementation.json').read_text(encoding='utf-8'))
    model['source_files'] += ['implementation.json','bo_stategraph/machine.json']
    by_id={n['id']:n for n in model['nodes']}
    by_id['read']['capture']['in']={'expected_version':'number'}
    by_id['recheck']['capture']['in']={'expected_version':'number'}
    by_id['flow.checks']['capture']['in']={'capacity':'number','content_length':'number'}
    by_id['change']['capture']['in']={'action':'string','values':{k:t for k,t in [
        ('id','string'),('project','string'),('actor','string'),('version','number'),('expires','number'),
        ('role','string'),('clock','number'),('capacity','number'),('content_length','number')]}}
    model=enrich(model,scan(ROOT,cfg['code_files']),depth=1)
    (ROOT/'observer_generated/behavior.json').write_text(json.dumps(model,ensure_ascii=False,indent=2),encoding='utf-8',newline='\n')
    for source in (ROOT/'integrations/bo_view').glob('*'):shutil.copyfile(source,ROOT/'observer_generated/static'/source.name)
    return model


if __name__=='__main__':
    m=build();print(json.dumps({'revision':m['revision'],'nodes':len(m['nodes']),'edges':len(m['edges'])}))
