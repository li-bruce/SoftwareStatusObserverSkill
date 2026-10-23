"""Check every native live observation and model export against the common protocol."""

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "skills/business-observer/scripts"))

from bo_observer.data.contract import validate_catalog
from bo_observer.protocol import schema_check


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", type=Path, default=ROOT / ".validation/database-native-live.json")
    args = parser.parse_args()
    report = json.loads(args.file.read_text(encoding="utf-8"))
    expected = {"postgresql", "mongodb", "redis", "neo4j"}
    databases = report.get("databases", {})
    if report.get("status") != "passed" or set(databases) != expected:
        raise ValueError("all four native database runs must have passed")
    count = catalogs = 0
    for name, result in databases.items():
        if result.get("status") != "passed" or not result.get("events"):
            raise ValueError("native database observation is missing: " + name)
        seen = {}
        for event in result["events"]:
            schema_check(event, "event")
            if event["id"] in seen:
                raise ValueError("duplicate native event identity")
            for dependency in event["depends"]:
                if dependency["event"] not in seen:
                    raise ValueError("native dependency does not refer to an earlier event")
            if event["node"] in {"read", "write"}:
                if event["outputs"].get("target_source") != "provided":
                    raise ValueError("native target provenance is missing or inaccurate")
            seen[event["id"]] = event
            count += 1
        if "catalog" in result:
            catalog = validate_catalog(result["catalog"])
            if catalog.get("validation_scope") != "application":
                raise ValueError("Mongoose declarations must not claim database enforcement")
            catalogs += 1
    if not catalogs:
        raise ValueError("native ODM model export is missing")
    print(
        json.dumps(
            {"status": "passed", "events": count, "catalogs": catalogs, "databases": len(databases)}
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
