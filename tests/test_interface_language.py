"""Conversation language changes the interface, never graph or personal-view content."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / 'skills/vibelens/scripts'
sys.path.insert(0, str(SCRIPTS))
from bo_observer.web.interface_language import read_language, set_language
from bo_observer.web.bo_design import BODesign


class InterfaceLanguageTests(unittest.TestCase):
    def setUp(self):
        (ROOT/'.validation').mkdir(exist_ok=True)

    def test_default_and_cli_work_before_a_graph_exists(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'.validation') as folder:
            self.assertEqual(read_language(folder)['conversation_locale'], 'en')
            self.assertFalse((Path(folder)/'bo_stategraph').exists())
            result = subprocess.run([sys.executable, '-B', '-X', 'utf8', str(SCRIPTS/'bo_design.py'),
                'language', '--root', folder, '--locale', 'zh-CN', '--source', 'Chinese conversation'],
                capture_output=True, text=True, encoding='utf-8')
            self.assertEqual(result.returncode, 0, result.stderr+result.stdout)
            self.assertEqual(BODesign(folder).snapshot(), {'available': False, 'locale': 'zh-CN'})
            settings = Path(folder)/'bo_stategraph/config/views/local.json'
            settings.parent.mkdir(parents=True)
            settings.write_text('{"personal":"Keep my notes"}', encoding='utf-8')
            before = settings.read_bytes()
            set_language(folder, 'en', 'English conversation')
            self.assertEqual(settings.read_bytes(), before)

    def test_invalid_inputs_and_malformed_settings_fail_without_repair(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'.validation') as folder:
            for locale, source in [('fr', 'conversation'), ([], 'conversation'), ('en', ''), ('en', None)]:
                with self.assertRaises(ValueError):
                    set_language(folder, locale, source)
            path = Path(folder)/'bo_stategraph/config/interface.json'
            path.parent.mkdir(parents=True)
            for value in [[], {'schema': True, 'conversation_locale':'en','source':''},
                          {'schema':1,'conversation_locale':[],'source':''},
                          {'schema':1,'conversation_locale':'en','source':'','unknown':True}]:
                path.write_text(json.dumps(value), encoding='utf-8')
                before = path.read_bytes()
                with self.assertRaises(ValueError):
                    read_language(folder)
                with self.assertRaises(ValueError):
                    set_language(folder, 'en', 'conversation')
                self.assertEqual(path.read_bytes(), before)


if __name__ == '__main__':
    unittest.main()
