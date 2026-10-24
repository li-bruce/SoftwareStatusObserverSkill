"""Run the release checks, including real effects and the observer-free package."""
import json
import argparse
from pathlib import Path
import subprocess
import sys
import tempfile
import uuid
import zipfile
from demo import EXAMPLE, ROOT, prepare
from setup_adapters import configure


def run(cwd, *args):
    subprocess.run([sys.executable, '-B', '-X', 'utf8', *map(str, args)], cwd=cwd, check=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database', action='store_true', help='Include optional database-adapter checks')
    args = parser.parse_args()
    configure()
    (ROOT/'.validation').mkdir(exist_ok=True)
    run(ROOT, 'tools/check_package.py')
    run(ROOT, 'tests/test_document_links.py')
    run(ROOT, 'tests/test_database_guidance.py')
    run(ROOT, 'tests/test_code_graph.py')
    subprocess.run(['node', 'tools/test_code_view.mjs'], cwd=ROOT, check=True)
    if args.database:
        run(ROOT, 'tools/verify_databases.py')
    run(ROOT, 'tests/test_ast_fingerprint.py')
    run(ROOT, 'tests/test_requirements_dialogue.py')
    run(ROOT, 'tests/test_clarification_gate.py')
    run(ROOT, 'tests/test_whitebox.py')
    run(ROOT, 'tests/test_focus_bundle.py')
    run(ROOT, 'tools/test_stategraph_module.py')
    run(ROOT, 'tools/test_recording.py')
    run(ROOT, 'tests/test_recording_retention.py')
    run(ROOT, 'tools/test_refactor.py')
    run(ROOT, 'tools/test_implementation_coverage.py')
    run(ROOT, 'tools/test_observer_noise.py')
    subprocess.run(['node', 'tools/test_source_pipe.mjs'], cwd=ROOT, check=True)
    run(ROOT, 'tools/test_multilanguage.py')
    run(ROOT, 'tools/verify_multilanguage.py')
    run(ROOT, 'tools/test_demo_launcher.py')
    run(ROOT, 'tools/test_assessment_fixes.py')
    run(ROOT, 'tools/test_web_continuity.py')
    run(ROOT, 'tests/test_interface_language.py')
    run(ROOT, 'tools/test_workflow_migration.py')
    run(ROOT, 'tools/test_archive_service_migration.py')
    run(ROOT, 'examples/python-modes/test_modes.py')
    subprocess.run(['node','tools/test_i18n.mjs'],cwd=ROOT,check=True)
    subprocess.run(['node','tools/test_conversation_focus.mjs'],cwd=ROOT,check=True)
    subprocess.run(['node','tools/test_refactor_view.mjs'],cwd=ROOT,check=True)
    subprocess.run(['node','tools/test_view_coverage.mjs'],cwd=ROOT,check=True)
    subprocess.run(['node','tools/test_view_continuity.mjs'],cwd=ROOT,check=True)
    subprocess.run(['node','tools/test_recorded_views.mjs'],cwd=ROOT,check=True)
    subprocess.run(['node','tools/test_web_colors.mjs'],cwd=ROOT,check=True)
    subprocess.run(['node', 'tools/test_product_demo.mjs'], cwd=ROOT, check=True)
    prepare()  # Refuse stale source/review before any re-verification.
    run(EXAMPLE, 'tooling/dev.py', 'verify')
    run(EXAMPLE, 'tooling/dev.py', 'accept')
    run(EXAMPLE, 'tooling/dev.py', 'check')
    package = 'dist/core-'+uuid.uuid4().hex[:8]+'.zip'
    run(EXAMPLE, 'tooling/dev.py', 'core', '--out', package)
    with tempfile.TemporaryDirectory(dir=ROOT/'.validation') as folder:
        with zipfile.ZipFile(EXAMPLE/package) as archive:
            assert not any(n.startswith(('observer_generated/', 'integrations/')) for n in archive.namelist())
            archive.extractall(folder)
        result = subprocess.run([sys.executable, '-B', '-X', 'utf8', 'main.py'], cwd=folder,
                                capture_output=True, text=True, encoding='utf-8', check=True)
        assert json.loads(result.stdout) == {'state': 'completed', 'effects': 1}, result.stdout
    run(ROOT, 'tests/test_installation.py')
    run(ROOT, 'tests/test_runtime_http.py')
    run(ROOT, 'tools/archive_demo.py', '--verify')
    archive_example = ROOT/'examples/team-archive'
    archive_package = 'dist/core-'+uuid.uuid4().hex[:8]+'.zip'
    run(archive_example, 'observer_runtime/architecture_guard.py', 'package',
        '--root', '.', '--out', archive_package)
    with tempfile.TemporaryDirectory(dir=ROOT/'.validation') as folder:
        with zipfile.ZipFile(archive_example/archive_package) as archive:
            assert not any(n.startswith(('observer_runtime/', 'integrations/')) for n in archive.namelist())
            archive.extractall(folder)
        # This recorded independent smoke test imports only the extracted business core.
        subprocess.run([sys.executable, '-I', '-B', '-X', 'utf8',
                        str(archive_example/'review/round-04/core_export_smoke.py'), folder],
                       cwd=folder, check=True)
    print('PASS: clarification, code/graph sync, business scenarios, graph history, HTTP runtime, installation, core package and independent archive example.')


if __name__ == '__main__':
    main()
