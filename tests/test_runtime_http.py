"""Verify the shipped HTTP example against live states and committed SQLite rows."""
import json
from contextlib import closing
from pathlib import Path
import queue
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]


class RuntimeTests(unittest.TestCase):
    def test_live_wait_completion_and_authoritative_effect(self):
        (ROOT/'.validation').mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=ROOT/'.validation') as folder:
            example = Path(folder)/'delivery'
            shutil.copytree(ROOT/'examples/delivery', example,
                ignore=shutil.ignore_patterns('scratch', 'history', 'dist', '.stategraph', '__pycache__'))
            with (Path(folder)/'server.log').open('w', encoding='utf-8') as log:
                process = subprocess.Popen([sys.executable, '-B', '-X', 'utf8', 'integrations/bo_server.py', '0'],
                    cwd=example, stdout=subprocess.PIPE, stderr=log, text=True, encoding='utf-8')
                startup = queue.Queue()
                threading.Thread(target=lambda: startup.put(process.stdout.readline()), daemon=True).start()
                try:
                    info = json.loads(startup.get(timeout=20))
                    base = info['url']
                    def view():
                        with urlopen(base+'/api/view', timeout=5) as response:
                            return json.load(response)
                    def command(action, **values):
                        request = Request(base+'/api/command', data=json.dumps({'action': action, **values}).encode(),
                                          headers={'Content-Type': 'application/json'})
                        with urlopen(request, timeout=5) as response:
                            self.assertTrue(json.load(response)['ok'])
                    def finish():
                        frames = []
                        deadline = time.monotonic()+12
                        while time.monotonic() < deadline:
                            frame = view(); frames.append(frame)
                            if not frame['busy']:
                                return frame, frames
                            time.sleep(.08)
                        self.fail('The real operation did not finish.')
                    with urlopen(base, timeout=5) as page:
                        self.assertIn('canvas-host', page.read().decode())
                    command('execute')
                    result, _ = finish()
                    self.assertEqual(result['authority']['state'], 'waiting')
                    self.assertEqual(result['authority']['effects'], [])
                    command('edit', content='public release sample', capacity=1)
                    command('grant', id='G1', expires=200)
                    command('grant', id='G2', expires=220)
                    command('revoke', id='G1')
                    command('execute')
                    result, frames = finish()
                    self.assertEqual(result['authority']['state'], 'completed')
                    self.assertEqual(result['binding_status']['status'], 'current')
                    self.assertEqual(result['manifest']['build_id'], info['build_id'])
                    self.assertTrue(any(set(r['activities'].values()) == {'running', 'waiting'}
                        for frame in frames for r in frame['machine']['configurations']))
                    self.assertTrue(any(event['node']=='commit' and event['phase']=='commit' for event in result['events']))
                    command('commit')
                    with closing(sqlite3.connect(example/'scratch/live.sqlite')) as db:
                        rows = db.execute('SELECT version, checksum FROM artifact').fetchall()
                    self.assertEqual(len(rows), 1)
                    self.assertEqual(rows[0][0], result['authority']['basis']['param_version'])
                    self.assertEqual(rows[0][1], result['authority']['effects'][0]['checksum'])
                finally:
                    process.terminate()
                    try:
                        process.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        process.kill(); process.wait(timeout=5)
                    process.stdout.close()


if __name__ == '__main__':
    unittest.main()
