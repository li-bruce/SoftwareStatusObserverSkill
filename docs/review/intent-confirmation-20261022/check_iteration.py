"""Independent iteration checks against real project rows and event-bound frames."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import traceback


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', type=Path, default=Path(__file__).resolve().parents[4] / 'project-flow-trial-20261022')
    parser.add_argument('--label', required=True)
    args = parser.parse_args()
    sys.path.insert(0, str(args.project))
    from app.store import Store
    from app.domain import Projects
    from integrations.bo_adapter import BOAdapter
    from bo_stategraph import bo_validate_export
    out = Path(__file__).parent / 'execution' / args.label
    out.mkdir(parents=True, exist_ok=False)
    results = []
    def digest():
        return {p.relative_to(args.project).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                for folder in ['app', 'bo_stategraph', 'integrations'] for p in sorted((args.project / folder).rglob('*.py'))}
    before_hashes = digest()
    def check(name, fn):
        try:
            results.append({'name': name, 'passed': True, 'evidence': fn()})
        except Exception as exc:
            results.append({'name': name, 'passed': False, 'error': repr(exc), 'trace': traceback.format_exc()})
    def fresh(name, mode):
        store = Store(out / name / 'trial.sqlite3')
        store.seed_demo()
        adapter = BOAdapter(args.project, store, mode)
        app = Projects(store, build_id=adapter.manifest['build_id'], events=adapter.events)
        return store, app, adapter
    def assert_empty(snap, ident):
        assert not [v for v in snap['port_values'] if v['project_id'] == ident]
        assert not [g for g in snap['grants'] if g['project_id'] == ident]
        assert not [e for e in snap['links'] if ident in (e['source_id'], e['target_id'])]
    def inspect_operation(adapter, result, phase):
        adapter.pins.flush()
        export = adapter.bo_export()
        bo_validate_export(export)
        if adapter.mode != 'on':
            return {'mode': adapter.mode, 'export_valid': True}
        view = adapter.bo_view()
        events = [e for e in view['events'] if e['attempt'] == result['operation_id']]
        frames = {f['event_id']: f for f in view['runtime_frames']['frames']}
        assert events and all(e['id'] in frames for e in events)
        terminal = [e for e in events if e['node'] == 'operation_result']
        assert len(terminal) == 1 and terminal[0]['outputs']['state'] == phase
        for event in events:
            frame = frames[event['id']]
            assert all(frame[k] == event[k] for k in ('run_id', 'build_id', 'revision'))
            cfg = next(c for c in frame['machine']['configurations'] if c['attempt'] == result['operation_id'])
            if event['node'] == 'operation_checking':
                assert cfg['phase'] == 'checking'
            if event['node'] == 'operation_result':
                assert cfg['phase'] == phase
        return {'mode': adapter.mode, 'events': len(events), 'frames': len(events), 'operation_id': result['operation_id'],
                'derive_events': [{k:e[k] for k in ['id','node','inputs','outputs']} for e in events if e['node'] == 'derive_project']}
    for mode in ['on', 'off', 'fault']:
        for target_type in ['collection', 'processing', 'report']:
            def explicit(mode=mode, target_type=target_type):
                store, app, adapter = fresh(mode + '_explicit_' + target_type, mode)
                try:
                    linked = app.configure_relation('alice', 'collect-a', 'records', 'process-b', 'records')
                    assert linked['ok']
                    before = store.snapshot()
                    result = app.derive_project('bob', 'collect-a', 'Independent', target_type=target_type)
                    assert result['ok'], result
                    snap = store.snapshot()
                    row = next(p for p in snap['projects'] if p['id'] == result['project_id'])
                    assert (row['type'], row['source_id'], row['owner']) == (target_type, 'collect-a', 'bob')
                    assert_empty(snap, row['id'])
                    assert snap['port_values'] == before['port_values'] and snap['grants'] == before['grants'] and snap['links'] == before['links']
                    return {'project': row, 'new_project_has_no_data_links_grants': True, 'runtime': inspect_operation(adapter, result, 'completed')}
                finally:
                    adapter.close()
            check(mode + '_explicit_' + target_type, explicit)
        for source, actor, kind in [('collect-a','bob','collection'), ('process-b','bob','processing'), ('report-c','carol','report')]:
            def default(mode=mode, source=source, actor=actor, kind=kind):
                store, app, adapter = fresh(mode + '_default_' + kind, mode)
                try:
                    result = app.derive_project(actor, source, 'Default')
                    assert result['ok'], result
                    snap = store.snapshot()
                    row = next(p for p in snap['projects'] if p['id'] == result['project_id'])
                    assert row['type'] == kind and row['source_id'] == source and row['owner'] == actor
                    assert_empty(snap, row['id'])
                    return {'project': row, 'runtime': inspect_operation(adapter, result, 'completed')}
                finally:
                    adapter.close()
            check(mode + '_default_' + kind, default)
        for name, actor, requested in [('unauthorized','dave','report'), ('unknown_type','bob','unsupported_type')]:
            def denied(mode=mode, name=name, actor=actor, requested=requested):
                store, app, adapter = fresh(mode + '_' + name, mode)
                try:
                    before = store.snapshot()
                    result = app.derive_project(actor, 'collect-a', 'Rejected', target_type=requested)
                    assert result['ok'] is False, result
                    after = store.snapshot()
                    for key in ['projects','port_values','grants','links']:
                        assert after[key] == before[key], key
                    return {'result': result, 'business_rows_unchanged': True, 'runtime': inspect_operation(adapter, result, 'rejected')}
                finally:
                    adapter.close()
            check(mode + '_' + name, denied)
    def resulting_type_controls_ports():
        store, app, adapter = fresh('resulting_type_controls_ports', 'on')
        try:
            derived = app.derive_project('bob','collect-a','Report',target_type='report')
            assert derived['ok'], derived
            snap = store.snapshot(); assert_empty(snap, derived['project_id'])
            denied = app.configure_relation('bob','collect-a','records',derived['project_id'],'result')
            assert denied['ok'] is False and not store.snapshot()['links'], denied
            good = app.configure_relation('bob','process-b','result',derived['project_id'],'result')
            assert good['ok'], good
            assert not [v for v in store.snapshot()['port_values'] if v['project_id'] == derived['project_id']]
            transferred = app.execute_relation('bob', good['link_id'])
            assert transferred['ok'], transferred
            value = next(v for v in store.snapshot()['port_values'] if v['project_id'] == derived['project_id'])
            assert value['port'] == 'result' and value['direction'] == 'in' and json.loads(value['value_json']) == {'total':12}
            return {'derived_type': 'report', 'collection_to_report_rejected': True, 'processing_to_report_copied': json.loads(value['value_json']), 'runtime': inspect_operation(adapter, transferred, 'completed')}
        finally:
            adapter.close()
    check('resulting_type_controls_ports_without_inheritance', resulting_type_controls_ports)
    report = {'scope':'Authorized optional derivation type, inherited defaults, no copied rows, current permission/type/port rules, and real event frames',
              'source_hashes': before_hashes, 'source_unchanged_during_check': digest() == before_hashes,
              'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), 'checks':results}
    report['passed'] = report['source_unchanged_during_check'] and all(c['passed'] for c in results)
    (out / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf8')
    print(json.dumps({'passed':report['passed'], 'checks':len(results), 'failed':[c['name'] for c in results if not c['passed']]}))
    raise SystemExit(0 if report['passed'] else 1)


if __name__ == '__main__':
    main()
