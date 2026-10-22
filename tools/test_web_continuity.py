"""Read-only design, stable identities, Web isolation and unchanged dialogue gates."""
from copy import deepcopy
import json
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / 'skills/business-observer'
sys.path.insert(0, str(SKILL / 'scripts'))
from bo_design import BODesign
from bo_web import BOWeb, ASSETS
from requirements_dialogue import assess
from view_preferences import Preferences


class DesignTests(unittest.TestCase):
    def setUp(self):
        temp = ROOT / '.validation/web-tests'; temp.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=temp)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.doc = json.loads((SKILL / 'assets/discovery.example.json').read_text(encoding='utf-8'))
        self.doc.update(project_id='web-trial', layout_id='web-trial')
        self.save()
        self.design = BODesign(self.root)

    def save(self):
        (self.root / 'discovery.json').write_text(json.dumps(self.doc, ensure_ascii=False), encoding='utf-8')

    def test_draft_has_no_runtime_fact_or_fake_state_machine(self):
        view = self.design.view()
        self.assertEqual(view['stage'], 'design')
        self.assertEqual(view['events'], [])
        self.assertIsNone(view['machine']['current'])
        self.assertEqual(view['model']['machine']['values'], [])
        self.assertFalse(assess(self.doc)['ready'])

    def test_cli_relative_root_uses_actual_working_directory(self):
        run = subprocess.run([sys.executable, '-B', '-X', 'utf8', str(SKILL/'scripts/bo_design.py'),
                              'show', '--root', '.'], cwd=self.root, capture_output=True, text=True, encoding='utf-8')
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
        self.assertTrue(json.loads(run.stdout)['available'])

    def test_focus_resolves_decision_edges_to_reserved_model_nodes(self):
        self.doc['networks'][0]['nodes'][-1]['model_nodes'] = ['publish']
        self.save(); before = (self.root / 'discovery.json').read_bytes()
        result = self.design.focus([], '核对下载条件', 'D1')
        self.assertEqual(result['nodes'], ['preview', 'publish'])
        self.assertFalse(result['stale'])
        self.assertIn('publish', [n['id'] for n in self.design.view()['model']['nodes']])
        self.assertEqual(before, (self.root / 'discovery.json').read_bytes())
        self.assertFalse(assess(self.doc)['ready'])  # Viewing/focusing is not confirmation.

    def test_conversation_change_updates_graph_and_invalidates_old_focus(self):
        self.design.focus(['preview'])
        self.doc['networks'][0]['edges'][-1]['label'] = '预览不影响下载'
        self.doc['sources'].append({'id':'U2', 'kind':'user', 'text':'先下载，预览后台继续', 'locator':'合成对话第 2 轮'})
        self.doc['decisions'][0].update(status='resolved', resolution={'kind':'user_answer','text':'先下载，预览后台继续','source_refs':['U2']})
        self.save()
        self.assertTrue(self.design.snapshot()['stale'])
        self.assertEqual(self.design.view()['model']['edges'][-1]['label'], '预览不影响下载')
        self.assertTrue(assess(self.doc)['ready'])
        self.assertFalse(assess(self.doc, model={'nodes':[{'id':'upload'}]}, intent={'requirements':[]}, acceptance={'checks':[]})['valid'])
        self.assertFalse(self.design.focus(['download'])['stale'])

    def test_missing_node_bad_identity_and_containment_cycle_fail(self):
        with self.assertRaises(ValueError): self.design.focus(['made-up'])
        self.doc['networks'][0]['nodes'][0]['model_nodes'] = 'bad'
        self.save()
        with self.assertRaises(ValueError): self.design.view()
        self.doc['networks'][0]['nodes'][0].pop('model_nodes')
        self.doc['networks'][0]['nodes'][0]['parent'] = 'preview'
        self.doc['networks'][0]['nodes'][2]['parent'] = 'upload'
        self.save()
        with self.assertRaises(ValueError): self.design.view()

    def test_web_modes_preserve_core_and_personal_files(self):
        core = self.root / 'bo_stategraph/definition.json';core.parent.mkdir();core.write_text('{"real":"engine"}')
        personal = self.root / 'bo_stategraph/config/views/local.json';personal.parent.mkdir(parents=True);personal.write_text('{"keep":1}')
        before = {p: p.read_bytes() for p in (core, personal, self.root / 'discovery.json')}
        web = BOWeb(self.root, assets=ASSETS)
        self.assertTrue(web.status()['entry_visible'])
        web.set_mode('hidden')
        self.assertFalse(web.status()['entry_visible']);self.assertTrue(web.allowed('/graph'))
        self.assertIn(b'data-bo-entry hidden', web.entry_html(b'<a data-bo-entry href="/graph">graph</a>'))
        web.set_mode('disabled')
        for path in ('/graph','/api/view','/api/source','/api/design','/api/preferences','/api/recordings/start','/api/stategraph/export','/viewer.js','/conversation.js','/pixi.min.js'):
            self.assertFalse(web.allowed(path), path)
        self.assertTrue(web.allowed('/api/state'));self.assertTrue(web.allowed('/control'))
        self.assertEqual(before, {p: p.read_bytes() for p in before})
        web.set_mode('visible');self.assertTrue(web.allowed('/graph'))

    def test_invalid_mode_fails_and_does_not_replace_policy(self):
        web = BOWeb(self.root)
        with self.assertRaises(ValueError): web.set_mode('silently-enable')
        web.config.parent.mkdir(parents=True, exist_ok=True);web.config.write_text('{"schema":1,"mode":"invalid"}')
        with self.assertRaises(ValueError): web.status()
        with self.assertRaises(ValueError): web.set_mode('visible')

    def test_explicit_preference_identity_migration_keeps_revision_and_entries(self):
        old = Preferences(self.root, 'old-id')
        saved = old.save({'schema':1,'project_id':'old-id','revision':0,
            'entries':{'business-observer.layout.v2:stable-layout':'{"annotations":{"node":{"core":true}}}'}})
        new = Preferences(self.root, 'stable-layout', legacy_project_ids=['old-id'])
        migrated = new.read()
        self.assertEqual(migrated['entries'], saved['entries'])
        self.assertEqual(migrated['revision'], saved['revision'])
        self.assertEqual(migrated['project_id'], 'stable-layout')
        new.save(migrated)
        self.assertEqual(Preferences(self.root, 'stable-layout').read()['entries'], saved['entries'])
        with self.assertRaises(ValueError): Preferences(self.root, 'unrelated').read()

    def test_real_http_graph_read_only_and_dynamic_closure(self):
        with socket.socket() as sock: sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
        proc = subprocess.Popen([sys.executable,'-B','-X','utf8',str(SKILL/'scripts/bo_web.py'),'serve','--root','.','--port',str(port)],cwd=self.root,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        self.addCleanup(lambda: (proc.terminate(), proc.communicate(timeout=8)))
        base = f'http://127.0.0.1:{port}'
        for _ in range(100):
            try:
                with urlopen(base+'/api/view',timeout=.2) as r: value=json.load(r)
                break
            except OSError: time.sleep(.05)
        else: self.fail('design server not reachable')
        self.assertEqual(value['stage'], 'design')
        with urlopen(base+'/api/preferences') as r: preference=json.load(r)
        preference['entries']={'business-observer.layout.v2:web-trial':'{"focus":"upload"}'}
        with urlopen(Request(base+'/api/preferences',data=json.dumps(preference).encode(),headers={'Content-Type':'application/json'})) as r:
            self.assertEqual(r.status,200)
        saved=json.loads((self.root/'bo_stategraph/config/views/local.json').read_text(encoding='utf-8'))
        self.assertEqual(saved['entries'],preference['entries'])
        before = (self.root/'discovery.json').read_bytes()
        for route in ('/api/design/answer','/api/command'):
            with self.assertRaises(HTTPError) as exc: urlopen(Request(base+route,data=b'{}',headers={'Content-Type':'application/json'}))
            self.assertEqual(exc.exception.code,405)
        self.assertEqual(before,(self.root/'discovery.json').read_bytes())
        with self.assertRaises(HTTPError) as exc: urlopen(Request(base+'/api/view',headers={'Origin':'http://unrelated.example'}))
        self.assertEqual(exc.exception.code,403)
        web=BOWeb(self.root);web.set_mode('disabled')
        for route in ('/graph','/api/view','/api/design','/viewer.js'):
            with self.assertRaises(HTTPError) as exc: urlopen(base+route)
            self.assertEqual(exc.exception.code,404)
        web.set_mode('visible')
        with urlopen(base+'/graph') as r: self.assertEqual(r.status,200)


if __name__ == '__main__': unittest.main(verbosity=2)
