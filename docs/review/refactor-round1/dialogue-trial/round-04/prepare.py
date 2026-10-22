from pathlib import Path
import json
root=Path('.')
def write(p,v): Path(p).write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
x=json.loads(Path('discovery.json').read_text())
x['sources'] += [
 {'id':'U05','kind':'user','text':'新增打印机维护，维护期间不再接新任务，已开始打印不中断；退出维护后原队列按原顺序继续。后续普通 Python 函数实现，不再以状态机指导开发，图和监控继续维护。','locator':'主会话第四轮模拟需求；非真人测试'},
 {'id':'A04','kind':'assistant','text':'维护期间新提交是 A 照常接收、检查、审批和排队，仅阻止开始打印，还是 B 在提交入口拒绝？','locator':'上一轮实际最终回复；review/round-04/dialogue.md'},
 {'id':'U06','kind':'user','text':'选 A。维护期间仍然可以提交、检查、审批和排队，只阻止开始打印。由工作室管理员切换维护开关；普通提交者和审批人不能切换。维护可以手动结束，没有自动到期。按这个继续。','locator':'2026-10-22 主会话模拟用户实际答复；非真人测试'}]
for ident,topic,question,answer,affects,rid,asked in [
 ('D13','concurrency','维护期间如何处理新任务和已开始任务？','照常提交、检查、审批和排队；只阻止开始打印，已开始的打印不中断，退出后按原队列顺序继续。',['submit','checks','queue','printing','printer'],'R12',['A04']),
 ('D14','authority','谁能切换维护，是否自动到期？','仅工作室管理员可开启和结束维护；提交者和审批人不因此有此权。维护只能手动结束，无自动到期。',['maintenance','maintenance-permission','printer'],'R13',[]),
 ('D15','other','后续开发方式是什么？','按用户要求普通 Python 函数实现；development_mode=observe、execution_mode=observe，适配器读取真实状态，继续源码/实例/探针/回放及门禁。',['lifecycle','queue','printing'],'R11',[])]:
 x['decisions'].append({'id':ident,'topic':topic,'question':question,'why':'第四轮用户明确答复或直接要求','affects':affects,'blocking':True,'status':'resolved','priority':1,'source_refs':['U05','U06'],'asked_in':asked,'resolution':{'kind':'user_answer','text':answer,'source_refs':['U05','U06']},'links':{'requirements':[rid],'model_nodes':[],'checks':[]}})
# New discovery nodes preserve existing node identities.
network=x['networks'][0]
for ident,label in [('maintenance','管理员手动维护'),('maintenance-permission','工作室管理员资格')]:
 network['nodes'].append({'id':ident,'label':label,'kind':'action' if ident=='maintenance' else 'decision','model_nodes':[]})
write('discovery.json',x)
i=json.loads(Path('intent.json').read_text());i['revision']='round-04'
for r in i['requirements']:
 if r['id']=='R11':r['text']+=' 用户 U05 明确要求普通 Python 函数实现，状态网作为观察适配，继续全部映射及监控。';r['source']='discovery.json:U05'
i['requirements'] += [{'id':'R12','text':'维护期间允许提交、检查、审批和进入原顺序队列，只阻止新打印；已开始的打印不中断；退出维护按原队列顺序、当前有效资格继续。','status':'confirmed','source':'discovery.json:U05/U06'},{'id':'R13','text':'仅工作室管理员可切换维护；普通提交者和审批人不能切换。手动结束，无自动到期，维护标记持久化。','status':'confirmed','source':'discovery.json:U06'}]
write('intent.json',i)
a=json.loads(Path('acceptance.json').read_text())
expected={
 'maintenance_flow':{'running_continues':True,'new_checks_passed':True,'new_queued':True,'wait_reason':'printer_maintenance','after_complete_empty':True,'order_preserved':True,'first_resumes':True,'second_resumes':True},
 'maintenance_auth':{'denied':['alice','bob','carol','unknown'],'denied_exit':['alice','bob'],'no_denied_writes':True,'admin_enabled':True,'admin_disabled':True},
 'maintenance_scope':{'p1_waits':True,'p2_prints':True},
 'maintenance_restart':{'persists':True,'no_timeout':True,'manual_exit_starts':True},
 'maintenance_approval':{'invalid_stays_blocked':True,'valid_later_starts':True,'restored_order':True},
 'maintenance_cancel':{'stopping_holds':True,'confirm_releases':True,'maintenance_still_blocks':True,'exit_starts':True},
 'maintenance_race':{'maintenance_on':True,'serialized_start':True,'capacity_ok':True},
}
for case,values in expected.items():
 values['state_constraints']=True
 for key,value in values.items():a['checks'].append({'id':case+':'+key,'requirement':'R13' if case in ('maintenance_auth','maintenance_restart') else 'R12','case':case,'path':[key],'equals':value})
write('acceptance.json',a)
w=json.loads(Path('whitebox.json').read_text())
for rule in w['rules']:
 if rule['source']['path']=='bo_stategraph/workflow.py':rule['source']['path']='app/workflow.py'
w['rules'].append({'id':'maintenance-admin','requirement':'R13','node':'maintenance-permission','source':{'path':'app/policy.py','symbol':'is_administrator'},'parameters':{'actor':'str'},'category':'actual-values','claim':'Only database administrator membership authorizes maintenance','basis':'intent.json:R13'})
w['checks'].append({'id':'maintenance-admin-denied','rule':'maintenance-admin','case':'maintenance_auth','phase':'decision','count':{'min':1},'select':[{'path':['inputs','actor'],'equals':'bob'}],'fields':[{'path':['outputs','allowed'],'equals':False}]})
write('whitebox.json',w)
print({'new_cases':len(expected),'total_assertions_per_mode':len(a['checks'])})
