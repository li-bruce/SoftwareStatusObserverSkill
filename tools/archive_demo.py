"""Restore the reviewed archive example, verify it or run its local UI."""
import argparse
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples/team-archive"


def run(*args):
    subprocess.run(
        [sys.executable, "-B", "-X", "utf8", *map(str, args)],
        cwd=EXAMPLE, check=True,
    )


def prepare():
    state = EXAMPLE / ".stategraph"
    if not (state / "active.json").exists():
        if state.exists() and any(state.iterdir()):
            raise SystemExit("An incomplete local change exists. Inspect .stategraph first.")
        shutil.copytree(EXAMPLE / ".release/stategraph", state, dirs_exist_ok=True)
        manifest = EXAMPLE / "manifest.json"
        if not manifest.exists():
            shutil.copyfile(EXAMPLE / ".release/manifest.json", manifest)
    # Check existing approval before running tests. Never silently approve edited inputs.
    run("observer_runtime/change_sync.py", "check", "--root", ".")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8824)
    parser.add_argument("--prepare-only", action="store_true")
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("port must be between 1 and 65535")
    prepare()
    if args.verify:
        run("observer_runtime/change_sync.py", "verify", "--root", ".")
        run("observer_runtime/change_sync.py", "accept", "--root", ".")
        run("validate.py")
    elif not args.prepare_only:
        try:
            run("run.py", "--port", args.port)
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
