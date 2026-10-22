"""Generate graph and bindings from reviewed project declarations; no observed expectations."""
import json
import hashlib
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from bo_stategraph.declaration import definition, LABELS
from observer_runtime.code_structure import scan, enrich
from observer_runtime.behavior_model import capture

def write(name, value):
    (ROOT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

def build():
    code = sorted(p.relative_to(ROOT).as_posix() for folder in ("app", "bo_stategraph", "integrations") for p in (ROOT / folder).glob("*.py"))
    code += [name for name in ("server.py", "main.py") if (ROOT / name).exists()]
    watched = ["AGENTS.md", "ownership.json", "config/printers.json", "bo_stategraph/config/retention.json"]
    watched += sorted(p.relative_to(ROOT).as_posix() for folder in ("tooling", "tests", "static", "observer_runtime") for p in (ROOT / folder).rglob("*") if p.is_file() and "__pycache__" not in p.parts)
    watched += ["review/round-03/prepare.py"]
    inputs = {"printer_id": "string", "task_id": "string", "run_id": "string", "actor": "string", "approver": "string", "approval_id": "string", "dimensions": "string", "material": "string", "parameters": "string", "value": "string", "capability": "string", "clock": "number", "version": "number", "run_version": "number", "grant_version": "number", "expires": "number", "active": "boolean", "kind": "string"}
    flags = {k: "boolean" for k in ("eligible", "task_ok", "printer_ok", "version_ok", "other_actor", "role_ok", "active_ok", "time_ok")}
    grant_fields = {**flags, "id": "string", "version": "number", "expires": "number", "printer_id": "string", "task_id": "string", "approver": "string"}
    inputs["implementation"] = "string"
    outputs = {**grant_fields, "run_id": "string", "approval_id": "string", "state": "string", "passed": "boolean", "allowed": "boolean", "unchanged": "boolean", "duplicate": "boolean", "released": "boolean", "revoked": "boolean", "queue_seq": "number", "effect_id": "number", "clock": "number", "reason": "string", "size": "string", "material": "string", "activity_state": "string", "failures": ["string"], "error_type": "string", "error": "string", "candidates": [grant_fields]}
    specs = [
        ("submit", "action", "提交与版本", "bo_stategraph/workflow.py", "Workflow.submit", None, ["R03"]),
        ("parameter-change", "action", "参数变化建立新版本", "bo_stategraph/workflow.py", "Workflow.submit", "submit", ["R03"]),
        ("checks", "action", "并行检查与汇合", "bo_stategraph/workflow.py", "Workflow.run_checks", None, ["R02", "R08"]),
        ("check-size", "function", "检查三边尺寸", "app/checks.py", "check_size", "checks", ["R10"]),
        ("check-material", "function", "检查材料", "app/checks.py", "check_material", "checks", ["R10"]),
        ("check-worker", "function", "检查调用与异常边界", "bo_stategraph/workflow.py", "Workflow._check", "checks", ["R08"]),
        ("approval", "decision", "当前审批资格", "bo_stategraph/workflow.py", "Workflow._authorization", None, ["R01", "R05"]),
        ("grant-match", "decision", "逐份审批条件", "app/policy.py", "grant_matches", "approval", ["R01", "R03"]),
        ("approval-change", "action", "审批与权限变更", "bo_stategraph/workflow.py", "Workflow.approve", "approval", ["R01", "R05"]),
        ("queue", "wait", "队列与等待", "bo_stategraph/workflow.py", "Workflow.schedule", None, ["R04", "R05"]),
        ("printing", "effect", "占用打印机", "bo_stategraph/workflow.py", "Workflow.schedule", None, ["R07"]),
        ("printer", "data", "共享打印机资源", "app/store.py", "Store.snapshot", "printing", ["R07"]),
        ("cancel", "action", "取消选中运行", "bo_stategraph/workflow.py", "Workflow.cancel", "printing", ["R09"]),
        ("printer-stopped", "effect", "设备确认与释放", "bo_stategraph/workflow.py", "Workflow.confirm", "printing", ["R06"]),
        ("lifecycle", "function", "完整生命周期", "bo_stategraph/declaration.py", "definition", "queue", ["R11"]),
    ]
    nodes = [{"id": ident, "kind": kind, "label": label, "summary": label + "；函数身份来自源码，值只来自已采集调用，展开可查看参数和源代码。", "source": {"path": path, "symbol": symbol}, "capture": {"in": inputs, "out": outputs}, "requirements": reqs, **({"parent": parent} if parent else {})} for ident, kind, label, path, symbol, parent, reqs in specs]
    nodes += [{"id": "state." + value, "kind": "state", "layer": "state", "value": value, "label": label, "summary": "项目执行器声明的持久状态", "parent": "lifecycle", "capture": {"in": {}, "out": {}}} for value, label in LABELS.items()]
    relations = [("submit", "checks", "flow", "新运行"), ("checks", "queue", "guard", "两项通过"), ("approval", "queue", "guard", "任一有效审批"), ("queue", "printing", "flow", "最早有资格任务"), ("printer", "printing", "guard", "该机空闲，事务内占用"), ("cancel", "printer-stopped", "flow", "请求停止后等待确认"), ("printer-stopped", "queue", "flow", "释放后自动调度"), ("parameter-change", "checks", "flow", "新版本重新检查"), ("grant-match", "approval", "guard", "OR"), ("check-size", "checks", "guard", "ALL"), ("check-material", "checks", "guard", "ALL")]
    index = scan(ROOT, code)
    mapped = {(n["source"]["path"], n["source"]["symbol"]) for n in nodes if n.get("source")}
    for symbol in index["symbols"].values():
        if symbol["kind"] != "function" or (symbol["path"], symbol["symbol"]) in mapped:
            continue
        candidates = [n for n in nodes if n.get("source", {}).get("path") == symbol["path"] and symbol["symbol"].startswith(n["source"]["symbol"] + ".")]
        parent = max(candidates, key=lambda n: len(n["source"]["symbol"]))["id"] if candidates else "lifecycle"
        nodes.append({"id": "internal." + hashlib.sha256(symbol["id"].encode()).hexdigest()[:12], "kind": "function", "label": symbol["symbol"], "summary": "实际源码函数；静态身份可定位。是否执行及局部值仅以显式事件为依据。", "parent": parent, "source": {"path": symbol["path"], "symbol": symbol["symbol"]}, "capture": {"in": {}, "out": {}}, "analysis_detail": True})
    edges = [{"id": f"declared:{a}:{b}:{t}", "from": a, "to": b, "type": t, "label": label, "evidence": "authored business declaration; not an executed call"} for a, b, t, label in relations]
    edges += [{"id": "contains:" + n["id"], "from": n["parent"], "to": n["id"], "type": "contains", "label": "展开", "evidence": "authored hierarchy"} for n in nodes if n.get("parent")]
    roots = ["submit", "checks", "approval", "queue", "printing"]
    authored = {"schema_version": 3, "revision": "print-r1", "title": "工作室 · 3D 打印执行图", "intent": "intent.json", "source_files": sorted(set(code + watched)), "nodes": nodes, "edges": edges, "graph_roots": roots, "overview": [{"node": ident, "x": 160 + i * 240, "y": 200} for i, ident in enumerate(roots)], "scope": {"unknowns": ["静态调用不证明实际调用；外部库内部与动态回调未完整展开", "本地模拟设备，不解析模型文件，不验证真实打印效果", "共享资源由项目 bo_stategraph.validate_instances 检查；冻结 activity-graph/v1 的运行内资源检查不适用", "无多用户身份认证；本地操作者提供合成身份", "事件顺序不是因果证明；本版不构造推测的因果边"]}, "machine": definition(), "presentation": {"subject": "打印任务", "states": LABELS}, "project_execution": {"scope": "SQLite shared", "activities": ["size", "material"], "join": "all", "resource_capacity": 1, "release": "device confirmation"}}
    model = enrich(authored, index, 1)
    write("behavior.json", model)
    sync = json.loads((ROOT / "sync.json").read_text())
    sync.update(code_files=code, watch_files=watched, whitebox="whitebox.json", stategraph={"module": "bo_stategraph/__init__.py", "development_mode": "guided", "execution_mode": "drive", "decision_source": "skill-default", "decision": "普通 Python 项目执行器消费同一生命周期声明"}, probe_callees=["self._emit"], required_probes=[{"symbol": "bo_stategraph/workflow.py::Workflow.schedule", "node": "printing", "phase": "commit"}, {"symbol": "bo_stategraph/workflow.py::Workflow.confirm", "node": "printer-stopped", "phase": "commit"}, {"symbol": "bo_stategraph/workflow.py::Workflow.run_checks", "node": "checks", "phase": "decision"}], required_runtime_probes=[{"case": "happy", "node": "printing", "phase": "commit"}, {"case": "happy", "node": "printer-stopped", "phase": "commit"}, {"case": "check_error", "node": "check-worker", "phase": "error"}], test_commands=[["{python}", "-B", "-X", "utf8", "tests/test_project.py"]])
    sync["source_scope"]["exclude"]["observer_runtime/*"] = "冻结 Skill 通用运行库，文件及散列通过 watch_files 与 ownership 单独绑定；不作为本项目业务函数"
    sync["test_commands"].insert(0, ["{python}", "-B", "-X", "utf8", "tests/test_policy.py"])
    write("sync.json", sync)
    doc = json.loads((ROOT / "discovery.json").read_text())
    node_ids = {n["id"] for n in model["nodes"]}
    for network in doc["networks"]:
        for n in network["nodes"]:
            n["model_nodes"] = [n["id"]] if n["id"] in node_ids else []
    acceptance = json.loads((ROOT / "acceptance.json").read_text())
    associations = {"D01": "R01", "D02": "R07", "D03": "R03", "D04": "R02", "D05": "R04", "D06": "R05", "D07": "R06", "D08": "R09", "D09": "R10", "D10": "R07", "D11": "R08", "D12": "R01"}
    for d in doc["decisions"]:
        rid = associations[d["id"]]
        d["links"] = {"requirements": [rid], "model_nodes": list(dict.fromkeys(x for x in d["affects"] if x in node_ids)), "checks": [c["id"] for c in acceptance["checks"] if c["requirement"] == rid]}
    write("discovery.json", doc)
    if (ROOT / "ownership.json").exists():
        write("manifest.json", capture(ROOT, model))
    print(json.dumps({"nodes": len(model["nodes"]), "edges": len(model["edges"]), "source_files": len(code), "watched": len(watched)}))

if __name__ == "__main__":
    build()


