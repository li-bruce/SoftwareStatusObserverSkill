"""Small example binding; real projects use change_sync's reviewed acceptance gate."""
import hashlib
import json


def bo_check_sources(root):
    manifest = json.loads((root / "bo_stategraph/sources.json").read_text(encoding="utf-8"))
    changed = [name for name, expected in manifest["files"].items()
               if not (root / name).is_file() or hashlib.sha256((root / name).read_bytes()).hexdigest() != expected]
    return {"status": "stale" if changed else "current", "changed": changed, "build_id": manifest["build_id"]}
