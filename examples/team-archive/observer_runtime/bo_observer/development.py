"""Separate human business confirmations from coding-side implementation evidence."""
from copy import deepcopy
from collections import Counter
import hashlib


MODE_QUESTION = {
    'id':'development-mode', 'audience':'user',
    'question':'Should the project execute from this state declaration, or retain its own implementation and let the graph observe it? Both modes maintain the graph and monitoring.',
    'options':{'drive':'Develop from the state declaration','observe':'Observe the existing implementation'},
}


def validate_selection(selection):
    if not isinstance(selection,dict) or selection.get('mode') not in {'drive','observe'}:
        raise ValueError('initial user choice is required: drive or observe')
    if selection.get('source')!='user' or not selection.get('answer','').strip() or not selection.get('locator','').strip():
        raise ValueError('mode needs the user answer and conversation locator; silence is not a choice')
    return deepcopy(selection)


def questions(project,index=None,discovery=None):
    human=[];coding=[]
    try:validate_selection(project.get('selection'))
    except (ValueError,TypeError):human.append(deepcopy(MODE_QUESTION))
    for decision in (discovery or {}).get('decisions',[]):
        if decision.get('status')=='open':
            human.append({'id':decision['id'],'audience':'user','question':decision.get('question',''),
                          'basis':decision.get('basis',decision.get('reason','')),'affects':decision.get('affects',[]),
                          'purpose':'confirm_current_intent'})
    owned={sid for f in project.get('model',{}).get('implementation',{}).get('features',[]) for sid in f.get('sources',[])}
    unresolved = [call for call in (index or {}).get('unresolved', []) if call['from'] in owned]
    locations = Counter((call['from'], call['line'], call['column']) for call in unresolved)
    repeated = Counter()
    for call in unresolved:
        ident=f"{call['from']}:{call['line']}:{call['column']}"
        if locations[(call['from'], call['line'], call['column'])] > 1:
            ident += ':' + hashlib.sha256(call['expression'].encode('utf-8')).hexdigest()[:16]
            repeated[ident] += 1
            if repeated[ident] > 1:
                ident += ':' + str(repeated[ident])
        coding.append({'id':ident,'audience':'coding','symbol':call['from'],'expression':call['expression'],
                       'question':'Verify the actual call target and project ownership. For dynamic calls, provide target and parameter evidence from a real scenario.',
                       'accepted_evidence':['source binding','external dependency with explicit boundary','runtime case and target']})
    return {'user':human,'coding':coding,'instruction':'Ask the user about business ambiguity; reconcile implementation bindings during coding. Do not recommend or expand business scope.'}


def reconciliation_errors(record,index,model):
    """Bindings must exist in current source. Assertions alone are not runtime proof."""
    try:
        from ..behavior_model import digest
    except ImportError:
        from behavior_model import digest
    errors=[]
    identity=digest({p:u['file_hash'] for p,u in index['units'].items()})
    if not isinstance(record,dict) or record.get('schema')!='bo-reconciliation/v1': return ['implementation reconciliation is missing']
    if record.get('source_id')!=identity:errors.append('implementation answers refer to an earlier source version')
    expected={q['id']:q for q in questions({'model':model},index)['coding']}
    items=record.get('answers',[])
    if not isinstance(items,list) or any(not isinstance(i,dict) for i in items):return ['invalid implementation answers']
    answers={a.get('id'):a for a in items}
    if len(answers)!=len(items):errors.append('duplicate implementation answer')
    for ident,q in expected.items():
        a=answers.get(ident,{})
        if not a.get('reason','').strip():errors.append({'unanswered_implementation':ident});continue
        if a.get('status')=='bound':
            if a.get('target') not in index['symbols']:errors.append({'missing_implementation_target':ident})
            cases={c['case'] for f in model.get('implementation',{}).get('features',[]) for c in f.get('cases',[])}
            if not a.get('case') or a['case'] not in cases:errors.append({'dynamic_binding_requires_runtime_case':ident})
        elif a.get('status')=='external':
            if not a.get('dependency','').strip():errors.append({'missing_external_boundary':ident})
        else:errors.append({'unresolved_implementation':ident})
    for ident in set(answers)-set(expected):errors.append({'stale_implementation_answer':ident})
    return errors
