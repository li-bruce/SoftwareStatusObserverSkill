"""Ensure installation is complete and cannot overwrite an existing Skill."""
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
PYTHON = [sys.executable, '-B', '-X', 'utf8']
sys.path.insert(0, str(ROOT/'tools'))
from install_skill import install


class InstallationTests(unittest.TestCase):
    def test_relative_project_from_target_directory(self):
        (ROOT/'.validation').mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=ROOT/'.validation') as folder:
            subprocess.run([*PYTHON, str(ROOT/'tools/install_skill.py'), '--project', '.'],
                           cwd=folder, check=True, capture_output=True)
            self.assertTrue((Path(folder)/'.agents/skills/vibelens/SKILL.md').is_file())

    def test_full_copy_and_refuse_overwrite(self):
        (ROOT/'.validation').mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=ROOT/'.validation') as folder:
            argv = [*PYTHON, str(ROOT/'tools/install_skill.py'), '--project', folder]
            subprocess.run(argv, check=True, capture_output=True)
            source = ROOT/'skills/vibelens'
            target = Path(folder)/'.agents/skills/vibelens'
            expected = {p.relative_to(source): p.read_bytes() for p in source.rglob('*')
                        if p.is_file() and '__pycache__' not in p.parts and 'node_modules' not in p.parts}
            actual = {p.relative_to(target): p.read_bytes() for p in target.rglob('*') if p.is_file()}
            self.assertEqual(expected, actual)
            (target/'SKILL.md').write_text('local edit', encoding='utf-8')
            self.assertNotEqual(subprocess.run(argv, capture_output=True).returncode, 0)
            self.assertEqual((target/'SKILL.md').read_text(), 'local edit')

    def test_legacy_requires_explicit_migration_and_retains_all_local_files(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'.validation') as folder:
            project = Path(folder)
            skills = project/'.agents/skills'
            legacy = skills/'business-observer'
            legacy.mkdir(parents=True)
            (legacy/'SKILL.md').write_text('user-edited legacy instructions', encoding='utf-8')
            (legacy/'custom.txt').write_text('keep this customization', encoding='utf-8')
            views = project/'bo_stategraph/config/views'
            views.mkdir(parents=True)
            (views/'local.json').write_text('{"positions":{"node":[42,16]}}', encoding='utf-8')
            protected = {p.relative_to(project): p.read_bytes() for p in project.rglob('*') if p.is_file()}
            command = [*PYTHON, str(ROOT/'tools/install_skill.py'), '--project', folder]
            rejected = subprocess.run(command, capture_output=True, text=True)
            self.assertNotEqual(rejected.returncode, 0)
            self.assertIn('--migrate-legacy', rejected.stderr)
            self.assertEqual(protected, {p.relative_to(project): p.read_bytes() for p in project.rglob('*') if p.is_file()})
            migrated = subprocess.run(command + ['--migrate-legacy'], capture_output=True, text=True)
            self.assertEqual(migrated.returncode, 0, migrated.stderr)
            self.assertFalse(legacy.exists())
            backups = list((project/'.agents/skill-backups').iterdir())
            self.assertEqual(len(backups), 1)
            self.assertEqual((backups[0]/'SKILL.md').read_bytes(), protected[Path('.agents/skills/business-observer/SKILL.md')])
            self.assertEqual((backups[0]/'custom.txt').read_bytes(), protected[Path('.agents/skills/business-observer/custom.txt')])
            self.assertEqual((views/'local.json').read_bytes(), protected[Path('bo_stategraph/config/views/local.json')])
            self.assertIn('name: vibelens', (skills/'vibelens/SKILL.md').read_text(encoding='utf-8'))

    def test_failed_copy_keeps_legacy_installation_usable(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'.validation') as folder:
            skills = Path(folder)/'skills'
            legacy = skills/'business-observer'
            legacy.mkdir(parents=True)
            (legacy/'SKILL.md').write_text('original', encoding='utf-8')
            with mock.patch('install_skill.shutil.copytree', side_effect=OSError('simulated copy failure')):
                with self.assertRaisesRegex(OSError, 'simulated copy failure'):
                    install(skills, migrate_legacy=True)
            self.assertEqual((legacy/'SKILL.md').read_text(), 'original')
            self.assertFalse((skills/'vibelens').exists())

    def test_custom_agent_directory_and_reject_missing_legacy(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'.validation') as folder:
            skills = Path(folder)/'custom-agent/skills'
            command = [*PYTHON, str(ROOT/'tools/install_skill.py'), '--skills-dir', str(skills)]
            result = subprocess.run(command + ['--migrate-legacy'], capture_output=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse(skills.exists())
            subprocess.run(command, capture_output=True, check=True)
            self.assertTrue((skills/'vibelens/scripts/bo.py').is_file())
            self.assertFalse((skills/'business-observer').exists())

    def test_failed_final_move_restores_the_previous_installation(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'.validation') as folder:
            skills = Path(folder)/'skills'
            legacy = skills/'business-observer'
            legacy.mkdir(parents=True)
            (legacy/'SKILL.md').write_text('original', encoding='utf-8')
            rename = Path.rename

            def fail_new_install(path, destination):
                if path.name == 'vibelens':
                    raise OSError('simulated final move failure')
                return rename(path, destination)

            with mock.patch.object(Path, 'rename', fail_new_install):
                with self.assertRaisesRegex(OSError, 'simulated final move failure'):
                    install(skills, migrate_legacy=True)
            self.assertEqual((legacy/'SKILL.md').read_text(), 'original')
            self.assertFalse((skills/'vibelens').exists())


if __name__ == '__main__':
    unittest.main()
