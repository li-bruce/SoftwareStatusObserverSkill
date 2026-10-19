"""Read-only Python evidence extraction; no execution, no semantic equivalence claim."""
from __future__ import annotations
import argparse
import ast
import hashlib
import json
from pathlib import Path
import re
import sys

ASSETS = Path(__file__).resolve().parent.parent / "assets"


def digest(value):
    data = value if isinstance(value, bytes) else json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()
    return hashlib.sha256(data).hexdigest()


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def safe_path(root, relative):
    root = Path(root).absolute().resolve()
    path = Path(relative)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError(f"path must be relative and contained: {relative}")
    result = (root / path).resolve()
    if not result.is_relative_to(root):
        raise ValueError(f"path escapes project: {relative}")
    return result


def schema_check(value, schema, at="$"):
    supported = {"$schema", "title", "description", "type", "enum", "required", "properties", "additionalProperties", "items", "minItems", "minLength", "minimum", "pattern"}
    if set(schema) - supported:
        raise ValueError(f"unsupported schema keys: {set(schema) - supported}")
    kinds = {"object": lambda x: isinstance(x, dict), "array": lambda x: isinstance(x, list),
             "string": lambda x: isinstance(x, str), "integer": lambda x: type(x) is int,
             "number": lambda x: type(x) in (int, float), "boolean": lambda x: type(x) is bool,
             "null": lambda x: x is None}
    wanted = schema.get("type")
    wanted = wanted if isinstance(wanted, list) else [wanted] if wanted else []
    if wanted and not any(kinds[t](value) for t in wanted):
        raise ValueError(f"{at}: expected {wanted}")
    if "enum" in schema and value not in schema["enum"]:
        raise ValueError(f"{at}: invalid enum {value!r}")
    if isinstance(value, dict):
        missing = set(schema.get("required", [])) - value.keys()
        props = schema.get("properties", {})
        if missing:
            raise ValueError(f"{at}: missing {sorted(missing)}")
        if schema.get("additionalProperties") is False and value.keys() - props.keys():
            raise ValueError(f"{at}: unexpected keys {sorted(value.keys() - props.keys())}")
        for key in value.keys() & props.keys():
            schema_check(value[key], props[key], f"{at}.{key}")
    if isinstance(value, list):
        if len(value) < schema.get("minItems", 0):
            raise ValueError(f"{at}: too few items")
        for i, item in enumerate(value):
            if "items" in schema:
                schema_check(item, schema["items"], f"{at}[{i}]")
    if isinstance(value, str):
        if len(value) < schema.get("minLength", 0) or ("pattern" in schema and not re.search(schema["pattern"], value)):
            raise ValueError(f"{at}: invalid string")
    if type(value) in (int, float) and "minimum" in schema and value < schema["minimum"]:
        raise ValueError(f"{at}: below minimum")


def validate_model(root, model):
    schema_check(model, read_json(ASSETS / "model.schema.json"))
    for group in ("nodes", "edges", "bindings"):
        ids = [n["id"] for n in model[group]]
        if len(ids) != len(set(ids)):
            raise ValueError(f"duplicate {group} id")
    nodes = {n["id"]: n for n in model["nodes"]}
    allowed = {
        "acts_on": ({"action"}, {"object"}),
        "supports": ({"fact", "condition"}, {"condition"}),
        "requires": ({"condition"}, {"action"}),
        "produces": ({"action"}, {"effect"}),
        "transitions_to": ({"action", "state", "wait", "effect"}, {"action", "state", "wait", "effect"}),
        "describes": ({"fact"}, {"object"}),
    }
    for e in model["edges"]:
        if e["source"] not in nodes or e["target"] not in nodes:
            raise ValueError(f"dangling edge {e['id']}")
        a, b = allowed[e["type"]]
        if nodes[e["source"]]["kind"] not in a or nodes[e["target"]]["kind"] not in b:
            raise ValueError(f"edge type mismatch {e['id']}")
    parents = {}
    dependencies = {}
    for n in nodes.values():
        if "parent" in n:
            if n["parent"] not in nodes:
                raise ValueError(f"unknown parent {n['id']}")
            parents[n["id"]] = [n["parent"]]
        if n["kind"] == "condition":
            if "operator" not in n or "dependencies" not in n or not n["dependencies"]:
                raise ValueError(f"condition needs operator/dependencies: {n['id']}")
            incoming = {e["source"] for e in model["edges"] if e["type"] == "supports" and e["target"] == n["id"]}
            if incoming != set(n["dependencies"]) or len(n["dependencies"]) != len(set(n["dependencies"])):
                raise ValueError(f"condition dependencies differ from supports: {n['id']}")
            dependencies[n["id"]] = n["dependencies"]
    def acyclic(graph):
        done, visiting = set(), set()
        def visit(n):
            if n in visiting:
                raise ValueError(f"cycle at {n}")
            if n in done:
                return
            visiting.add(n)
            for nxt in graph.get(n, []):
                visit(nxt)
            visiting.remove(n)
            done.add(n)
        for n in graph:
            visit(n)
    acyclic(parents)
    acyclic(dependencies)
    intent_path = safe_path(root, model["intent"])
    intent = read_json(intent_path)
    if not intent.get("requirements") or not intent.get("revision"):
        raise ValueError("intent needs requirements and revision")
    for req in intent["requirements"]:
        if not all(req.get(k) for k in ("id", "text", "source")) or req.get("status") not in {"confirmed", "assumption", "pending"}:
            raise ValueError("invalid intent requirement provenance")
    for b in model["bindings"]:
        if b["node"] not in nodes:
            raise ValueError(f"unknown binding node {b['node']}")
        safe_path(root, b["path"])
    return intent


def inventory(path):
    raw = path.read_bytes()
    if len(raw) > 2_000_000:
        raise ValueError(f"source too large: {path.name}")
    source = raw.decode("utf-8-sig")
    tree = ast.parse(source, filename=path.name)
    symbols = {}
    def walk(body, prefix=""):
        for node in body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                name = prefix + node.name
                if name in symbols:
                    raise ValueError(f"ambiguous repeated symbol {path.name}:{name}")
                line = min([node.lineno] + [d.lineno for d in node.decorator_list])
                symbols[name] = {
                    "line": line, "end_line": node.end_lineno,
                    "ast_sha256": digest(ast.dump(node, include_attributes=False).encode()),
                    "calls": sorted({ast.unparse(c.func) for c in ast.walk(node) if isinstance(c, ast.Call)}),
                    "guards": [{"line": c.lineno, "expression": ast.unparse(c.test)} for c in ast.walk(node) if isinstance(c, ast.If)],
                    "async": isinstance(node, ast.AsyncFunctionDef),
                    "snippet": "\n".join(source.splitlines()[line - 1:node.end_lineno]),
                }
                walk(node.body, name + ".")
    walk(tree.body)
    return {"sha256": digest(raw), "symbols": symbols}


def capture(root, model):
    root = Path(root).absolute().resolve()
    intent = validate_model(root, model)
    files = {}
    for name in model["source_roots"]:
        p = safe_path(root, name)
        if not p.exists():
            raise ValueError(f"missing source root {name}")
        for f in ([p] if p.is_file() else sorted(p.rglob("*.py"))):
            if f.suffix != ".py":
                raise ValueError(f"unsupported source {f.name}")
            safe = safe_path(root, f.relative_to(root))
            files[safe.relative_to(root).as_posix()] = inventory(safe)
    bindings = []
    mapped = set()
    for b in model["bindings"]:
        path = Path(b["path"]).as_posix()
        if path not in files or b["symbol"] not in files[path]["symbols"]:
            raise ValueError(f"unresolved source binding {b['id']}: {path}:{b['symbol']}")
        mapped.add((path, b["symbol"]))
        bindings.append({**b, **files[path]["symbols"][b["symbol"]], "file_sha256": files[path]["sha256"], "status": "symbol_resolved"})
    hashes = {p: v["sha256"] for p, v in files.items()}
    unknowns = list(model["scope"]["unknowns"]) + ["AST positions/calls/guards are syntax evidence; dominance and business conformance are unproved", "Unlisted imports, interpreter, monkey patches and external services are not attested"]
    unmapped = [f"{p}:{s}" for p, v in files.items() for s in v["symbols"] if (p, s) not in mapped]
    return {"schema_version": 1, "build_id": digest({"files": hashes, "model": model, "intent": intent}),
            "model_sha256": digest(model), "intent_sha256": digest(intent), "model_revision": model["revision"],
            "python_version": sys.version.split()[0], "files": hashes, "bindings": bindings,
            "unmapped_symbols": unmapped, "unknowns": unknowns, "nodes": model["nodes"], "edges": model["edges"]}


def compare(current, baseline):
    changed_files = sorted(p for p in current["files"].keys() | baseline["files"].keys() if current["files"].get(p) != baseline["files"].get(p))
    affected = {b["node"] for b in current["bindings"] + baseline["bindings"] if b["path"] in changed_files}
    before = {n["id"]: n for n in baseline.get("nodes", [])}
    after = {n["id"]: n for n in current["nodes"]}
    affected |= {n for n in before.keys() | after.keys() if before.get(n) != after.get(n)}
    if current["intent_sha256"] != baseline["intent_sha256"] or current["model_sha256"] != baseline["model_sha256"]:
        affected |= set(after)  # conservative for changed edges/bindings/intent
    direct = sorted(affected)
    edges = current["edges"] + baseline.get("edges", [])
    while True:
        more = {e["target"] for e in edges if e["source"] in affected and e["type"] in {"supports", "requires", "produces", "transitions_to"}}
        if more <= affected:
            break
        affected |= more
    return {"status": "current" if current["build_id"] == baseline["build_id"] else "stale",
            "previous_build": baseline["build_id"], "current_build": current["build_id"],
            "changed_files": changed_files, "directly_invalidated_nodes": direct,
            "possibly_affected_nodes": sorted(affected), "retained_mapping_nodes": sorted(set(after) - affected),
            "meaning": "Content correspondence only; retained mapping is not retained semantic proof"}


def validate_events(events, model, build_id=None):
    schema = read_json(ASSETS / "event.schema.json")
    nodes = {n["id"]: n for n in model["nodes"]}
    event_ids, groups, coverage = set(), {}, set()
    required_payload = {"fact": {"value", "source", "version", "quality"},
                        "decision": {"status", "reason", "evidence", "basis_version"},
                        "transition": {"from_state", "to_state", "outcome", "basis_version"},
                        "effect": {"effect_id", "outcome", "basis_version"}}
    kinds = {"fact": {"fact"}, "decision": {"condition"}, "transition": {"action", "state", "wait"}, "effect": {"effect"}}
    for e in events:
        schema_check(e, schema)
        if e["event_id"] in event_ids:
            raise ValueError("duplicate event_id")
        event_ids.add(e["event_id"])
        if e["node_id"] not in nodes or nodes[e["node_id"]]["kind"] not in kinds[e["kind"]]:
            raise ValueError("event/node kind mismatch")
        if build_id and e["build_id"] != build_id:
            raise ValueError("event belongs to a different build")
        if e["model_revision"] != model["revision"]:
            raise ValueError("event model revision mismatch")
        if not required_payload[e["kind"]] <= e["payload"].keys():
            raise ValueError("event payload misses semantic fields")
        if e["kind"] == "decision" and set(e["payload"]["evidence"]) != set(nodes[e["node_id"]]["dependencies"]):
            raise ValueError("decision evidence differs from declared dependencies")
        coverage.add(e["node_id"])
        group = (e["run_id"], e["entity_id"], e["attempt_id"], e["tx_id"])
        groups.setdefault(group, {})[e["node_id"]] = e
    unknowns = []
    for group, samples in groups.items():
        for node_id, e in samples.items():
            n = nodes[node_id]
            if e["kind"] != "decision" or n.get("operator") not in {"all", "any"}:
                continue
            deps = [samples.get(d) for d in n["dependencies"]]
            if any(d is None or d["kind"] != "decision" for d in deps):
                unknowns.append(f"missing decision dependencies: {group[-1]}:{node_id}")
                continue
            if any(d["payload"]["basis_version"] != e["payload"]["basis_version"] for d in deps):
                raise ValueError("mixed decision snapshot versions")
            statuses = [d["payload"]["status"] for d in deps]
            if "stale" in statuses:
                expected = "stale"
            elif n["operator"] == "all":
                expected = "false" if "false" in statuses else "unknown" if "unknown" in statuses else "true"
            else:
                expected = "true" if "true" in statuses else "unknown" if "unknown" in statuses else "false"
            if e["payload"]["status"] != expected:
                raise ValueError(f"inconsistent {n['operator']} decision: {node_id}")
    return {"event_count": len(events), "observed_nodes": sorted(coverage),
            "unobserved_nodes": sorted(nodes.keys() - coverage), "unknowns": unknowns,
            "claim": "Structural and declared AND/OR consistency only; not proof of fact truth or business conformance"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["validate", "capture", "check", "events"])
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--out")
    parser.add_argument("--baseline")
    parser.add_argument("--events")
    args = parser.parse_args()
    try:
        model = read_json(safe_path(args.root, args.model))
        current = capture(args.root, model)
        result = current if args.command == "capture" else {"status": "valid", "bindings": len(current["bindings"]), "unknowns": current["unknowns"]}
        if args.command == "check":
            if not args.baseline:
                parser.error("check requires --baseline")
            result = compare(current, read_json(safe_path(args.root, args.baseline)))
        if args.command == "events":
            if not args.events:
                parser.error("events requires --events")
            events = [json.loads(line) for line in safe_path(args.root, args.events).read_text(encoding="utf-8").splitlines()]
            result = {"status": "valid", **validate_events(events, model, current["build_id"])}
        if args.out:
            out = safe_path(args.root, args.out)
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
            print(json.dumps({"status": result.get("status", "captured"), "output": args.out, "build_id": current["build_id"]}))
        else:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        return 2 if result.get("status") == "stale" else 0
    except (ValueError, OSError, SyntaxError) as exc:
        print(json.dumps({"status": "invalid", "error": str(exc)}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
