"""The native demo must remain usable when its observer cannot start or stops."""
from contextlib import ExitStack
from io import StringIO
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import multilanguage_demo as launcher


class Process:
    def __init__(self, results):
        self.results = iter(results)
        self.returncode = None
        self.terminated = False

    def poll(self):
        self.returncode = next(self.results, self.returncode)
        return self.returncode

    def terminate(self):
        self.terminated = True
        self.returncode = -15

    def wait(self, timeout=None):
        return self.returncode


class LauncherTests(unittest.TestCase):
    def run_case(self, graph, response):
        temporary_root = launcher.ROOT/'.validation'
        temporary_root.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=temporary_root) as folder, ExitStack() as stack:
            root = Path(folder)
            (root/'bo_stategraph').mkdir()
            (root/'bo_stategraph/project.json').write_text('{"project_id":"trial"}', encoding='utf-8')
            (root/'node_modules/vite/bin').mkdir(parents=True)
            (root/'node_modules/vite/bin/vite.js').touch()
            app = Process([None, None, 0])
            output = StringIO()
            stack.enter_context(patch.object(launcher, 'EXAMPLE', root))
            stack.enter_context(patch.object(launcher, 'configure'))
            stack.enter_context(patch.object(launcher.sys, 'argv', ['demo', '--mode', 'observe']))
            stack.enter_context(patch.object(launcher.sys, 'stdout', output))
            stack.enter_context(patch.object(launcher.time, 'sleep'))
            launch = stack.enter_context(patch.object(launcher.subprocess, 'Popen', side_effect=[graph, app]))
            stack.enter_context(patch.object(launcher, 'urlopen', return_value=response))
            launcher.main()
            self.assertEqual(launch.call_count, 2, 'business server must start')
            self.assertFalse(app.terminated, 'observer failure must not kill the business server')
            settings = root/'.stategraph/collector.json'
            return output.getvalue(), json.loads(settings.read_text()) if settings.exists() else None

    def test_first_launch_without_observer_disables_stale_capture(self):
        output, settings = self.run_case(Process([1]), None)
        self.assertIn('Application: http://', output)
        self.assertNotIn('\nGraph: http://', output)
        self.assertEqual(settings['enabled'], False)
        self.assertIsNone(settings['endpoint'])
        self.assertIsNone(settings['token'])

    def test_observer_exit_after_readiness_keeps_application_running(self):
        output, settings = self.run_case(Process([None, 1]), StringIO('{"project_id":"trial"}'))
        self.assertIn('Graph: http://', output)
        self.assertIn('Business execution continues', output)
        self.assertIsNone(settings)


if __name__ == '__main__':
    unittest.main()
