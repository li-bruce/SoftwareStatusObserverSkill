"""Format maintained source; leave vendored bundles and frozen evidence untouched.

Install tools/formatting/requirements.txt and run npm ci in tools/formatting
before using this command. Pass --check in a development check or CI job.
"""

import argparse
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills/business-observer"
VENDOR_FILES = {"pixi.min.js", "elk.bundled.js", "elk-worker.min.js"}


def source_files():
    """Select authored sources once; installed copies are updated by sync_runtime.py."""
    python = sorted((SKILL / "scripts").rglob("*.py"))
    javascript = sorted(
        p for p in (SKILL / "assets/stategraph-viewer").glob("*.js") if p.name not in VENDOR_FILES
    )
    javascript += sorted((SKILL / "scripts/bo_observer/adapters/javascript").glob("*.mjs"))
    website = sorted(
        p for p in (ROOT / "docs/site").iterdir() if p.suffix in {".html", ".css", ".js", ".mjs"}
    )
    return python, javascript + website


def main():
    """Run both pinned formatters and propagate a failed check to the caller."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    python, web = source_files()
    subprocess.run(
        [
            sys.executable,
            "-m",
            "black",
            "--line-length",
            "100",
            "--target-version",
            "py311",
            *(["--check"] if args.check else []),
            *map(str, python),
        ],
        cwd=ROOT,
        check=True,
    )
    subprocess.run(
        [
            "node",
            str(ROOT / "tools/formatting/node_modules/prettier/bin/prettier.cjs"),
            "--config",
            str(ROOT / "tools/formatting/prettier.json"),
            "--check" if args.check else "--write",
            *map(str, web),
        ],
        cwd=ROOT,
        check=True,
    )


if __name__ == "__main__":
    main()
