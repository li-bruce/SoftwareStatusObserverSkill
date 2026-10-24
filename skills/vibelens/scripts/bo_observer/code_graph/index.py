"""Build a deterministic graph from parser facts, without running application code.

This layer describes source structure. It does not infer business intent, runtime
dispatch, or data flow from a syntactic call.
"""

from pathlib import PurePosixPath
from copy import deepcopy
from ..sources import SOURCE_SUFFIXES
from ..graph.code_structure import module_name
from ..graph.behavior_model import digest


def identity(role, value):
    """Keep identity independent of line numbers, labels and source revisions."""
    return "code:" + role + ":" + digest(value)[:24]


def import_target(path, reference, units):
    """Resolve only project-local imports supported by the indexed source scope."""
    if isinstance(reference, str):
        modules = {module_name(p): p for p in units if p.endswith(".py")}
        parts = reference.split(".")
        for size in range(len(parts), 0, -1):
            if ".".join(parts[:size]) in modules:
                return modules[".".join(parts[:size])]
        return None
    module = reference["module"]
    if not module.startswith("."):
        return None
    parts = []
    for part in (PurePosixPath(path).parent / module).parts:
        if part == "..":
            if not parts:
                return None
            parts.pop()
        elif part != ".":
            parts.append(part)
    stem = "/".join(parts)
    candidates = [stem]
    if PurePosixPath(stem).suffix in {".js", ".mjs", ".cjs"}:
        candidates += [
            str(PurePosixPath(stem).with_suffix(s)) for s in (".ts", ".tsx", ".mts", ".cts")
        ]
    if not PurePosixPath(stem).suffix:
        candidates += [stem + s for s in sorted(SOURCE_SUFFIXES)]
        candidates += [stem + "/index" + s for s in (".js", ".ts", ".tsx")]
    return next((p for p in candidates if p in units), None)


def build(index):
    """Project files, declarations, parameters, imports and call occurrences."""
    index = deepcopy(index)
    for path, unit in index["units"].items():
        calls = unit.get("module_calls", [])
        if not calls:
            continue
        key = path + "::<module>"
        symbol = {
            "id": key,
            "path": path,
            "symbol": "<module>",
            "kind": "function",
            "line": 1,
            "end_line": max(c["line"] for c in calls),
            "signature": "Module initialization",
            "parameters": [],
        }
        unit["symbols"]["<module>"] = index["symbols"][key] = symbol
        for call in calls:
            target = path + "::" + call["expression"]
            if target not in index["symbols"]:
                ref = unit["imports"].get(call["expression"])
                imported = import_target(path, ref, index["units"]) if ref else None
                target = (
                    str(imported) + "::" + (ref.rsplit(".", 1)[-1] if isinstance(ref, str) else "")
                )
            evidence = {
                **call,
                "from": key,
                "evidence": "python syntax reference; execution unproven",
            }
            if target in index["symbols"]:
                index["edges"].append({**evidence, "to": target})
            else:
                index["unresolved"].append(
                    {**evidence, "reason": "External or unresolved initializer"}
                )
    nodes, edges, bindings = {}, [], {}
    units, symbols = index["units"], index["symbols"]
    symbol_ids = {key: identity("symbol", key) for key in symbols}
    file_ids = {path: identity("file", path) for path in units}
    counts = {}

    def edge(source, target, relation, label, evidence=None):
        signature = [source, target, relation, label]
        occurrence = counts.get(digest(signature), 0)
        counts[digest(signature)] = occurrence + 1
        item = {
            "id": identity("edge", [signature, occurrence]),
            "from": source,
            "to": target,
            "type": "data",
            "code_relation": relation,
            "label": label,
            "origin": "code-index",
        }
        if evidence:
            item["evidence"] = evidence
        edges.append(item)

    def node(key, label, role, source=None, parent=None, summary=""):
        value = {
            "id": key,
            "label": label,
            "kind": "data" if role in {"file", "parameter", "unresolved"} else "function",
            "layer": "code",
            "code_role": role,
            "origin": "code-index",
            "summary": summary,
        }
        if source:
            value["source"] = source
            bindings[key] = {**source, "code_revision": True}
        if parent:
            value["parent"] = parent
        nodes[key] = value
        return value

    for path, unit in sorted(units.items()):
        node(
            file_ids[path],
            path,
            "file",
            {"path": path, "line": 1, "symbol": "<file>"},
            summary=unit.get("language", "source"),
        )
    for key, symbol in sorted(symbols.items()):
        prefix = symbol["symbol"].rsplit(".", 1)[0] if "." in symbol["symbol"] else None
        parent = symbol_ids.get(symbol["path"] + "::" + str(prefix), file_ids[symbol["path"]])
        source = {k: symbol[k] for k in ("path", "symbol", "line", "end_line")}
        value = node(
            symbol_ids[key],
            symbol["symbol"],
            symbol["kind"],
            source,
            parent,
            symbol.get("signature", ""),
        )
        value["code_symbol"] = key
        value["code_signature"] = symbol.get("signature", "")
        value["code_returns"] = symbol.get("returns")
        edge(parent, value["id"], "defines", "Defines")
        for parameter in symbol.get("parameters", []):
            pid = identity("parameter", [key, parameter["name"]])
            node(
                pid,
                parameter["name"],
                "parameter",
                source,
                value["id"],
                parameter.get("annotation") or "Type unspecified",
            )
            edge(pid, value["id"], "parameter", "Parameter")

    for path, unit in sorted(units.items()):
        for alias, reference in sorted(unit.get("imports", {}).items()):
            target = import_target(path, reference, units)
            name = reference if isinstance(reference, str) else reference["module"]
            if target:
                tid = file_ids[target]
            else:
                tid = identity("import", [path, name])
                node(
                    tid,
                    name,
                    "unresolved",
                    parent=file_ids[path],
                    summary="External or unresolved import",
                )
            # The alias may contain a source offset for a side-effect import.
            edge(
                file_ids[path],
                tid,
                "imports",
                "Imports " + (name if alias.startswith("<side-effect:") else alias),
            )
        for symbol in unit["symbols"].values():
            for base in symbol.get("bases", []):
                target = symbol["path"] + "::" + base
                if target not in symbol_ids:
                    ref = unit.get("imports", {}).get(base)
                    imported = import_target(path, ref, units) if ref else None
                    imported_name = (
                        ref.rsplit(".", 1)[-1]
                        if isinstance(ref, str)
                        else (ref or {}).get("name", base)
                    )
                    target = str(imported) + "::" + imported_name
                if target in symbol_ids:
                    tid = symbol_ids[target]
                else:
                    tid = identity("base", [symbol["id"], base])
                    node(
                        tid,
                        base,
                        "unresolved",
                        parent=file_ids[path],
                        summary="Unresolved base type",
                    )
                edge(symbol_ids[symbol["id"]], tid, "inherits", "Extends " + base)
    for call in [*index["edges"], *index["unresolved"]]:
        source = symbol_ids[call["from"]]
        target = symbol_ids.get(call.get("to"))
        if not target:
            target = identity("unresolved", [call["from"], call["expression"]])
            node(
                target,
                call["expression"],
                "unresolved",
                parent=source,
                summary=call.get("reason", "Target unresolved"),
            )
        edge(
            source,
            target,
            "calls",
            call["expression"],
            {k: call[k] for k in ("line", "column", "evidence") if k in call},
        )
    result = {
        "schema": "bo-code-graph/v1",
        "nodes": list(nodes.values()),
        "edges": edges,
        "bindings": bindings,
        "files": {p: u["file_hash"] for p, u in sorted(units.items())},
        "symbols": symbol_ids,
        "errors": index["errors"],
        "limits": index["limits"],
        "incremental": index["incremental"],
    }
    result["revision"] = digest({k: result[k] for k in ("nodes", "edges", "files", "errors")})
    return result
