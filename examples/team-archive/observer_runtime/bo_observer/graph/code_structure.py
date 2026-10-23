"""Deterministic source slices for an authored business map, without importing code.

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
    from ...behavior_model import ast_fingerprint, contained, digest, read
except ImportError:
    from behavior_model import ast_fingerprint, contained, digest, read


def key(path, name):
    return f"{path}::{name}"


def module_name(path):
    parts = Path(path).with_suffix("").parts
    return ".".join(parts[:-1] if parts[-1] == "__init__" else parts)


def parse_unit(path, source):
    """Extract Python symbols, parameters, and call expressions from the syntax tree."""
    tree = ast.parse(source, filename=path)
    imports, symbols, shadowed_globals = {}, {}, set()
    package = module_name(path).split(".")
    if not path.endswith("/__init__.py"):
        package = package[:-1]
    for node in tree.body:
        if isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            shadowed_globals.update(
                n.id for target in targets for n in ast.walk(target) if isinstance(n, ast.Name)
            )
        if isinstance(node, ast.Import):
            for item in node.names:
                imports[item.asname or item.name.split(".")[0]] = (
                    item.name if item.asname else item.name.split(".")[0]
                )
        if isinstance(node, ast.ImportFrom):
            prefix = package[: len(package) - node.level + 1] if node.level else []
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
            item = {
                "id": key(path, name),
                "path": path,
                "symbol": name,
                "kind": "class" if is_class else "function",
                "class": class_name,
                "line": node.lineno,
                "end_line": node.end_lineno,
                "ast_hash": ast_fingerprint(node),
                "signature": name if is_class else ast.unparse(node.args),
                "parameters": [],
                "returns": None,
                "calls": [],
                "predicates": [],
                "fields": [],
            }
            item["entrypoints"] = [
                ast.unparse(d)
                for d in node.decorator_list
                if isinstance(d, ast.Call)
                and isinstance(d.func, ast.Attribute)
                and d.func.attr
                in {
                    "route",
                    "get",
                    "post",
                    "put",
                    "patch",
                    "delete",
                    "websocket",
                    "command",
                    "task",
                }
            ]
            if not is_class:
                arguments = [*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs]
                arguments += [v for v in (node.args.vararg, node.args.kwarg) if v]
                item["parameters"] = [
                    {
                        "name": a.arg,
                        "annotation": ast.unparse(a.annotation) if a.annotation else None,
                    }
                    for a in arguments
                ]
                item["returns"] = ast.unparse(node.returns) if node.returns else None
                local_names = {a.arg for a in arguments}
                local_names.update(
                    n.id
                    for n in ast.walk(node)
                    if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store)
                )
                local_names.update(
                    n.name
                    for stmt in node.body
                    for n in ast.walk(stmt)
                    if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
                )
                for inner in ast.walk(node):
                    if isinstance(inner, (ast.Import, ast.ImportFrom)):
                        local_names.update(a.asname or a.name.split(".")[0] for a in inner.names)
                local_names -= {
                    n for stmt in ast.walk(node) if isinstance(stmt, ast.Global) for n in stmt.names
                }
                item["local_names"] = sorted(local_names)

                class Body(ast.NodeVisitor):
                    def visit_FunctionDef(self, _):
                        pass

                    def visit_AsyncFunctionDef(self, _):
                        pass

                    def visit_ClassDef(self, _):
                        pass

                    def visit_Lambda(self, _):
                        pass

                    def visit_Call(self, call):
                        entry = {
                            "expression": ast.unparse(call.func),
                            "line": call.lineno,
                            "column": call.col_offset,
                            "args": [ast.unparse(a) for a in call.args],
                            "keywords": {
                                a.arg or "**": ast.unparse(a.value) for a in call.keywords
                            },
                        }
                        if len(call.args) >= 2 and all(
                            isinstance(a, ast.Constant) and isinstance(a.value, str)
                            for a in call.args[:2]
                        ):
                            entry["literal_pair"] = [a.value for a in call.args[:2]]
                        item["calls"].append(entry)
                        self.generic_visit(call)

                    def visit_Compare(self, expr):
                        item["predicates"].append(
                            {"line": expr.lineno, "expression": ast.unparse(expr)}
                        )
                        self.generic_visit(expr)

                    def visit_If(self, expr):
                        item["predicates"].append(
                            {"line": expr.lineno, "expression": ast.unparse(expr.test)}
                        )
                        self.generic_visit(expr)

                visitor = Body()
                for statement in node.body:
                    visitor.visit(statement)
            else:
                for statement in node.body:
                    if isinstance(statement, ast.AnnAssign):
                        item["fields"].append(
                            {
                                "name": ast.unparse(statement.target),
                                "type": ast.unparse(statement.annotation),
                                "value": ast.unparse(statement.value) if statement.value else None,
                            }
                        )
            symbols[name] = item
            walk(node.body, name + ".", name if is_class else class_name)

    walk(tree.body)
    declarations = [
        {"line": n.lineno, "expression": ast.unparse(n)}
        for n in tree.body
        if isinstance(n, (ast.Assign, ast.AnnAssign))
    ]
    return {
        "imports": imports,
        "symbols": symbols,
        "declarations": declarations,
        "shadowed_globals": sorted(shadowed_globals),
    }


def scan(root, paths, previous=None):
    """Delegate source indexing to the language-aware dispatcher and its cache."""
    try:
        from ..sources import scan as scan_sources
    except ImportError:
        from bo_observer.sources import scan as scan_sources
    return scan_sources(root, paths, previous)


def enrich(authored, index, depth=1):
    """Keep business meaning authored; generate selected local function/call nodes.

    Existing source-bound program nodes anchor the slice. Helpers reached through
    resolved calls become children. No guard, business transition or runtime event
    is invented. Use a separate authored input or regenerate it before each call.
    """
    try:
        from ...observation_scope import observer_symbols
    except ImportError:
        from observation_scope import observer_symbols
    internal = observer_symbols(authored.get("implementation"), index)
    model = copy.deepcopy(authored)
    model["nodes"] = [
        n for n in model["nodes"] if n.get("origin") not in {"python-ast", "source-ast"}
    ]
    model["edges"] = [
        e for e in model["edges"] if e.get("origin") not in {"python-ast", "source-ast"}
    ]
    outgoing = {}
    for edge in index["edges"]:
        outgoing.setdefault(edge["from"], []).append(edge)
    roots = model.get("graph_roots") or [v["node"] for v in model["overview"]]
    by_id = {n["id"]: n for n in model["nodes"]}

    def group(node):
        seen = set()
        while node["id"] not in roots and node.get("parent") in by_id:
            if node["id"] in seen:
                raise ValueError("parent cycle")
            seen.add(node["id"])
            node = by_id[node["parent"]]
        return node["id"]

    mapped, queue = {}, []
    for n in list(model["nodes"]):
        src = n.get("source")
        if not src or n.get("layer") in {"state", "predicate"} or n["kind"] in {"data", "state"}:
            continue
        sid = key(src["path"], src["symbol"])
        if sid in internal:
            continue
        if sid not in index["symbols"]:
            continue
        n["code_evidence"] = {
            "symbol": sid,
            "ast_hash": index["symbols"][sid]["ast_hash"],
            "origin": "source-ast",
        }
        g = group(n)
        # Shared functions may appear in different business invocation contexts.
        mapped.setdefault((g, sid), n["id"])
        queue.append((g, sid, n["id"], 0))
    seen, edge_ids = set(), {e["id"] for e in model["edges"]}
    while queue:
        g, sid, node_id, level = queue.pop(0)
        if (g, sid, node_id) in seen or level >= depth:
            continue
        seen.add((g, sid, node_id))
        occurrences = {}
        for call in outgoing.get(sid, []):
            if call["to"] in internal:
                continue
            target = index["symbols"][call["to"]]
            if target["kind"] != "function":
                continue
            tid = mapped.get((g, target["id"]))
            if tid is None:
                tid = "code." + digest([g, target["id"]])[:16]
                helper = {
                    "id": tid,
                    "kind": "function",
                    "layer": "program",
                    "origin": "source-ast",
                    "label": target["symbol"],
                    "summary": "Local static call; execution requires runtime evidence.",
                    "source": {"path": target["path"], "symbol": target["symbol"]},
                    "parent": node_id,
                    "capture": {"in": {}, "out": {}},
                    "signature": target["signature"],
                    "code_evidence": {
                        "symbol": target["id"],
                        "ast_hash": target["ast_hash"],
                        "parameters": target["parameters"],
                        "returns": target["returns"],
                        "origin": "source-ast",
                    },
                }
                model["nodes"].append(helper)
                by_id[tid] = helper
                mapped[(g, target["id"])] = tid
                model["edges"].append(
                    {
                        "id": "contains." + tid,
                        "from": node_id,
                        "to": tid,
                        "type": "contains",
                        "label": "Local function",
                        "origin": "source-ast",
                        "evidence": "business-map anchor + source AST call",
                    }
                )
            # Source lines locate evidence; they are not relation identity.
            # A repeated identical call uses its occurrence within this caller.
            identity = [node_id, tid, call["expression"], call["args"], call["keywords"]]
            fingerprint = digest(identity)
            occurrence = occurrences.get(fingerprint, 0)
            occurrences[fingerprint] = occurrence + 1
            eid = "call." + digest([identity, occurrence])[:16]
            if eid not in edge_ids:
                model["edges"].append(
                    {
                        "id": eid,
                        "from": node_id,
                        "to": tid,
                        "type": "flow",
                        "label": "Static call " + call["expression"],
                        "origin": "source-ast",
                        "evidence": call["evidence"],
                        "callsite": {k: call[k] for k in ("line", "column", "args", "keywords")},
                    }
                )
                edge_ids.add(eid)
            queue.append((g, target["id"], tid, level + 1))
    # Inventory obligations add missing implementations below their authored
    # feature. The semantic owner is explicit; AST never guesses it from names.
    plan = model.get("implementation") or {}
    owners = {sid: item.get("node") for sid, item in plan.get("support", {}).items()}
    for feature in plan.get("features", []):
        owner = feature.get("business_node")
        if owner in by_id:
            roles = by_id[owner].setdefault("semantic_roles", [])
            if "business" not in roles:
                roles.append("business")
        owners.update({sid: owner for sid in feature.get("sources", [])})
    bound = {
        key(n["source"]["path"], n["source"]["symbol"]) for n in model["nodes"] if n.get("source")
    }
    for sid, parent in sorted(owners.items()):
        if sid in internal:
            continue
        target = index["symbols"].get(sid)
        if sid in bound or not target or parent not in by_id:
            continue
        tid = "implementation." + digest(sid)[:16]
        helper = {
            "id": tid,
            "kind": "function",
            "layer": "program",
            "origin": "source-ast",
            "label": target["symbol"],
            "summary": "Implementation ownership; source and runtime records establish calls",
            "source": {"path": target["path"], "symbol": target["symbol"]},
            "parent": parent,
            "capture": {"in": {}, "out": {}},
            "signature": target["signature"],
            "code_evidence": {
                "symbol": sid,
                "ast_hash": target["ast_hash"],
                "parameters": target["parameters"],
                "returns": target["returns"],
                "origin": "source-ast",
            },
        }
        model["nodes"].append(helper)
        by_id[tid] = helper
        model["edges"].append(
            {
                "id": "contains." + tid,
                "from": parent,
                "to": tid,
                "type": "contains",
                "label": "Implementation function",
                "origin": "source-ast",
                "evidence": "implementation inventory + source AST",
            }
        )
    # Preserve calls between inventoried implementations, including helpers that
    # are beyond the default displayed slice. No runtime execution is inferred.
    by_symbol = {}
    for n in model["nodes"]:
        if n.get("source"):
            by_symbol.setdefault(key(n["source"]["path"], n["source"]["symbol"]), n["id"])
    pairs = {
        (e["from"], e["to"], e.get("callsite", {}).get("line"), e.get("callsite", {}).get("column"))
        for e in model["edges"]
        if e.get("origin") in {"python-ast", "source-ast"}
    }
    occurrences = {}
    for call in index["edges"]:
        if call["from"] in internal or call["to"] in internal:
            continue
        a, b = by_symbol.get(call["from"]), by_symbol.get(call["to"])
        identity = [a, b, call["expression"], call["args"], call["keywords"]]
        fingerprint = digest(identity)
        occurrence = occurrences.get(fingerprint, 0)
        occurrences[fingerprint] = occurrence + 1
        if a and b and (a, b, call["line"], call["column"]) not in pairs:
            model["edges"].append(
                {
                    "id": "inventory-call." + digest([identity, occurrence])[:16],
                    "from": a,
                    "to": b,
                    "type": "flow",
                    "label": "Static call " + call["expression"],
                    "origin": "source-ast",
                    "evidence": call["evidence"],
                    "callsite": {k: call[k] for k in ("line", "column", "args", "keywords")},
                }
            )
    model["static_structure"] = {
        "files": {p: u["file_hash"] for p, u in index["units"].items()},
        "resolved_calls": len(index["edges"]),
        "unresolved_calls": len(index["unresolved"]),
        "depth": depth,
        "limits": index["limits"],
    }
    return model


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["scan", "project"])
    parser.add_argument("--root", required=True)
    parser.add_argument("--files", nargs="+", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--previous")
    parser.add_argument("--model")
    parser.add_argument("--depth", type=int, default=1)
    a = parser.parse_args()
    index = scan(a.root, a.files, read(contained(a.root, a.previous)) if a.previous else None)
    result = index
    if a.command == "project":
        if not a.model or a.model == a.out:
            raise ValueError("project needs a separate authored --model and --out")
        result = enrich(read(contained(a.root, a.model)), index, a.depth)
    target = contained(a.root, a.out)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8", newline="\n"
    )
    print(
        json.dumps(
            {
                "written": a.out,
                "symbols": len(index["symbols"]),
                "resolved_calls": len(index["edges"]),
                "unresolved_calls": len(index["unresolved"]),
                "errors": index["errors"],
            },
            ensure_ascii=False,
        )
    )
    return 1 if index["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
