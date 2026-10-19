"""Exercise clarification through the real change_sync CLI and a runnable program."""
from copy import deepcopy
import json
from pathlib import Path
from datetime import datetime
import cochange_fixture as f
OUT=f.ROOT/'.validation'/('gate-'+datetime.now().strftime('%Y%m%d-%H%M%S-%f'))

def main():
    root=f.prepare(OUT/'program');report={'root':str(root),'steps':[]}
    def save_report():f.save(OUT/'report.json',report)
    def check(name,action,success,expected=None,extra=()):
        code,value=f.sync(root,action,*extra)
        assert (code==0)==success,(name,value)
        if expected:assert expected in json.dumps(value,ensure_ascii=False),(name,value)
        report['steps'].append({'name':name,'passed':True,'exit_code':code,'result':value});save_report()
        print(json.dumps({'step':name,'passed':True}),flush=True)
        return value
    cfg=json.loads((root/'sync.json').read_text(encoding='utf-8'));cfg['discovery']='discovery.json';f.save(root/'sync.json',cfg)
    contract=json.loads((root/'acceptance.json').read_text(encoding='utf-8'))
    viewer=[c for c in contract['checks'] if c['case']=='bad_role']
    doc={'schema':'business-discovery/v1','goal':'明确任务工具中谁可以提交任务',
        'sources':[{'id':'U1','kind':'user','text':'研究员提交任务，观测者是否允许提交还没有确定。','locator':'集成测试的合成初始需求'}],
        'networks':[{'id':'submission','title':'任务提交权限','actors':['研究员','观测者'],'trigger':'提交任务请求','outcome':'允许的角色执行；其他角色不产生提交',
                     'nodes':[{'id':'permission','label':'判断角色是否可以执行','kind':'condition','source_refs':['U1'],'model_nodes':['authorize']}],'edges':[]}],
        'decisions':[{'id':'D1','topic':'authority','blocking':True,'status':'open','source_refs':['U1'],'affects':['permission'],
                      'question':'观测者也可以提交任务吗？','why':'这决定角色检查是否允许 viewer 产生提交。'}]}
    f.save(root/'discovery.json',doc)
    check('开始时保存未决问题','begin',True,extra=('--change','.stategraph/clarify-1','--request','先澄清提交角色，再检查原程序。','--requirements','R2'))
    f.review(root)
    check('关键问题未回答，不能交付','verify',False,'unanswered_business_questions')
    assert not (root/'.stategraph/clarify-1/checks/observations.json').exists()
    doc['sources'].append({'id':'U2','kind':'user','text':'只有 engineer 可以提交，viewer 只能查看。','locator':'集成测试的合成用户回答'})
    doc['decisions'][0].update(status='resolved',resolution={'kind':'user_answer','text':'仅 engineer 可以执行。','source_refs':['U2']},
                               links={'requirements':list({c['requirement'] for c in viewer}),'model_nodes':['authorize'],'checks':[c['id'] for c in viewer]})
    f.save(root/'discovery.json',doc);f.review(root)
    check('回答已关联原图和权限反例，运行检查通过','verify',True)
    check('验收同一回答和实现','accept',True);check('当前回答与验收一致','check',True)
    accepted=deepcopy(doc)
    doc['decisions'][0]['resolution']['text']='允许 viewer 提交。';f.save(root/'discovery.json',doc)
    check('回答改变使旧验收失效','check',False,'verification is failed or stale')
    f.save(root/'discovery.json',accepted)
    check('开始下一次需求调整','begin',True,extra=('--change','.stategraph/clarify-2','--request','测试已确认角色规则的调整记录，最终保留原行为。','--requirements','R2'))
    removed=deepcopy(accepted);removed['decisions']=[];f.save(root/'discovery.json',removed);f.review(root)
    check('删除已确认问题不能隐藏原决定','verify',False,'decision_changed_without_history')
    f.save(root/'discovery.json',None);f.review(root)
    check('空记录不能绕过已接入的澄清检查','verify',False,'expected_object')
    f.save(root/'discovery.json',accepted);without=deepcopy(cfg);without.pop('discovery');f.save(root/'sync.json',without);f.review(root)
    check('删除配置不能静默取消澄清检查','verify',False,'configured discovery was removed')
    f.save(root/'sync.json',cfg);f.save(root/'discovery.json',accepted);f.review(root)
    check('恢复原规则后通过实际运行','verify',True);check('验收恢复后的记录','accept',True);check('最终检查','check',True)
    report.update(passed=True,steps_count=len(report['steps']));save_report()
    f.save(f.ROOT/'.validation/gate.json',{'path':str(OUT.relative_to(f.ROOT)),'passed':True,'steps':len(report['steps'])})
    print(json.dumps({'passed':True,'steps':len(report['steps']),'report':str(OUT/'report.json')},ensure_ascii=False))

if __name__=='__main__':main()
