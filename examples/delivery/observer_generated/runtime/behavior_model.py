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


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def digest(value):
    raw = value if isinstance(value, bytes) else json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(raw).hexdigest()


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
    if model.get("schema_version") != 3:
        raise ValueError("expected model v3")
    for key in ("revision", "intent", "source_files", "nodes", "edges", "overview", "scope"):
        if not model.get(key):
            raise ValueError(f"missing {key}")
    nodes = {n["id"]: n for n in model["nodes"]}
    if len(nodes) != len(model["nodes"]):
        raise ValueError("duplicate nodes")
    intent = read(contained(root, model["intent"]))
    requirements = {r["id"] for r in intent["requirements"]}
    for r in intent["requirements"]:
        if r.get("status") not in {"confirmed", "assumption", "pending"} or not r.get("source"):
            raise ValueError("missing requirement provenance")
    for n in nodes.values():
        if n["kind"] not in {"action", "function", "decision", "wait", "effect", "data", "state"}:
            raise ValueError("invalid node kind")
        if not n.get("label") or not n.get("summary"):
            raise ValueError("node lacks developer explanation")
        if n["kind"] not in {"data", "state"} and not n.get("source"):
            raise ValueError(f"executable node lacks source: {n['id']}")
        if n.get("source"):
            contained(root, n["source"]["path"])
            if n["source"]["path"] not in model["source_files"]:
                raise ValueError("source binding outside explicit scope")
        if set(n.get("requirements", [])) - requirements:
            raise ValueError("unknown requirement")
        seen = {n["id"]}
        parent = n.get("parent")
        while parent:
            if parent not in nodes or parent in seen:
                raise ValueError("missing parent or hierarchy cycle")
            seen.add(parent)
            parent = nodes[parent].get("parent")
    edge_ids = set()
    for e in model["edges"]:
        if e["id"] in edge_ids or e["from"] not in nodes or e["to"] not in nodes:
            raise ValueError("duplicate/dangling edge")
        edge_ids.add(e["id"])
        if e["type"] not in {"flow", "data", "guard", "contains", "resource", "join"} or not e.get("evidence"):
            raise ValueError("edge needs type and provenance")
        if e['type'] in {'resource','join'} and not model.get('machine',{}).get('execution'):
            raise ValueError('resource and join edges need an executable activity declaration')
    for item in model["overview"]:
        if item["node"] not in nodes:
            raise ValueError("unknown overview node")
    for name in model["source_files"]:
        if not contained(root, name).is_file():
            raise ValueError(f"missing tracked source: {name}")
    return intent


def symbols(path):
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
                result[name] = {"line": line, "end_line": n.end_lineno,
                    "signature": ast.unparse(n.args) if hasattr(n, "args") else name,
                    "ast_sha256": digest(ast.dump(n, include_attributes=False).encode()),
                    "snippet": "\n".join(source.splitlines()[line-1:n.end_lineno]),
                    "calls": sorted({ast.unparse(c.func) for c in ast.walk(n) if isinstance(c, ast.Call)}),
                    "guards": [{"line": c.lineno, "expression": ast.unparse(c.test)} for c in ast.walk(n) if isinstance(c, (ast.If, ast.IfExp))]}
                walk(n.body, name + ".")
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
    for n in model["nodes"]:
        src = n.get("source")
        if src:
            info = inventories.get(src["path"], {}).get(src["symbol"])
            if not info:
                raise ValueError(f"unresolved symbol: {src}")
            bindings[n["id"]] = {**src, **info, "file_sha256": files[src["path"]]}
    return {"schema_version": 3, "build_id": digest({"files": files, "model": model, "intent": intent}),
        "files": files, "model_hash": digest(model), "intent_hash": digest(intent),
        "model_revision": model["revision"], "bindings": bindings,
        "python": sys.version.split()[0], "unknowns": model["scope"]["unknowns"] + [
            "AST evidence does not prove value flow, guard dominance or behavioral equivalence",
            "External dependencies, interpreter, dynamic patching and omitted files are not attested"]}


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
    return {"status": "stale" if changed or model_changed or intent_changed else "current",
        "changed_files": sorted(changed), "model_changed": model_changed, "intent_changed": intent_changed,
        "directly_affected": direct, "possibly_affected": sorted(affected)}


def validate_events(events, model, build_id=None):
    nodes = {n["id"]: n for n in model["nodes"]}
    seen, errors, gaps = {}, [], []
    for e in events:
        if e.get("node") not in nodes or e.get("phase") not in {"enter", "return", "read", "decision", "wait", "commit", "change", "error"}:
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
            if prior["build_id"] != e["build_id"] or prior["run_id"] != e["run_id"] or prior["seq"] >= e["seq"]:
                errors.append("invalid causal reference context")
            if prior["attempt"] != e["attempt"] and ref["type"] != "trigger":
                errors.append("cross-attempt reference without explicit trigger")
            if prior["entity"] != e["entity"]:
                errors.append("cross-entity reference unsupported")
            if ref["type"] == "data" and prior["basis"]["param_version"] != e["basis"]["param_version"]:
                errors.append("cross-parameter-version data reference")
        seen[e["id"]] = e
    return {"valid": not errors, "events": len(events), "errors": errors, "gaps": gaps,
            "meaning": "reference integrity only; leaf truth and dependency semantics require independent checks"}


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
        events = [json.loads(l) for l in contained(a.root, a.events).read_text(encoding="utf-8").splitlines() if l.strip()]
        result = validate_events(events, model)
    if a.out:
        path = contained(a.root, a.out)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8", newline="\n")
        print(json.dumps({"written": a.out, "build_id": result.get("build_id")}, ensure_ascii=False))
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    return 1 if result.get("status") == "stale" or result.get("valid") is False else 0


if __name__ == "__main__":
    raise SystemExit(main())
