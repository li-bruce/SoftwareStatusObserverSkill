"""Ensure installation is complete and cannot overwrite an existing Skill."""
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class InstallationTests(unittest.TestCase):
    def test_relative_project_from_target_directory(self):
        (ROOT/'.validation').mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=ROOT/'.validation') as folder:
            subprocess.run([sys.executable, str(ROOT/'tools/install_skill.py'), '--project', '.'],
                           cwd=folder, check=True, capture_output=True)
            self.assertTrue((Path(folder)/'.agents/skills/business-observer/SKILL.md').is_file())

    def test_full_copy_and_refuse_overwrite(self):
        (ROOT/'.validation').mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=ROOT/'.validation') as folder:
            argv = [sys.executable, str(ROOT/'tools/install_skill.py'), '--project', folder]
            subprocess.run(argv, check=True, capture_output=True)
            source = ROOT/'skills/business-observer'
            target = Path(folder)/'.agents/skills/business-observer'
            expected = {p.relative_to(source): p.read_bytes() for p in source.rglob('*')
                        if p.is_file() and '__pycache__' not in p.parts}
            actual = {p.relative_to(target): p.read_bytes() for p in target.rglob('*') if p.is_file()}
            self.assertEqual(expected, actual)
            (target/'SKILL.md').write_text('local edit', encoding='utf-8')
            self.assertNotEqual(subprocess.run(argv, capture_output=True).returncode, 0)
            self.assertEqual((target/'SKILL.md').read_text(), 'local edit')


if __name__ == '__main__':
    unittest.main()
