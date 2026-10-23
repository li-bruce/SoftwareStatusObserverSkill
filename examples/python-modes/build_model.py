"""Maintain an explicit behavior declaration plus deterministic Python AST bindings.

This small example has a source freshness check, not the full change_sync gate.
Rebuilding a hash cannot prove that the implementation matches the declaration;
test_modes.py independently checks the outcomes and observation boundaries.
"""
import ast
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
STATES = ["pending", "waiting", "running", "done"]


def build():
    transitions = [
        {"trigger": "start", "source": "pending", "dest": "running", "conditions": "available"},
        {"trigger": "start", "source": "pending", "dest": "waiting", "unless": "available"},
        {"trigger": "resume", "source": "waiting", "dest": "running", "conditions": "available"},
        {"trigger": "finish", "source": "running", "dest": "done"},
    ]
    machine = {"engine": "adapter-selected", "version": "1", "states": STATES, "values": STATES,
        "initial": "pending", "state_type": "str enum", "transitions": transitions,
        "events": {name: {"payload": {}} for name in ("start", "resume", "finish")},
        "context": {"slots": {"type": "integer", "min": 0}, "effects": {"type": "integer", "min": 0}},
        "guards": {"available": "An available slot exists"}}
    nodes = [{"id": "job", "kind": "action", "layer": "business", "label": "Execute task", "source": {"path":"app.py", "symbol":"Job.run"}},
             {"id": "slots", "kind": "data", "parent": "job", "label": "Available slots", "value_type": "integer"}]
    nodes += [{"id": "state." + s, "kind": "state", "layer": "state", "parent": "job", "value": s, "label": s} for s in STATES]
    edges = [{"id": "transition:" + str(i), "from": "state." + t["source"], "to": "state." + t["dest"],
              "type": "flow", "event": t["trigger"], "conditions": t.get("conditions"), "unless": t.get("unless")} for i, t in enumerate(transitions)]
    # Exact local signatures/lines come from the source. The business grouping above is authored.
    tree = ast.parse((ROOT / "app.py").read_text(encoding="utf-8"))
    for cls in tree.body:
        if not isinstance(cls, ast.ClassDef): continue
        for fn in cls.body:
            if not isinstance(fn, ast.FunctionDef) or fn.name.startswith("_"): continue
            symbol = cls.name + "." + fn.name
            nodes.append({"id": symbol, "kind": "function", "parent": "job", "label": symbol,
                "source": {"path": "app.py", "symbol": symbol, "line": fn.lineno},
                "parameters": [{"name": arg.arg, "type": ast.unparse(arg.annotation) if arg.annotation else "unknown"}
                               for arg in fn.args.args if arg.arg != "self"]})
    edges += [{"id": "contains:" + n["id"], "from": n["parent"], "to": n["id"], "type": "contains"} for n in nodes if n.get("parent")]
    for node in nodes:
        node['summary'] = "Actual task implementation: " + node['label']
    for edge in edges:
        edge['evidence'] = 'executable declaration and Python source'
    files = ["intent.json", "bo_stategraph/driver.py", "bo_stategraph/bo_contracts.py", "bo_stategraph/execution_contract.py", "app.py", "run.py", "build_model.py", "test_modes.py", "bo_stategraph/__init__.py", "bo_stategraph/binding.py"]
    model = {"schema_version": 3, "revision": "1", "machine": machine, "nodes": nodes, "edges": edges,
        "graph_roots": ["job"], "intent":"intent.json", "overview":[{"node":"job"}], "source_files": files,
        "scope": {"unknowns": ["Validates local task state, available slots, and commit count; no database, concurrency, or authorization engine."]}}
    (ROOT / "bo_stategraph/model.json").write_text(json.dumps(model, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    hashes = {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in files + ["bo_stategraph/model.json"]}
    manifest = {"files": hashes, "build_id": hashlib.sha256(json.dumps(hashes, sort_keys=True).encode()).hexdigest()}
    (ROOT / "bo_stategraph/sources.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8", newline="\n")


if __name__ == "__main__": build()
