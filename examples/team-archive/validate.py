"""Normal project delivery gate. Never regenerates or accepts a baseline."""
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).absolute().parent


def main():
    python = [sys.executable, "-X", "utf8", "-B"]
    node = os.environ.get("ARCHIVE_NODE") or shutil.which("node")
    commands = [
        python + ["observer_runtime/change_sync.py", "check", "--root", "."],
        python + ["observer_runtime/architecture_guard.py", "check", "--root", "."],
        python + ["tooling/tests.py"],
    ]
    if not node:
        print("Node is required for graph history checks; set ARCHIVE_NODE.", file=sys.stderr)
        return 1
    commands.append([node, "tooling/graph_tests.mjs"])
    for command in commands:
        completed = subprocess.run(command, cwd=ROOT)
        if completed.returncode:
            return completed.returncode
    print("Project validation passed, including accepted source/model synchronization.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
