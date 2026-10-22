"""Start the frozen source package from a fresh directory and use its real HTTP API."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import threading
import urllib.request
import zipfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive-label', default='02-initial-repaired')
    parser.add_argument('--label', default='package-smoke')
    parser.add_argument('--iteration', action='store_true')
    args = parser.parse_args()
    here = Path(__file__).resolve().parent
    archive = here / 'snapshots' / (args.archive_label + '.zip')
    work = here.parents[2] / '.validation/intent-confirmation-20261022' / args.label
    work.mkdir(parents=True, exist_ok=False)
    with zipfile.ZipFile(archive) as zipped:
        for name in zipped.namelist():
            if not (work / name).resolve().is_relative_to(work.resolve()):
                raise ValueError('Unexpected archive path')
        zipped.extractall(work)
    root = work / 'project'
    sys.path.insert(0, str(root))
    from app.store import Store
    from app.domain import Projects
    from bo_stategraph import bo_validate_export
    from integrations.bo_adapter import BOAdapter
    from integrations.bo_server import bo_http_server
    store = Store(work / 'demo.sqlite3')
    store.seed_demo()
    adapter = BOAdapter(root, store, recordings=True)
    service = Projects(store, build_id=adapter.manifest['build_id'], events=adapter.events)
    server = bo_http_server(root, service, adapter, 0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    checks = []
    report = {'archive_sha256': hashlib.sha256(archive.read_bytes()).hexdigest(), 'extracted_source': str(root), 'checks': checks}
    try:
        base = f'http://127.0.0.1:{server.server_port}'
        for endpoint in ['/', '/graph', '/pixi.min.js', '/elk.bundled.js']:
            with opener.open(base + endpoint, timeout=5) as response:
                assert response.status == 200 and response.read(32)
            checks.append({'name': 'reachable:' + endpoint, 'passed': True})
        payload = json.dumps({'actor': 'alice', 'name': 'Extracted package check', 'type': 'report'}).encode()
        with opener.open(urllib.request.Request(base + '/api/create', data=payload, headers={'Content-Type': 'application/json'}), timeout=5) as response:
            result = json.load(response)
        assert result['ok'], result
        with opener.open(base + '/api/projects', timeout=5) as response:
            saved = json.load(response)
        row = next(p for p in saved['projects'] if p['id'] == result['project_id'])
        assert row['owner'] == 'alice' and row['type'] == 'report'
        checks.append({'name': 'create_through_real_http_and_read_stored_result', 'passed': True})
        if args.iteration:
            data = json.dumps({'actor':'bob','source_id':'collect-a','name':'Package cross-type check','target_type':'processing'}).encode()
            request = urllib.request.Request(base + '/api/derive', data=data, headers={'Content-Type':'application/json'})
            with opener.open(request, timeout=5) as response:
                derived = json.load(response)
            assert derived['ok'], derived
            with opener.open(base + '/api/projects', timeout=5) as response:
                current = json.load(response)
            row = next(p for p in current['projects'] if p['id'] == derived['project_id'])
            assert row['type'] == 'processing' and row['source_id'] == 'collect-a' and row['owner'] == 'bob'
            assert not [v for v in current['port_values'] if v['project_id'] == row['id']]
            checks.append({'name':'cross_type_derivation_in_extracted_package','passed':True})
        with opener.open(base + '/api/stategraph/export', timeout=5) as response:
            exported = json.load(response)
        bo_validate_export(exported)
        checks.append({'name': 'package_public_export_validates', 'passed': True})
        report['passed'] = True
    except Exception as error:
        report.update(passed=False, error=repr(error))
    finally:
        server.shutdown()
        thread.join(5)
        server.server_close()
        adapter.close()
    (here / 'execution' / (args.label + '.json')).write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf8')
    print(json.dumps({'passed': report['passed'], 'checks': len(checks), 'error': report.get('error')}))
    raise SystemExit(0 if report['passed'] else 1)


if __name__ == '__main__':
    main()
