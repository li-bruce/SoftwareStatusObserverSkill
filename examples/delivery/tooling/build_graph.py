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
    node('flow.input','读取本次内容','Delivery.prepare',summary='读取文本和参数版本')
    node('flow.permission','检查执行权限','authorized',summary='操作者有执行角色，且至少一份授权有效')
    node('flow.checks','检查内容','run_checks',path='app/checks.py',summary='两项检查都通过后，才能提交',
         outputs={'revision':'number','activity':'string','event':'string'})
    node('flow.commit','提交交付物','Delivery.commit',summary='提交前再次检查权限和参数版本')
    node('flow.wait','等待或重新执行','Delivery.command',summary='补充授权或修改内容后，可以重新检查')
    node('read','读取输入','Delivery.prepare','flow.input',kind='action',outputs={'param_version':'number','length':'number'})
    node('execute','检查并提交指定版本','Delivery.execute','flow.input',kind='action',
         inputs={'expected_version':'number'},summary='这条命令只提交启动时指定的内容版本')
    node('authorize','判断授权是否有效','authorized','flow.permission',kind='decision',
         inputs={'role':'string','grants':'number'},outputs={'allowed':'boolean','evaluated_grants':['string']},predicate='engineer AND ANY eligible grant')
    node('grant','检查一份授权','eligible_grant','flow.permission',kind='decision',
         inputs={'grant_id':'string','grant_version':'number','param_version':'number','clock':'number','expires':'number'},
         outputs={'allowed':'boolean','evaluated':['string'],
                  'conditions':{k:'boolean' for k in ('project','actor','version','not_revoked','not_expired')}},
         summary='保留实际执行的条件；短路跳过的条件没有结果')
    for resource in execution['resources']:
        node(resource['id'],resource['label'],'ActivityExecution.start',execution['parent'],path='bo_stategraph/workflow.py',
             kind='data',execution_role='resource',summary='每项检查占用一个名额，结束后归还')
    for activity in execution['activities']:
        checksum=activity['id']=='checksum'
        node(activity['id'],activity['label'],activity['source']['symbol'],execution['parent'],
             path=activity['source']['path'],execution_role='activity',inputs={'length':'number'},
             outputs={'state':'string',**({'checksum':'string'} if checksum else {'safe':'boolean'})},
             summary='计算文本的 SHA-256 摘要' if checksum else '检查文本是否包含 SECRET: 标记')
    join=execution['join']
    node(join['id'],join['label'],'ActivityExecution.join',execution['parent'],kind='decision',path='bo_stategraph/workflow.py',
         execution_role='join',outputs={'passed':'boolean','tasks':['string']},predicate='ALL checks passed',
         summary='等待两项检查结束；只有全部通过才继续')
    for id,label,symbol,parent,path in [
        ('execution.init','建立本次活动状态','ActivityExecution.__init__','workers','bo_stategraph/workflow.py'),
        ('execution.finish','记录结果并归还名额','ActivityExecution.finish','workers','bo_stategraph/workflow.py'),
        ('execution.invariant','核对可用和占用的名额','ActivityExecution.invariant','workers','bo_stategraph/workflow.py'),
        ('execution.snapshot','读取全部内部状态','ActivityExecution.snapshot','workers','bo_stategraph/workflow.py'),
        ('execution.progress','保存这次运行的状态','Delivery.execution_progress','workers','app/service.py'),
        ('execution.abort','取消未开始的检查','ActivityExecution.abort','join','bo_stategraph/workflow.py'),
        ('execution.lookup','查找指定运行','Store.execution','execution.progress','app/store.py'),
        ('execution.save','保存指定运行','Store.put_execution','execution.progress','app/store.py'),
        ('execution.update','更新指定运行的流程状态','Store.update_execution','execution.progress','app/store.py'),
        ('execution.all','查询全部运行','Store.snapshot','execution.progress','app/store.py')]:
        node(id,label,symbol,parent,path=path)
    node('recheck','提交前再次检查','Delivery.commit','flow.commit',kind='decision',outputs={'allowed':'boolean','version_ok':'boolean'})
    node('commit','保存交付物','Delivery.commit','flow.commit',kind='effect',outputs={'version':'number','checksum':'string'})
    node('effect.storage','写入交付物记录','Store.artifact','commit',path='app/store.py',analysis_level='advanced')
    node('job.storage','保存任务参数','Store.put','flow.input',path='app/store.py',analysis_level='advanced')
    for ident,label,symbol in [('execution.record','保存完整实例','execution_record'),
            ('execution.advance','推进并保存流程状态','advance_record'),
            ('execution.recover','标记中断实例','recover_records')]:
        node(ident,label,symbol,'flow.checks',path='bo_stategraph/workflow.py',analysis_level='advanced')
    node('transition.storage','保存实际迁移','Store.record_transition','execution.advance',path='app/store.py',analysis_level='advanced')
    node('wait','说明不能继续的原因','Delivery.prepare','flow.wait',kind='wait',outputs={'reason':'string'})
    node('change','修改、取消或补充授权','Delivery.command','flow.wait',kind='action',outputs={'action':'string','state':'string'})
    for state in machine['values']:
        group='input' if state=='draft' else 'checks' if state=='checking' else 'commit' if state in ('ready','completed') else 'wait'
        node('state.'+state,machine['labels'][state],'advance','flow.'+group,kind='state',path='bo_stategraph/workflow.py',layer='state',value=state)
    def edge(a,b,type,label,**extra):
        edges.append({'id':a+'>'+b+':'+type,'from':a,'to':b,'type':type,'label':label,
                      'evidence':'executable declaration' if type in ('resource','join') else 'business mapping and source binding',**extra})
    for a,b,type,label in [('read','authorize','data','使用本次参数'),('grant','authorize','data','任一有效授权可通过'),('authorize','checksum','guard','有执行权限'),
        ('authorize','privacy','guard','有执行权限'),('join','recheck','guard','两项检查通过'),
        ('recheck','commit','guard','当前权限和版本仍有效'),('authorize','wait','flow','缺少有效授权'),
        ('recheck','wait','flow','权限或版本已改变'),('change','read','flow','重新读取内容')]:edge(a,b,type,label)
    for a in execution['activities']:
        for rid,units in a['requires'].items():edge(rid,a['id'],'resource',f'占用 {units} 个名额；结束后归还',units=units)
        edge(a['id'],join['id'],'join','等待这项检查完成')
    for n in nodes:
        if n.get('parent'):edge(n['parent'],n['id'],'contains','查看内部')
    files=sorted(p.relative_to(ROOT).as_posix() for folder in ('app','integrations') for p in (ROOT/folder).glob('*.py'))
    files+=[p.relative_to(ROOT).as_posix() for p in (ROOT/'bo_stategraph').glob('*.py')]
    files+=['tooling/build_graph.py','requirements.txt','observer_generated/runtime/recording_session.py','observer_generated/runtime/bo_stategraph.py',
            'observer_generated/runtime/bo_design.py','observer_generated/runtime/bo_web.py']
    files += [p.relative_to(ROOT).as_posix() for p in (ROOT/'integrations/bo_view').glob('*') if p.suffix in ('.js','.html','.css')]
    roots=['flow.input','flow.permission','flow.checks','flow.commit','flow.wait']
    model={'schema_version':3,'revision':revision,'intent':'intent.json','source_files':files,'nodes':nodes,'edges':edges,
           'overview':[{'node':n,'x':i*400,'y':0} for i,n in enumerate(roots)],'graph_roots':roots,'machine':machine,
           'presentation':{'subject':'数据交付','layout_id':'delivery-example','execution_projection':'inline',
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
    model['source_files'].append('implementation.json')
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
