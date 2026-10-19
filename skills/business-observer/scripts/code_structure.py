"""Deterministic Python slices for an authored business map, without importing code.

Syntactic references are candidates, not runtime calls or complete data flow.
Unresolved/dynamic calls stay explicit. Unchanged files reuse their parsed units.
"""
from __future__ import annotations
import argparse
import ast
import copy
import json
from pathlib import Path
try:
    from .behavior_model import ast_fingerprint, contained, digest, read
except ImportError:
    from behavior_model import ast_fingerprint, contained, digest, read


def key(path, name):
    return f"{path}::{name}"


def module_name(path):
    parts = Path(path).with_suffix("").parts
    return ".".join(parts[:-1] if parts[-1] == "__init__" else parts)


def parse_unit(path, source):
    tree = ast.parse(source, filename=path)
    imports, symbols, shadowed_globals = {}, {}, set()
    package = module_name(path).split(".")
    if not path.endswith("/__init__.py"):
        package = package[:-1]
    for node in tree.body:
        if isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            shadowed_globals.update(n.id for target in targets for n in ast.walk(target) if isinstance(n, ast.Name))
        if isinstance(node, ast.Import):
            for item in node.names:
                imports[item.asname or item.name.split(".")[0]] = item.name if item.asname else item.name.split(".")[0]
        if isinstance(node, ast.ImportFrom):
            prefix = package[:len(package)-node.level+1] if node.level else []
            target = ".".join(prefix + ([node.module] if node.module else []))
            for item in node.names:
                if item.name != "*":
                    imports[item.asname or item.name] = ".".join(filter(None, [target, item.name]))

    def walk(body, prefix="", class_name=None):
        for node in body:
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                continue
            name = prefix + node.name
            if name in symbols:
                raise ValueError("ambiguous definition: " + name)
            is_class = isinstance(node, ast.ClassDef)
            item = {"id": key(path, name), "path": path, "symbol": name,
                    "kind": "class" if is_class else "function", "class": class_name,
                    "line": node.lineno, "end_line": node.end_lineno,
                    "ast_hash": ast_fingerprint(node),
                    "signature": name if is_class else ast.unparse(node.args),
                    "parameters": [], "returns": None, "calls": [], "predicates": [], "fields": []}
            if not is_class:
                arguments = [*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs]
                arguments += [v for v in (node.args.vararg, node.args.kwarg) if v]
                item["parameters"] = [{"name": a.arg, "annotation": ast.unparse(a.annotation) if a.annotation else None} for a in arguments]
                item["returns"] = ast.unparse(node.returns) if node.returns else None
                local_names = {a.arg for a in arguments}
                local_names.update(n.id for n in ast.walk(node) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store))
                local_names.update(n.name for stmt in node.body for n in ast.walk(stmt) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)))
                for inner in ast.walk(node):
                    if isinstance(inner, (ast.Import, ast.ImportFrom)):
                        local_names.update(a.asname or a.name.split('.')[0] for a in inner.names)
                local_names -= {n for stmt in ast.walk(node) if isinstance(stmt, ast.Global) for n in stmt.names}
                item["local_names"] = sorted(local_names)

                class Body(ast.NodeVisitor):
                    def visit_FunctionDef(self, _): pass
                    def visit_AsyncFunctionDef(self, _): pass
                    def visit_ClassDef(self, _): pass
                    def visit_Lambda(self, _): pass
                    def visit_Call(self, call):
                        entry = {"expression": ast.unparse(call.func), "line": call.lineno, "column": call.col_offset,
                                 "args": [ast.unparse(a) for a in call.args],
                                 "keywords": {a.arg or "**": ast.unparse(a.value) for a in call.keywords}}
                        if len(call.args) >= 2 and all(isinstance(a, ast.Constant) and isinstance(a.value, str) for a in call.args[:2]):
                            entry["literal_pair"] = [a.value for a in call.args[:2]]
                        item["calls"].append(entry)
                        self.generic_visit(call)
                    def visit_Compare(self, expr):
                        item["predicates"].append({"line": expr.lineno, "expression": ast.unparse(expr)})
                        self.generic_visit(expr)
                    def visit_If(self, expr):
                        item["predicates"].append({"line": expr.lineno, "expression": ast.unparse(expr.test)})
                        self.generic_visit(expr)
                visitor = Body()
                for statement in node.body:
                    visitor.visit(statement)
            else:
                for statement in node.body:
                    if isinstance(statement, ast.AnnAssign):
                        item["fields"].append({"name": ast.unparse(statement.target), "type": ast.unparse(statement.annotation),
                                               "value": ast.unparse(statement.value) if statement.value else None})
            symbols[name] = item
            walk(node.body, name + ".", name if is_class else class_name)
    walk(tree.body)
    declarations = [{"line": n.lineno, "expression": ast.unparse(n)} for n in tree.body if isinstance(n, (ast.Assign, ast.AnnAssign))]
    return {"imports": imports, "symbols": symbols, "declarations": declarations, "shadowed_globals": sorted(shadowed_globals)}


def scan(root, paths, previous=None):
    units, errors, parsed, reused = {}, [], [], []
    extractor_hash = digest(Path(__file__).read_bytes())
    old = (previous or {}).get("units", {})
    for name in sorted(set(paths)):
        if not name.endswith(".py"):
            continue
        try:
            raw = contained(root, name).read_bytes()
            content_hash = digest(raw)
            if old.get(name, {}).get("file_hash") == content_hash and old[name].get("extractor_hash") == extractor_hash:
                units[name] = copy.deepcopy(old[name]); reused.append(name)
            else:
                units[name] = {"file_hash": content_hash, "extractor_hash": extractor_hash, **parse_unit(name, raw.decode("utf-8-sig"))}
                parsed.append(name)
        except (OSError, SyntaxError, ValueError, UnicodeError) as exc:
            errors.append({"path": name, "error": str(exc)})
    symbols = {s["id"]: copy.deepcopy(s) for unit in units.values() for s in unit["symbols"].values()}
    qualified = {module_name(s["path"]) + "." + s["symbol"]: s["id"] for s in symbols.values()}
    edges, unresolved = [], []
    for symbol in symbols.values():
        for call in symbol["calls"]:
            expr = call["expression"]
            head, *tail = expr.split(".")
            candidate = None
            if head in {"self", "cls"} and len(tail) == 1 and symbol["class"]:
                candidate = key(symbol["path"], symbol["class"] + "." + tail[0])
            elif head not in symbol.get("local_names", []) and head not in units[symbol["path"]].get("shadowed_globals", []):
                alias = units[symbol["path"]]["imports"].get(head)
                if alias:
                    candidate = qualified.get(".".join([alias, *tail]))
                else:
                    candidate = key(symbol["path"], expr)
            evidence = {"from": symbol["id"], **call, "evidence": "python-ast syntactic reference"}
            if candidate in symbols:
                edges.append({**evidence, "to": candidate})
            else:
                unresolved.append({**evidence, "reason": "external, dynamic, shadowed or outside selected scope"})
    return {"schema_version": 1, "units": units, "symbols": symbols, "edges": edges,
            "unresolved": unresolved, "errors": errors, "incremental": {"parsed": parsed, "reused": reused},
            "limits": ["Syntactic call candidates, not executed calls or proven data flow.",
                       "Reflection, decorators, inherited/overridden dispatch, callbacks and local instance aliases may remain unresolved.",
                       "Only explicitly selected Python files; no automatic discovery of every new entry point."]}


def enrich(authored, index, depth=1):
    """Keep business meaning authored; generate selected local function/call nodes.

    Existing source-bound program nodes anchor the slice. Helpers reached through
    resolved calls become children. No guard, business transition or runtime event
    is invented. Use a separate authored input or regenerate it before each call.
    """
    model = copy.deepcopy(authored)
    model["nodes"] = [n for n in model["nodes"] if n.get("origin") != "python-ast"]
    model["edges"] = [e for e in model["edges"] if e.get("origin") != "python-ast"]
    outgoing = {}
    for edge in index["edges"]:
        outgoing.setdefault(edge["from"], []).append(edge)
    roots = model.get("graph_roots") or [v["node"] for v in model["overview"]]
    by_id = {n["id"]: n for n in model["nodes"]}

    def group(node):
        seen = set()
        while node["id"] not in roots and node.get("parent") in by_id:
            if node["id"] in seen: raise ValueError("parent cycle")
            seen.add(node["id"]); node = by_id[node["parent"]]
        return node["id"]

    mapped, queue = {}, []
    for n in list(model["nodes"]):
        src = n.get("source")
        if not src or n.get("layer") in {"business", "state", "predicate"} or n["kind"] in {"data", "state"}:
            continue
        sid = key(src["path"], src["symbol"])
        if sid not in index["symbols"]: continue
        n["code_evidence"] = {"symbol": sid, "ast_hash": index["symbols"][sid]["ast_hash"], "origin": "python-ast"}
        g = group(n)
        # Shared functions may appear in different business invocation contexts.
        mapped.setdefault((g, sid), n["id"])
        queue.append((g, sid, n["id"], 0))
    seen, edge_ids = set(), {e["id"] for e in model["edges"]}
    while queue:
        g, sid, node_id, level = queue.pop(0)
        if (g, sid, node_id) in seen or level >= depth: continue
        seen.add((g, sid, node_id))
        for call in outgoing.get(sid, []):
            target = index["symbols"][call["to"]]
            if target["kind"] != "function": continue
            tid = mapped.get((g, target["id"]))
            if tid is None:
                tid = "code." + digest([g, target["id"]])[:16]
                helper = {"id": tid, "kind": "function", "layer": "program", "origin": "python-ast",
                    "label": target["symbol"], "summary": "局部静态调用；是否执行由运行事实确认。",
                    "source": {"path": target["path"], "symbol": target["symbol"]}, "parent": node_id,
                    "capture": {"in": {}, "out": {}}, "signature": target["signature"],
                    "code_evidence": {"symbol": target["id"], "ast_hash": target["ast_hash"],
                                      "parameters": target["parameters"], "returns": target["returns"], "origin": "python-ast"}}
                model["nodes"].append(helper); by_id[tid] = helper; mapped[(g, target["id"])] = tid
                model["edges"].append({"id": "contains."+tid, "from": node_id, "to": tid, "type": "contains",
                                       "label": "局部函数", "origin": "python-ast", "evidence": "business-map anchor + Python AST call"})
            eid = "call." + digest([node_id, tid, call["expression"], call["args"], call["keywords"], call["line"]])[:16]
            if eid not in edge_ids:
                model["edges"].append({"id": eid, "from": node_id, "to": tid, "type": "flow",
                    "label": "静态调用 " + call["expression"], "origin": "python-ast", "evidence": call["evidence"],
                    "callsite": {k: call[k] for k in ("line", "column", "args", "keywords")}})
                edge_ids.add(eid)
            queue.append((g, target["id"], tid, level+1))
    model["static_structure"] = {"files": {p: u["file_hash"] for p, u in index["units"].items()},
        "resolved_calls": len(index["edges"]), "unresolved_calls": len(index["unresolved"]),
        "depth": depth, "limits": index["limits"]}
    return model


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["scan", "project"])
    parser.add_argument("--root", required=True); parser.add_argument("--files", nargs="+", required=True)
    parser.add_argument("--out", required=True); parser.add_argument("--previous"); parser.add_argument("--model")
    parser.add_argument("--depth", type=int, default=1)
    a = parser.parse_args()
    index = scan(a.root, a.files, read(contained(a.root, a.previous)) if a.previous else None)
    result = index
    if a.command == "project":
        if not a.model or a.model == a.out: raise ValueError("project needs a separate authored --model and --out")
        result = enrich(read(contained(a.root, a.model)), index, a.depth)
    target = contained(a.root, a.out); target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8", newline="\n")
    print(json.dumps({"written": a.out, "symbols": len(index["symbols"]), "resolved_calls": len(index["edges"]),
                      "unresolved_calls": len(index["unresolved"]), "errors": index["errors"]}, ensure_ascii=False))
    return 1 if index["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
