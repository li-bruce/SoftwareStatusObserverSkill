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
    doc={'schema':'business-discovery/v1','goal':"Clarify who may submit tasks",
        'sources':[{'id':'U1','kind':'user','text':"Researchers submit tasks; viewer submission is not yet decided.",'locator':"Synthetic initial request for integration testing"}],
        'networks':[{'id':'submission','title':"Task submission permission",'actors':["Researcher","Viewer"],'trigger':"Submit a task request",'outcome':"Allowed roles execute; other roles create no submission",
                     'nodes':[{'id':'permission','label':"Check whether the role may execute",'kind':'condition','source_refs':['U1'],'model_nodes':['authorize']}],'edges':[]}],
        'decisions':[{'id':'D1','topic':'authority','blocking':True,'status':'open','source_refs':['U1'],'affects':['permission'],
                      'question':"May viewers also submit tasks?",'why':"This determines whether the role check permits viewer submissions."}]}
    f.save(root/'discovery.json',doc)
    check("Record unresolved questions at the start",'begin',True,extra=('--change','.stategraph/clarify-1','--request',"Clarify submission roles before checking the original program.",'--requirements','R2'))
    f.review(root)
    check("Unanswered critical questions block delivery",'verify',False,'unanswered_business_questions')
    assert not (root/'.stategraph/clarify-1/checks/observations.json').exists()
    doc['sources'].append({'id':'U2','kind':'user','text':"Only engineer may submit; viewer may only inspect.",'locator':"Synthetic user answer for integration testing"})
    doc['decisions'][0].update(status='resolved',resolution={'kind':'user_answer','text':"Only engineer may execute.",'source_refs':['U2']},
                               links={'requirements':list({c['requirement'] for c in viewer}),'model_nodes':['authorize'],'checks':[c['id'] for c in viewer]})
    f.save(root/'discovery.json',doc);f.review(root)
    check("Answer is bound to the graph and permission counterexample; checks passed",'verify',True)
    check("Accept the same answer and implementation",'accept',True);check("Current answer matches acceptance",'check',True)
    accepted=deepcopy(doc)
    doc['decisions'][0]['resolution']['text']="Allow viewer to submit.";f.save(root/'discovery.json',doc)
    check("A changed answer invalidates old acceptance",'check',False,'verification is failed or stale')
    f.save(root/'discovery.json',accepted)
    check("Begin the next requirement change",'begin',True,extra=('--change','.stategraph/clarify-2','--request',"Test the history of a confirmed role change; retain original behavior in the end.",'--requirements','R2'))
    removed=deepcopy(accepted);removed['decisions']=[];f.save(root/'discovery.json',removed);f.review(root)
    check("Deleting a confirmed question cannot hide the original decision",'verify',False,'decision_changed_without_history')
    f.save(root/'discovery.json',None);f.review(root)
    check("Empty records cannot bypass an established clarification gate",'verify',False,'expected_object')
    f.save(root/'discovery.json',accepted);without=deepcopy(cfg);without.pop('discovery');f.save(root/'sync.json',without);f.review(root)
    check("Removing configuration cannot silently disable clarification checks",'verify',False,'configured discovery was removed')
    f.save(root/'sync.json',cfg);f.save(root/'discovery.json',accepted);f.review(root)
    check("Restore the original rule and verify actual execution",'verify',True);check("Accept the restored record",'accept',True);check("Final check",'check',True)
    report.update(passed=True,steps_count=len(report['steps']));save_report()
    f.save(f.ROOT/'.validation/gate.json',{'path':str(OUT.relative_to(f.ROOT)),'passed':True,'steps':len(report['steps'])})
    print(json.dumps({'passed':True,'steps':len(report['steps']),'report':str(OUT/'report.json')},ensure_ascii=False))

if __name__=='__main__':main()
