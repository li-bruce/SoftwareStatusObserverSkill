"""Extract a bounded, source-preserving view from one version of a typed graph."""
from __future__ import annotations
import argparse
from collections import deque
from copy import deepcopy
import html
import json
from pathlib import Path
try:
    from ...behavior_model import read, contained, digest
except ImportError:
    from behavior_model import read, contained, digest

CRITICAL = {"guard", "condition", "depends", "resource", "join", "data", "reads", "writes"}


def extract(model, anchors, *, depth=1, max_nodes=24, max_edges=48, relations=None,
            events=(), run_id=None, build_id=None):
    if type(depth) is not int or not 0 <= depth <= 12:
        raise ValueError("depth must be 0..12")
    if (type(max_nodes) is not int or type(max_edges) is not int
            or not 1 <= max_nodes <= 1000 or not 1 <= max_edges <= 4000):
        raise ValueError("invalid node/edge budget")
    if run_id and not build_id:
        raise ValueError("runtime focus requires build_id as well as run_id")
    nodes = {n["id"]: n for n in model["nodes"]}
    edges = model["edges"]
    if len(nodes) != len(model["nodes"]) or any(n.startswith("view:") for n in nodes):
        raise ValueError("duplicate node or reserved view namespace")
    edge_ids = [e["id"] for e in edges]
    if len(edge_ids) != len(set(edge_ids)) or any(
        e["from"] not in nodes or e["to"] not in nodes for e in edges
    ):
        raise ValueError("invalid edge identities/endpoints")
    anchors = sorted(set(anchors))
    if not anchors or set(anchors) - nodes.keys():
        raise ValueError("unknown or missing focus node")
    if len(anchors) > max_nodes:
        raise ValueError("budget cannot hold requested anchors")
    adjacent = {n: [] for n in nodes}
    for e in edges:
        adjacent[e["from"]].append(e)
        adjacent[e["to"]].append(e)
    selected, queue = set(anchors), deque((n, 0) for n in anchors)
    limited = False
    while queue:
        node, level = queue.popleft()
        if level >= depth:
            continue
        for edge in sorted(adjacent[node], key=lambda e: (e["type"] not in CRITICAL, e["id"])):
            if relations is not None and edge["type"] not in relations:
                continue
            other = edge["to"] if edge["from"] == node else edge["from"]
            if other in selected:
                continue
            if len(selected) >= max_nodes:
                limited = True
                continue
            selected.add(other); queue.append((other, level + 1))
    candidates = sorted((e for e in edges if e["from"] in selected and e["to"] in selected
                         and (relations is None or e["type"] in relations)),
                        key=lambda e: (e["type"] not in CRITICAL, e["id"]))
    included = candidates[:max_edges]
    used = {e["id"] for e in included}
    omitted = sorted((e for e in edges if e["id"] not in used
                      and (e["from"] in selected or e["to"] in selected)), key=lambda e: e["id"])
    boundaries = []
    for edge in omitted[:max_edges]:
        outside = [n for n in (edge["from"], edge["to"]) if n not in selected]
        boundaries.append({"id": "view:boundary:" + digest(edge["id"])[:16],
                           "edge_id": edge["id"], "from": edge["from"], "to": edge["to"],
                           "type": edge["type"], "label": edge.get("label", edge["type"]),
                           "relation": deepcopy(edge),
                           "outside": [{"id": n, "label": nodes[n]["label"], "kind": nodes[n]["kind"]}
                                       for n in outside],
                           "reason": "relation_filter" if relations is not None and edge["type"] not in relations
                                     else "edge_budget" if not outside else "outside_focus",
                           "meaning": "Original relation continues outside this view; no inferred shortcut."})
    observed, gaps = [], []
    if run_id:
        chosen = [e for e in events if e.get("run_id") == run_id and e.get("node") in selected]
        if not chosen:
            gaps.append("no selected events for requested run")
        for event in chosen:
            if event.get("model_revision") != model["revision"] or (
                build_id is not None and event.get("build_id") != build_id
            ):
                gaps.append("stale runtime event: " + str(event.get("id")))
            else:
                observed.append(deepcopy(event))
    unresolved = deepcopy(model.get("scope", {}).get("unknowns", []))
    result = {
        "schema_version": 1,
        "base": {"project_id": model.get("presentation", {}).get("layout_id", model.get("project_id", "project")),
                 "model_revision": model["revision"], "model_hash": digest(model), "build_id": build_id},
        "selection": {"nodes": anchors, "depth": depth, "max_nodes": max_nodes,
                      "max_edges": max_edges, "relations": sorted(relations) if relations is not None else None,
                      "run_id": run_id},
        "nodes": [deepcopy(nodes[n]) for n in sorted(selected)], "edges": deepcopy(included),
        "boundaries": boundaries,
        "mapping": {n: {"nodes": [n], "source": deepcopy(nodes[n].get("source"))} for n in sorted(selected)},
        "events": observed,
        "coverage": {"selected_nodes": len(selected), "total_nodes": len(nodes),
                     "crossing_or_omitted_edges": len(omitted), "reported_boundaries": len(boundaries),
                     "limits_hit": [name for name, hit in (
                         ("nodes", limited), ("edges", len(candidates) > max_edges),
                         ("boundaries", len(omitted) > max_edges)) if hit],
                     "source_unknowns": unresolved, "evidence_gaps": sorted(set(gaps)),
                     "runtime_evidence": "not_selected" if not run_id else "partial" if gaps else "selected",
                     "complete": not omitted and not unresolved and not gaps},
        "questions": deepcopy(model.get("questions", [])),
    }
    result["focus_id"] = "focus:" + digest(result)[:20]
    return result


def markdown(view):
    """Static conversation view; IDs are preserved in the accompanying JSON."""
    def label(value):
        return html.escape(str(value), quote=True).replace("\n", " ").replace("`", "&#96;")
    aliases = {n["id"]: "n" + str(i) for i, n in enumerate(view["nodes"])}
    lines = ["# Focused business and implementation graph", "", f"Model revision: {view['base']['model_revision']}",
             f"Focus graph: `{view['focus_id']}`", "", "```mermaid", "flowchart LR"]
    for n in view["nodes"]:
        operator = f' · {n["operator"]}' if n.get("operator") else ""
        lines.append(f'  {aliases[n["id"]]}["{label(n["label"] + operator)}"]')
    for e in view["edges"]:
        lines.append(f'  {aliases[e["from"]]} -->|"{label(e.get("label", e["type"]))}"| {aliases[e["to"]]}')
    for i, b in enumerate(view["boundaries"]):
        outside = b["outside"]
        if outside:
            other = outside[0]
            lines.append(f'  b{i}["{label(other["label"])} (outside scope)"]')
            left, right = aliases.get(b["from"], f"b{i}"), aliases.get(b["to"], f"b{i}")
            lines.append(f'  {left} -.->|"{label(b["label"])}"| {right}')
    lines += ["```", "", "Dashed edges preserve original relations outside this scope. They do not imply execution or permission.", "",
              "| Node | Type | Source |", "|---|---|---|"]
    for n in view["nodes"]:
        source = n.get("source", {})
        lines.append(f'| {label(n["label"])} | {label(n["kind"])} | '
                     f'{label(source.get("path", ""))} {label(source.get("symbol", ""))} |')
    c = view["coverage"]
    lines += ["", f"Crossing or omitted relations: {c['crossing_or_omitted_edges']}；"
              f"Unresolved items: {len(c['source_unknowns'])}; runtime evidence: {c['runtime_evidence']}。", ""]
    if view["boundaries"]:
        lines += ["| Collapsed relation | Type | Role |", "|---|---|---|"]
        for b in view["boundaries"]:
            relation = b["relation"]
            lines.append(f'| {label(b["from"])} → {label(b["to"])} | {label(b["type"])} | '
                         f'{label(relation.get("operand", b["label"]))} |')
        lines.append("")
    return "\n".join(lines)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", required=True); p.add_argument("--model", required=True)
    p.add_argument("--nodes", nargs="+", required=True)
    p.add_argument("--depth", type=int, default=1)
    p.add_argument("--max-nodes", type=int, default=24); p.add_argument("--max-edges", type=int, default=48)
    p.add_argument("--relations", nargs="+"); p.add_argument("--events"); p.add_argument("--run-id")
    p.add_argument("--build-id"); p.add_argument("--out", required=True); p.add_argument("--markdown")
    a = p.parse_args(); root = Path(a.root).absolute().resolve()
    events = read(contained(root, a.events)) if a.events else []
    if not isinstance(events, list):
        raise ValueError("--events must contain a JSON array")
    from ..model_io import read_model
    result = extract(read_model(contained(root, a.model)), a.nodes, depth=a.depth, max_nodes=a.max_nodes,
                     max_edges=a.max_edges, relations=a.relations, events=events,
                     run_id=a.run_id, build_id=a.build_id)
    out = contained(root, a.out); out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    if a.markdown:
        md = contained(root, a.markdown); md.parent.mkdir(parents=True, exist_ok=True)
        md.write_text(markdown(result), encoding="utf-8")
    print(json.dumps({"valid": True, "focus_id": result["focus_id"], "coverage": result["coverage"]}, ensure_ascii=False))


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(json.dumps({"valid": False, "error": str(exc)}, ensure_ascii=False))
        raise SystemExit(2)
