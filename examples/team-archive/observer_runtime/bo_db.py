"""Export, synchronize, and check database structure in the existing project graph."""

import argparse
import json
from pathlib import Path
import time


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["guide", "sync", "check", "watch"])
    parser.add_argument("--root", required=True)
    parser.add_argument("--model", default="bo_stategraph/project.json")
    parser.add_argument("--interval", type=float, default=2)
    args = parser.parse_args()
    from bo_observer.data.sync import synchronize
    from bo_observer.data.contract import write_if_changed

    root = Path(args.root).resolve()
    if args.command == "guide":
        from bo_observer.data.guidance import storage_questions
        from bo_observer.data.contract import CONFIG_PATH
        from bo_observer.graph.behavior_model import read, contained

        path = contained(root, CONFIG_PATH)
        print(
            json.dumps(
                storage_questions(read(path) if path.exists() else None, required=True),
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0
    last = None
    try:
        while True:
            report = synchronize(root, model_path=args.model, update=args.command != "check")
            serialized = json.dumps(report, sort_keys=True)
            if serialized != last:
                write_if_changed(root / ".stategraph/database-maintenance.json", report)
                print(json.dumps(report, ensure_ascii=False), flush=True)
                last = serialized
            if args.command != "watch":
                return 0 if report["valid"] else 1
            time.sleep(max(0.2, args.interval))
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
