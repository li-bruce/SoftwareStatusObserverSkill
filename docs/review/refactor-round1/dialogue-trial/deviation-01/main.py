"""Run from project root: python main.py demo | show | command '{...}'."""
import argparse
import json
from pathlib import Path
from integrations.bo_app import BOApplication

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("action", choices=["demo", "show", "command"])
    p.add_argument("payload", nargs="?")
    p.add_argument("--db", default="data/studio.sqlite")
    args = p.parse_args()
    app = BOApplication(Path(args.db))
    result = app.bo_demo() if args.action == "demo" else app.graph.bo_export() if args.action == "show" else app.bo_command(json.loads(args.payload))
    print(json.dumps(result, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
