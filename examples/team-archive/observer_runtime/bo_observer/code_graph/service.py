"""Lazy source index shared by the CLI and the optional Web code view."""

import json
from pathlib import Path
import threading
from ..graph.behavior_model import contained, read, digest
from ..model_io import read_model
from ..sources import scan
from ..workflow.bo_sync import source_inventory
from .index import build
from .query import query


class CodeGraph:
    def __init__(self, root, *, persist=True):
        self.root = Path(root).resolve()
        self.lock = threading.RLock()
        self.previous = None
        self.graph = None
        self.fingerprint = None
        self.persist = persist
        self.cache = contained(self.root, ".stategraph/code-graph.json")

    def inputs(self):
        """Use the same independently declared source scope as iteration checks."""
        config = self.root / "sync.json"
        if config.is_file():
            cfg = read(config)
        else:
            excluded = {"tests/*": "Project tests", "test_*": "Project tests"}
            metadata = self.root / "bo_stategraph/runtime-version.json"
            if metadata.is_file():
                # Exclude only exact installed copies. A project-owned executor
                # or an edited support module remains visible to source analysis.
                try:
                    from ...bo_upgrade import portable_files
                except ImportError:
                    from bo_upgrade import portable_files
                for name, expected in portable_files(read(metadata).get("files", {})).items():
                    path = contained(self.root, name)
                    if path.is_file() and digest(path.read_bytes()) == expected:
                        excluded[name] = "Unchanged managed observer support"
            cfg = {
                "model": "bo_stategraph/project.json",
                "source_scope": {
                    "roots": ["."],
                    "exclude": excluded,
                },
            }
        model_path = contained(self.root, cfg.get("model", "bo_stategraph/project.json"))
        model = (
            read_model(model_path) if model_path.is_file() else {"nodes": [], "source_files": []}
        )
        return cfg, model

    def refresh(self):
        """Check file bytes on demand; parse only changed units and invalidate deletions."""
        with self.lock:
            cfg, model = self.inputs()
            inventory = source_inventory(self.root, cfg)
            # Source inventory reports hidden implementation separately from parser errors.
            fingerprint = digest(inventory)
            from ..sources import adapter_identity

            fingerprint = digest([fingerprint, adapter_identity()])
            if self.graph is None or fingerprint != self.fingerprint:
                index = scan(self.root, inventory["files"], self.previous)
                index["errors"] += [
                    {"path": p, "error": "Excluded application implementation"}
                    for p in inventory["excluded_implementations"]
                ]
                index["errors"] += [
                    {"path": p, "error": "Excluded entrypoint", "details": value}
                    for p, value in inventory["excluded_entrypoints"].items()
                ]
                self.previous, self.graph = index, build(index)
                self.graph["scope"] = {
                    "files": list(inventory["files"]),
                    "excluded": inventory["excluded"],
                }
                self.fingerprint = fingerprint
                if self.persist:
                    from ..workflow.sync_io import write

                    write(self.cache, self.graph)
            return self.graph, model

    def view(self, **options):
        with self.lock:
            graph, model = self.refresh()
            result = query(graph, model, **options)
            result["scope"] = graph["scope"]
            return result

    def check(self):
        """Verify a saved index independently; never repair evidence during a check."""
        enabled = self.cache.is_file()
        saved, errors = None, []
        if enabled:
            try:
                saved = read(self.cache)
                if not isinstance(saved, dict) or not saved:
                    raise ValueError("expected a nonempty code graph object")
            except (OSError, ValueError) as exc:
                errors.append("Invalid saved code structure: " + str(exc))
        fresh, _ = CodeGraph(self.root, persist=False).refresh()
        errors.extend(fresh["errors"])
        if isinstance(saved, dict):
            # Compare content as well as its claimed revision; reject tampering
            # that keeps the old fingerprint while removing a node or relation.
            for key in (
                "schema",
                "nodes",
                "edges",
                "bindings",
                "symbols",
                "files",
                "scope",
                "revision",
                "errors",
            ):
                if saved.get(key) != fresh.get(key):
                    errors.append("Saved code structure differs from current source: " + key)
        return {
            "enabled": enabled,
            "valid": not errors,
            "errors": errors,
            "status": "failed" if errors else "passed" if enabled else "not_enabled",
            "revision": fresh["revision"],
            "nodes": len(fresh["nodes"]),
            "edges": len(fresh["edges"]),
        }

    def source(self, path, revision):
        """Only return an indexed project file from the exact requested revision."""
        with self.lock:
            graph, _ = self.refresh()
            if revision != graph["revision"]:
                raise ValueError("Code changed; refresh the code view before opening source")
            if path not in graph["files"]:
                raise ValueError("Source is outside the indexed scope")
            raw = contained(self.root, path).read_bytes()
            if digest(raw) != graph["files"][path]:
                raise ValueError("Source changed while reading")
            return {"source": raw.decode("utf-8-sig"), "code_revision": revision}


def main():
    """Export the full source graph or retrieve a bounded neighborhood as JSON."""
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["scan", "query", "check"])
    parser.add_argument("--root", required=True)
    parser.add_argument("--focus")
    parser.add_argument("--depth", type=int, default=1)
    parser.add_argument("--limit", type=int, default=400)
    parser.add_argument("--out")
    args = parser.parse_args()
    service = CodeGraph(args.root, persist=args.command != "check")
    if args.command == "check":
        result = service.check()
        print(json.dumps(result, ensure_ascii=False))
        return int(not result["valid"])
    graph, _ = service.refresh()
    result = (
        service.view(focus=args.focus, depth=args.depth, limit=args.limit)
        if args.command == "query"
        else graph
    )
    if args.out:
        target = contained(service.root, args.out)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "valid": not result["errors"],
                "revision": result["revision"],
                "nodes": len(result["nodes"]),
                "edges": len(result["edges"]),
                "errors": result["errors"],
                "output": args.out,
            },
            ensure_ascii=False,
        )
    )
    return int(bool(result["errors"]))
