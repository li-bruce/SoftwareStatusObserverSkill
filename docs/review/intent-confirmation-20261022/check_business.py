"""Independent checks from the simulated user's answers, not the project's test expectations."""
from __future__ import annotations
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
import traceback


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', type=Path, default=Path(__file__).resolve().parents[4] / 'project-flow-trial-20261022')
    parser.add_argument('--label', required=True)
    parser.add_argument('--iteration', action='store_true')
    args = parser.parse_args()
    sys.path.insert(0, str(args.project))
    from app.store import Store
    from app.domain import Projects
    from app.ports import BOEvents
    from bo_stategraph.workflow import next_state, DEFINITION
    from bo_stategraph.bo_contracts import validate_runtime_definition
    loaded_files = sorted({Path(module.__file__).resolve() for module in tuple(sys.modules.values()) if getattr(module,'__file__',None) and Path(module.__file__).resolve().is_relative_to(args.project.resolve()) and str(module.__file__).endswith('.py')})
    def hashes():
        return {str(path.relative_to(args.project.resolve())):hashlib.sha256(path.read_bytes()).hexdigest() for path in loaded_files}
    source_hashes = hashes()
    out = Path(__file__).parent / 'execution' / args.label
    out.mkdir(parents=True, exist_ok=False)
    results = []
    def fresh(name, events=None):
        store = Store(out / (name + '.sqlite'))
        store.seed_demo()
        return store, Projects(store, events=events)
    def values(store):
        return store.snapshot()['port_values']
    def configured(name):
        store, app = fresh(name)
        link = app.configure_relation('alice','collect-a','records','process-b','records')
        assert link['ok'], link
        return store, app, link['link_id']
    def check(name, fn):
        try:
            evidence = fn()
            results.append({'name': name, 'passed': True, 'evidence': evidence})
        except Exception as error:
            results.append({'name': name, 'passed': False, 'error': repr(error), 'trace': traceback.format_exc()})
    def created():
        store, app = fresh('create')
        result = app.create_project('alice','Independent','report')
        assert result['ok'], result
        row = next(p for p in store.snapshot()['projects'] if p['id'] == result['project_id'])
        assert (row['owner'], row['type'], row['source_id']) == ('alice','report',None)
        return row
    check('create_owner_type_and_independent_origin', created)
    def derived():
        store, app, _ = configured('derive')
        result = app.derive_project('bob','collect-a','Derived')
        assert result['ok'], result
        snap = store.snapshot(); ident=result['project_id']
        row = next(p for p in snap['projects'] if p['id'] == ident)
        assert (row['owner'],row['type'],row['source_id']) == ('bob','collection','collect-a')
        assert not [r for r in snap['port_values'] if r['project_id'] == ident]
        assert not [r for r in snap['grants'] if r['project_id'] == ident]
        assert not [r for r in snap['links'] if ident in (r['source_id'],r['target_id'])]
        return {'project':row,'data':0,'grants':0,'links':0}
    check('derive_grantee_without_copying_data_grants_or_links', derived)
    def derive_denied():
        store, app = fresh('derive_denied')
        before = store.snapshot()['projects']
        result=app.derive_project('dave','collect-a','Forbidden')
        assert result['ok'] is False and result['code']=='derive_denied',result
        assert store.snapshot()['projects']==before
        return result
    check('derive_permission_is_distinct_from_connect', derive_denied)
    def configure_only():
        store, app = fresh('configure_only')
        before=values(store)
        result=app.configure_relation('alice','collect-a','records','process-b','records')
        assert result['ok'] and values(store)==before
        projects=store.snapshot()['projects']
        assert all(p['source_id'] is None for p in projects)
        return {'result':result,'target_unchanged':True,'both_independent':True}
    check('independent_projects_connect_without_transferring', configure_only)
    for actor in ('dave','carol'):
        def missing(actor=actor):
            store,app=fresh('one_end_'+actor)
            before=values(store)
            result=app.configure_relation(actor,'collect-a','records','process-b','records')
            assert result['ok'] is False and result['code']=='connect_denied',result
            assert not store.snapshot()['links'] and values(store)==before
            return result
        check('both_endpoint_permissions_required_'+actor,missing)
    def type_pair():
        store,app=fresh('wrong_pair')
        with store.connect() as db:
            db.execute('INSERT INTO grants VALUES(?,?,?)',('report-c','alice','connect'))
        result=app.configure_relation('alice','collect-a','records','report-c','result')
        assert result['ok'] is False and result['code']=='invalid_path',result
        assert not store.snapshot()['links']
        return result
    check('preset_type_pair_rejected',type_pair)
    for name, actor, src, port, dst, target in (
        ('missing_port','alice','collect-a','missing','process-b','records'),
        ('wrong_direction','bob','process-b','records','report-c','result')):
        def bad_path(name=name,actor=actor,src=src,port=port,dst=dst,target=target):
            store,app=fresh(name)
            result=app.configure_relation(actor,src,port,dst,target)
            assert result['ok'] is False and result['code']=='invalid_path',result
            assert not store.snapshot()['links']
            return result
        check(name,bad_path)
    for name, sql, code in (
        ('revoke_target',"DELETE FROM grants WHERE project_id='process-b' AND actor='alice' AND permission='connect'",'connect_denied'),
        ('change_format',"UPDATE ports SET format='other/v1' WHERE project_type='processing' AND name='records' AND direction='in'",'invalid_path'),
        ('remove_type_rule',"DELETE FROM type_edges WHERE source_type='collection' AND target_type='processing'",'invalid_path')):
        def recheck(name=name,sql=sql,code=code):
            store,app,link=configured(name)
            with store.connect() as db:db.execute(sql)
            before=values(store)
            result=app.execute_relation('alice',link)
            assert result['ok'] is False and result['code']==code,result
            assert values(store)==before
            operation=next(o for o in store.snapshot()['operations'] if o['id']==result['operation_id'])
            assert operation['state']=='rejected' and not operation['effect_id']
            return {'result':result,'stored_state':operation['state'],'target_unchanged':True}
        check('execute_rechecks_'+name,recheck)
    def current_value():
        store,app,link=configured('current_value')
        raw=json.dumps({'nested':{'items':[1,{'value':False},None]},'message':'sample'},sort_keys=True)
        with store.connect() as db:
            db.execute("UPDATE port_values SET value_json=?,revision=revision+1 WHERE project_id='collect-a' AND direction='out'",(raw,))
        result=app.execute_relation('alice',link)
        assert result['ok'],result
        target=next(v for v in values(store) if v['project_id']=='process-b' and v['direction']=='in')
        assert target['value_json']==raw
        with store.connect() as db:
            db.execute("UPDATE port_values SET value_json='null' WHERE project_id='collect-a' AND direction='out'")
        assert next(v for v in values(store) if v['project_id']=='process-b' and v['direction']=='in')['value_json']==raw
        return {'result':result,'copied_value':json.loads(raw),'source_later_change_did_not_rewrite_target':True}
    check('copies_current_json_without_continuous_transfer',current_value)
    for mode in ('off','failing_sink','failing_factory'):
        def fault(mode=mode):
            calls=[]
            def broken_sink(*args,**kwargs):
                calls.append('sink');raise RuntimeError('synthetic observer failure')
            def factory(entity):
                calls.append('factory')
                if mode=='failing_factory':raise RuntimeError('synthetic observer factory failure')
                return broken_sink
            events=BOEvents() if mode=='off' else BOEvents(factory)
            store,app=fresh('observer_'+mode,events)
            link=app.configure_relation('alice','collect-a','records','process-b','records')
            assert link['ok'],link
            result=app.execute_relation('alice',link['link_id'])
            assert result['ok'],result
            snap=values(store)
            source=next(v for v in snap if v['project_id']=='collect-a' and v['direction']=='out')
            target=next(v for v in snap if v['project_id']=='process-b' and v['direction']=='in')
            assert source['value_json']==target['value_json']
            assert mode=='off' or calls
            return {'business_ok':True,'injected_failure_calls':len(calls)}
        check('observer_'+mode+'_does_not_change_business',fault)
    def illegal_transition():
        try:next_state('completed','commit')
        except ValueError:return {'rejected':True}
        raise AssertionError('undeclared transition was accepted')
    check('illegal_transition_fails',illegal_transition)
    def malformed_definition():
        value=deepcopy(DEFINITION);value['initial']='not_a_state'
        try:validate_runtime_definition(value,loaded_engine='python.explicit',loaded_version='1',guard_names=[])
        except ValueError:return {'rejected':True}
        raise AssertionError('bad initial state was accepted')
    check('malformed_definition_fails',malformed_definition)
    if args.iteration:
        def different_type():
            store,app=fresh('derive_cross_type')
            result=app.derive_project('bob','collect-a','Changed',project_type='report')
            assert result['ok'],result
            row=next(p for p in store.snapshot()['projects'] if p['id']==result['project_id'])
            assert (row['type'],row['source_id'],row['owner'])==('report','collect-a','bob')
            return row
        check('iteration_derive_explicit_type',different_type)
    same_source = hashes() == source_hashes
    report={'scope':'Concrete synthetic project cases and direct SQLite results','source_hashes':source_hashes,'source_unchanged_during_check':same_source,'check_script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'checks':results,'passed':same_source and all(r['passed'] for r in results)}
    (out/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(json.dumps({'passed':report['passed'],'checks':len(results),'failed':[r['name'] for r in results if not r['passed']]}))
    raise SystemExit(0 if report['passed'] else 1)


if __name__=='__main__':main()
