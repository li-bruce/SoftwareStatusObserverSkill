"""Run the release checks, including real effects and the observer-free package."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import uuid
import zipfile
from demo import EXAMPLE, ROOT, prepare


def run(cwd, *args):
    subprocess.run([sys.executable, '-B', '-X', 'utf8', *map(str, args)], cwd=cwd, check=True)


def main():
    (ROOT/'.validation').mkdir(exist_ok=True)
    run(ROOT, 'tools/check_package.py')
    run(ROOT, 'tests/test_ast_fingerprint.py')
    run(ROOT, 'tests/test_requirements_dialogue.py')
    run(ROOT, 'tests/test_clarification_gate.py')
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
    print('PASS: clarification, code/graph sync, business scenarios, graph history, HTTP runtime, installation and core package.')


if __name__ == '__main__':
    main()
