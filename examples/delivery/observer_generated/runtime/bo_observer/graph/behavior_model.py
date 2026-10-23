"""v3 declared behavior graph, Python source binding and event-reference checks.

This does not prove business semantics or extract complete data flow.
"""

from __future__ import annotations
import argparse
import ast
import hashlib
import json
from pathlib import Path
import sys

try:
    from ...bo_contracts import validate_graph
except ImportError:
    from bo_contracts import validate_graph


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def digest(value):
    raw = (
        value
        if isinstance(value, bytes)
        else json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    )
    return hashlib.sha256(raw).hexdigest()


def ast_fingerprint(node):
    """Hash syntax consistently across Python 3.11-3.13 AST schemas.

    New, empty generic-parameter fields do not change existing Python code.
    Nonempty parameters and defaults remain part of the fingerprint.
    """

    def normalize(value):
        if isinstance(value, ast.AST):
            fields = {}
            for name, child in ast.iter_fields(value):
                if name == "type_params" and child == []:
                    continue
                if name == "default_value" and child is None:
                    continue
                fields[name] = normalize(child)
            return {"node": type(value).__name__, "fields": fields}
        if isinstance(value, list):
            return [normalize(child) for child in value]
        # repr preserves the types of constants, including bytes and complex values.
        return {"value": repr(value)}

    return digest(normalize(node))


def contained(root, name):
    root = Path(root).absolute().resolve()
    rel = Path(name)
    if rel.is_absolute() or ".." in rel.parts:
        raise ValueError("expected contained relative path")
    target = (root / rel).resolve()
    if not target.is_relative_to(root):
        raise ValueError("path escapes project")
    return target


def validate(root, model):
    nodes = validate_graph(model)
    if model.get("schema_version") != 3:
        raise ValueError("expected model v3")
    intent = read(contained(root, model["intent"]))
    requirements = {r["id"] for r in intent["requirements"]}
    for requirement in intent["requirements"]:
        if requirement.get("status") not in {
            "confirmed",
            "assumption",
            "pending",
        } or not requirement.get("source"):
            raise ValueError("missing requirement provenance")
    for node in nodes.values():
        if node.get("source"):
            contained(root, node["source"]["path"])
            if node["source"]["path"] not in model["source_files"]:
                raise ValueError("source binding outside explicit scope")
        if set(node.get("requirements", [])) - requirements:
            raise ValueError("unknown requirement")
    for name in model["source_files"]:
        if not contained(root, name).is_file():
            raise ValueError(f"missing tracked source: {name}")
    return intent


def symbols(path):
    """Locate declarations using the same lexical scope rules as source inventory."""
    source = path.read_text(encoding="utf-8-sig")
    tree = ast.parse(source)
    result = {}

    def walk(body, prefix=""):
        for n in body:
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                name = prefix + n.name
                if name in result:
                    raise ValueError(f"ambiguous symbol {name}")
                line = min([n.lineno] + [d.lineno for d in n.decorator_list])
                result[name] = {
                    "line": line,
                    "end_line": n.end_lineno,
                    "signature": ast.unparse(n.args) if hasattr(n, "args") else name,
                    "ast_sha256": ast_fingerprint(n),
                    "snippet": "\n".join(source.splitlines()[line - 1 : n.end_lineno]),
                    "calls": sorted(
                        {ast.unparse(c.func) for c in ast.walk(n) if isinstance(c, ast.Call)}
                    ),
                    "guards": [
                        {"line": c.lineno, "expression": ast.unparse(c.test)}
                        for c in ast.walk(n)
                        if isinstance(c, (ast.If, ast.IfExp))
                    ],
                }
                walk(n.body, name + ".")
            else:
                # Control-flow blocks do not introduce a Python name scope.
                # Keep conditional/try/match declarations bindable, including
                # nested callbacks, while retaining ambiguity rejection.
                walk(ast.iter_child_nodes(n), prefix)

    walk(tree.body)
    return result


def capture(root, model):
    intent = validate(root, model)
    files, inventories, bindings = {}, {}, {}
    for name in sorted(set(model["source_files"])):
        path = contained(root, name)
        raw = path.read_bytes()
        if len(raw) > 2_000_000:
            raise ValueError(f"source too large: {name}")
        files[name] = digest(raw)
        if path.suffix == ".py":
            inventories[name] = symbols(path)
    bound_paths = {n["source"]["path"] for n in model["nodes"] if n.get("source")}
    foreign = [
        n
        for n in files
        if n in bound_paths
        and Path(n).suffix in {".js", ".mjs", ".cjs", ".jsx", ".ts", ".tsx", ".mts", ".cts", ".vue"}
    ]
    if foreign:
        try:
            from ..sources import scan
        except ImportError:
            from bo_observer.sources import scan
        index = scan(root, foreign)
        if index["errors"]:
            raise ValueError("source adapter errors: " + json.dumps(index["errors"]))
        for name in foreign:
            inventories[name] = {}
            lines = contained(root, name).read_text(encoding="utf-8-sig").splitlines()
            for symbol, item in index["units"][name]["symbols"].items():
                inventories[name][symbol] = {
                    "line": item["line"],
                    "end_line": item["end_line"],
                    "signature": item["signature"],
                    "ast_sha256": item["ast_hash"],
                    "snippet": "\n".join(lines[item["line"] - 1 : item["end_line"]]),
                    "calls": [c["expression"] for c in item["calls"]],
                    "guards": item["predicates"],
                }
    for n in model["nodes"]:
        src = n.get("source")
        if src:
            info = inventories.get(src["path"], {}).get(src["symbol"])
            if not info:
                raise ValueError(f"unresolved symbol: {src}")
            bindings[n["id"]] = {**src, **info, "file_sha256": files[src["path"]]}
    return {
        "schema_version": 3,
        "build_id": digest({"files": files, "model": model, "intent": intent}),
        "files": files,
        "model_hash": digest(model),
        "intent_hash": digest(intent),
        "model_revision": model["revision"],
        "bindings": bindings,
        "python": sys.version.split()[0],
        "unknowns": model["scope"]["unknowns"]
        + [
            "AST evidence does not prove value flow, guard dominance or behavioral equivalence",
            "External dependencies, interpreter, dynamic patching and omitted files are not attested",
        ],
    }


def check(root, model, baseline):
    changed = []
    for name in set(baseline["files"]) | set(model["source_files"]):
        path = contained(root, name)
        if not path.is_file() or digest(path.read_bytes()) != baseline["files"].get(name):
            changed.append(name)
    model_changed = digest(model) != baseline["model_hash"]
    try:
        intent_changed = digest(read(contained(root, model["intent"]))) != baseline["intent_hash"]
    except (OSError, ValueError):
        intent_changed = True
    affected = {n["id"] for n in model["nodes"] if n.get("source", {}).get("path") in changed}
    if model_changed or intent_changed:
        affected |= {n["id"] for n in model["nodes"]}
    direct = sorted(affected)
    while True:
        following = {e["to"] for e in model["edges"] if e["from"] in affected}
        if following <= affected:
            break
        affected |= following
    return {
        "status": "stale" if changed or model_changed or intent_changed else "current",
        "changed_files": sorted(changed),
        "model_changed": model_changed,
        "intent_changed": intent_changed,
        "directly_affected": direct,
        "possibly_affected": sorted(affected),
    }


def validate_events(events, model, build_id=None):
    nodes = {n["id"]: n for n in model["nodes"]}
    seen, errors, gaps = {}, [], []
    for e in events:
        if e.get("scope", "attempt") not in {"attempt", "entity", "application"}:
            errors.append("invalid event scope")
        if e.get("node") not in nodes or e.get("phase") not in {
            "enter",
            "return",
            "read",
            "decision",
            "wait",
            "commit",
            "change",
            "error",
        }:
            errors.append(f"invalid event node/phase: {e.get('id')}")
        if e.get("id") in seen:
            errors.append("duplicate event id")
        if build_id and e.get("build_id") != build_id:
            errors.append("build mismatch")
        for ref in e.get("depends", []):
            prior = seen.get(ref["event"])
            if not prior:
                gaps.append({"event": e["id"], "missing": ref["event"]})
                continue
            if ref["type"] not in {"data", "control", "trigger", "recheck"}:
                errors.append("invalid dependency type")
            if (
                prior["build_id"] != e["build_id"]
                or prior["run_id"] != e["run_id"]
                or prior["seq"] >= e["seq"]
            ):
                errors.append("invalid causal reference context")
            if prior["attempt"] != e["attempt"] and ref["type"] != "trigger":
                errors.append("cross-attempt reference without explicit trigger")
            if prior["entity"] != e["entity"]:
                errors.append("cross-entity reference unsupported")
            if (
                ref["type"] == "data"
                and prior["basis"]["param_version"] != e["basis"]["param_version"]
            ):
                errors.append("cross-parameter-version data reference")
        seen[e["id"]] = e
    return {
        "valid": not errors,
        "events": len(events),
        "errors": errors,
        "gaps": gaps,
        "meaning": "reference integrity only; leaf truth and dependency semantics require independent checks",
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("command", choices=["validate", "capture", "check", "events"])
    p.add_argument("--root", required=True)
    p.add_argument("--model", default="behavior.json")
    p.add_argument("--out")
    p.add_argument("--baseline")
    p.add_argument("--events")
    a = p.parse_args()
    model = read(contained(a.root, a.model))
    if a.command == "validate":
        validate(a.root, model)
        result = {"valid": True}
    elif a.command == "capture":
        result = capture(a.root, model)
    elif a.command == "check":
        result = check(a.root, model, read(contained(a.root, a.baseline)))
    else:
        events = [
            json.loads(l)
            for l in contained(a.root, a.events).read_text(encoding="utf-8").splitlines()
            if l.strip()
        ]
        result = validate_events(events, model)
    if a.out:
        path = contained(a.root, a.out)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8", newline="\n"
        )
        print(
            json.dumps({"written": a.out, "build_id": result.get("build_id")}, ensure_ascii=False)
        )
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    return 1 if result.get("status") == "stale" or result.get("valid") is False else 0


if __name__ == "__main__":
    raise SystemExit(main())
