"""Run data-adapter checks; --live additionally requires the four real test databases."""

import argparse
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--browser", action="store_true")
    parser.add_argument(
        "--native",
        action="store_true",
        help="Run the installed Node drivers against the real test databases",
    )
    args = parser.parse_args()
    for name in (
        "catalog",
        "runtime",
        "sync",
        "guidance",
        "acceptance",
        "watch",
        "identity",
        "protocol",
    ):
        subprocess.run(
            [sys.executable, "-B", "-X", "utf8", f"tests/test_database_{name}.py"],
            cwd=ROOT,
            check=True,
        )
    for name in ("view", "runtime"):
        subprocess.run(["node", f"tools/test_database_{name}.mjs"], cwd=ROOT, check=True)
    environment = {**os.environ}
    if args.live or args.native:
        # Only the explicitly started Compose test fixture uses these defaults.
        for key, value in {
            "POSTGRES": "postgresql+pg8000://bo_test:bo_test_local_only@127.0.0.1:19432/bo_test",
            "MONGODB": "mongodb://127.0.0.1:19017/bo_test",
            "REDIS": "redis://127.0.0.1:19379/15",
            "NEO4J": "bolt://neo4j:bo_test_local_only@127.0.0.1:19687",
        }.items():
            environment.setdefault(f"BO_TEST_{key}_URL", value)
    if args.live:
        for name in ("catalog", "runtime"):
            subprocess.run(
                [
                    sys.executable,
                    "-B",
                    "-X",
                    "utf8",
                    f"tools/test_database_{name}_live.py",
                    "--report" if name == "catalog" else "--out",
                    f".validation/database-{name}-live.json",
                ],
                cwd=ROOT,
                env=environment,
                check=True,
            )
    if args.native:
        subprocess.run(
            [
                "node",
                "tools/database-native/acceptance.mjs",
                "--out",
                ".validation/database-native-live.json",
            ],
            cwd=ROOT,
            env=environment,
            check=True,
        )
        subprocess.run(
            [
                sys.executable,
                "-B",
                "-X",
                "utf8",
                "tools/test_database_native_protocol.py",
                "--file",
                ".validation/database-native-live.json",
            ],
            cwd=ROOT,
            check=True,
        )
    subprocess.run(
        [
            sys.executable,
            "-B",
            "-X",
            "utf8",
            "tools/test_database_dialogue.py",
            "--out",
            ".validation/database-dialogue",
        ],
        cwd=ROOT,
        check=True,
    )
    if args.browser:
        subprocess.run(
            ["node", "tools/test_database_browser.mjs"],
            cwd=ROOT,
            env={**os.environ, "BO_PYTHON": sys.executable},
            check=True,
        )
    print("Database checks passed for the requested scope.")


if __name__ == "__main__":
    main()
