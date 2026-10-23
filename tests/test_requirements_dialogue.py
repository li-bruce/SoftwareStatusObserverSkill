"""Meaningful cases for clarification records, question selection and decision links."""
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1]
SKILL=ROOT/'skills/business-observer'
TEMP=ROOT/'.validation/dialogue'
TEMP.mkdir(parents=True,exist_ok=True)
sys.path.insert(0,str(SKILL/'scripts'))
from requirements_dialogue import assess

def draft():return json.loads((SKILL/'assets/discovery.example.json').read_text(encoding='utf-8'))
def resolve(doc,did='D1',text="Allow download after format checks; preview continues in the background.",sid='U2'):
    if not any(s['id']==sid for s in doc['sources']):doc['sources'].append({'id':sid,'kind':'user','text':text,'locator':"Synthetic user answer, test fixture"})
    d=next(d for d in doc['decisions'] if d['id']==did)
    d.update(status='resolved',resolution={'kind':'user_answer','text':text,'source_refs':[sid]})
    return d
def extra(doc,did='D2',**kw):
    d=deepcopy(doc['decisions'][0]);d.update(id=did,status='open',question="Can retry create a second delivery?",topic='retry',**kw)
    d.pop('resolution',None);doc['decisions'].append(d);return d
def codes(result):return {e['code'] for e in result['errors']}

class DialogueTests(unittest.TestCase):
    def test_ambiguous_draft_is_valid_but_cannot_be_delivered(self):
        result=assess(draft());self.assertTrue(result['valid']);self.assertFalse(result['ready'])
        self.assertEqual(result['blocked'],['D1']);self.assertEqual([q['id'] for q in result['questions']],['D1'])

    def test_known_answer_ends_questioning(self):
        doc=draft();resolve(doc);result=assess(doc)
        self.assertTrue(result['ready']);self.assertEqual(result['questions'],[])

    def test_assistant_recommendation_is_not_a_user_answer(self):
        doc=draft();resolve(doc);doc['sources'][-1]['kind']='assistant'
        self.assertIn('not_a_decision_source',codes(assess(doc)))

    def test_inference_is_not_an_existing_project_rule(self):
        doc=draft();d=resolve(doc);d['resolution']['kind']='existing_rule';d['resolution']['source_refs']=['A1']
        self.assertFalse(assess(doc)['ready'])

    def test_actual_existing_rule_does_not_need_reasking(self):
        doc=draft();d=resolve(doc);doc['sources'][-1]['kind']='project_rule';d['resolution']['kind']='existing_rule'
        self.assertTrue(assess(doc)['ready']);self.assertEqual(assess(doc)['questions'],[])

    def test_delegated_choice_records_authorization_and_reason(self):
        doc=draft();d=resolve(doc,text="You decide whether download waits for preview; prioritize prompt download availability.")
        d['resolution'].update(kind='delegated_choice',text="Allow download after format checks.",rationale="Follow the user's timely-download goal and let preview continue in the background.")
        self.assertTrue(assess(doc)['ready'])
        d['resolution'].pop('rationale');self.assertFalse(assess(doc)['ready'])

    def test_silence_does_not_resolve_or_resend_a_question(self):
        doc=draft();doc['sources'].append({'id':'Q1','kind':'assistant','text':doc['decisions'][0]['question'],'locator':"Simulated round 1 sent"})
        doc['decisions'][0]['asked_in']=['Q1'];r=assess(doc)
        self.assertFalse(r['ready']);self.assertEqual(r['questions'],[]);self.assertEqual(r['awaiting_answers'],['D1'])

    def test_partial_answer_only_closes_its_question(self):
        doc=draft();extra(doc);resolve(doc);r=assess(doc)
        self.assertEqual(r['blocked'],['D2']);self.assertEqual([q['id'] for q in r['questions']],['D2'])

    def test_only_first_three_independent_questions_are_offered(self):
        doc=draft()
        for i in range(2,6):extra(doc,'D'+str(i),priority=2)
        self.assertEqual([q['id'] for q in assess(doc)['questions']],['D1','D2','D3'])

    def test_followup_question_waits_for_its_upstream_answer(self):
        doc=draft();extra(doc,depends_on=['D1'])
        self.assertEqual([q['id'] for q in assess(doc)['questions']],['D1'])
        resolve(doc);self.assertEqual([q['id'] for q in assess(doc)['questions']],['D2'])

    def test_business_loop_is_allowed_but_question_deadlock_is_not(self):
        doc=draft();doc['networks'][0]['edges'].append({'id':'retry','from':'validate','to':'upload','relation':'retry','label':"Correct and upload again",'source_refs':['U1']})
        self.assertTrue(assess(doc)['valid'])
        extra(doc,depends_on=['D1']);doc['decisions'][0]['depends_on']=['D2']
        self.assertIn('question_dependency_cycle',codes(assess(doc)))

    def test_connected_networks_can_share_dependencies_without_duplicate_nodes(self):
        doc=draft();n=doc['networks'][0];node=n['nodes'].pop()
        doc['networks'].append({'id':'delivery','title':"Provide file",'actors':["Downloader"],'trigger':"File available",'outcome':"Obtain file",'nodes':[node],'edges':[]})
        self.assertTrue(assess(doc)['valid'])

    def test_critical_assumption_or_defer_does_not_pass(self):
        for status in ('assumed','deferred'):
            doc=draft();doc['decisions'][0].update(status=status,note="No user answer yet")
            self.assertFalse(assess(doc)['ready'])

    def test_unanswered_behavior_cannot_be_relabelled_optional(self):
        doc=draft();doc['decisions'][0]['blocking']=False
        self.assertIn('behavior_question_cannot_be_optional',codes(assess(doc)))

    def test_reversible_presentation_assumption_is_visible_and_not_blocking(self):
        doc=draft();doc['decisions'][0].update(topic='presentation',blocking=False,status='assumed',note="Keep the project's existing button wording for now")
        r=assess(doc);self.assertTrue(r['ready']);self.assertEqual(r['warnings'][0]['code'],'explicit_assumption')

    def test_rule_change_needs_previous_answer_and_real_change_source(self):
        old=draft();resolve(old);doc=deepcopy(old);resolve(doc,text="Change download to require completed preview.",sid='U3')
        self.assertIn('decision_changed_without_history',codes(assess(doc,previous=old)))
        doc['changes']=[{'id':'C1','decision':'D1','previous':old['decisions'][0],'source_refs':['U3'],'reason':"The user explicitly changed the download condition"}]
        self.assertTrue(assess(doc,previous=old)['ready'])
        doc['changes'][0]['source_refs']=['A1'];self.assertFalse(assess(doc,previous=old)['ready'])

    def test_removing_an_old_question_cannot_hide_it(self):
        old=draft();doc=deepcopy(old);doc['decisions']=[];doc['networks'][0]['edges'][-1]['decision_refs']=[]
        self.assertIn('decision_changed_without_history',codes(assess(doc,previous=old)))

    def test_downgrading_a_pending_question_needs_a_recorded_change(self):
        old=draft();doc=deepcopy(old);doc['decisions'][0].update(blocking=False,topic='other')
        self.assertIn('decision_changed_without_history',codes(assess(doc,previous=old)))

    def test_answer_must_link_to_original_graph_and_the_right_test(self):
        doc=draft();d=resolve(doc)
        model={'nodes':[{'id':'flow.files'}]};intent={'requirements':[{'id':'R1'}]};acceptance={'checks':[{'id':'without_preview','requirement':'R1'}]}
        r=assess(doc,model=model,intent=intent,acceptance=acceptance)
        self.assertIn('business_node_not_mapped',codes(r));self.assertIn('missing_decision_link',codes(r))
        for n in doc['networks'][0]['nodes']:n['model_nodes']=['flow.files']
        d['links']={'requirements':['R1'],'model_nodes':['flow.files'],'checks':['without_preview']}
        self.assertTrue(assess(doc,model=model,intent=intent,acceptance=acceptance)['ready'])
        acceptance['checks'][0]['requirement']='other'
        self.assertIn('test_for_different_requirement',codes(assess(doc,model=model,intent=intent,acceptance=acceptance)))

    def test_malformed_records_fail_closed_without_a_question_plan(self):
        for value in (None,[],{}, {'schema':'x'}):
            r=assess(value);self.assertFalse(r['valid']);self.assertEqual(r['questions'],[])
        doc=draft();doc['decisions'][0]['depends_on']=None
        self.assertFalse(assess(doc)['valid'])

    def test_cli_check_rejects_open_question_and_accepts_actual_answer(self):
        with tempfile.TemporaryDirectory(dir=TEMP) as folder:
            path=Path(folder)/'discovery.json';doc=draft();path.write_text(json.dumps(doc),encoding='utf-8')
            args=[sys.executable,'-B','-X','utf8',str(SKILL/'scripts/requirements_dialogue.py'),'check','--file',str(path)]
            result=subprocess.run(args,capture_output=True,text=True,encoding='utf-8');self.assertEqual(result.returncode,1)
            self.assertFalse(json.loads(result.stdout)['valid'])
            resolve(doc);path.write_text(json.dumps(doc),encoding='utf-8')
            self.assertEqual(subprocess.run(args,capture_output=True).returncode,0)

    def test_malformed_linked_records_do_not_skip_history_or_crash(self):
        doc=draft();resolve(doc)
        for name in ('intent','model','acceptance','previous'):
            for value in ([],['bad'],'bad',0):
                r=assess(doc,**{name:value})
                self.assertFalse(r['ready']);self.assertEqual(r['questions'],[])
        with tempfile.TemporaryDirectory(dir=TEMP) as folder:
            path=Path(folder)/'discovery.json';path.write_text(json.dumps(doc),encoding='utf-8')
            previous=Path(folder)/'previous.json';previous.write_text('null',encoding='utf-8')
            args=[sys.executable,'-B','-X','utf8',str(SKILL/'scripts/requirements_dialogue.py'),'check','--file',str(path),'--previous',str(previous)]
            result=subprocess.run(args,capture_output=True,text=True,encoding='utf-8')
            self.assertEqual(result.returncode,1);self.assertFalse(json.loads(result.stdout)['valid'])


if __name__=='__main__':unittest.main()
