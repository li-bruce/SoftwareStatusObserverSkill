"""Authored expectations, independent of runtime output; initial implementation only."""
import json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]

def write(path, data):
    (ROOT / path).write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

def prepare():
    doc = json.loads((ROOT / "discovery.json").read_text())
    text = "取消只针对我选中的那一次运行，不影响同一任务的新旧其他运行。尺寸先用提交时填写的长、宽、高，单位毫米，不解析真实模型文件；必须是有限的正数，恰好等于机器上限允许，超过任一维度拒绝。先支持 PLA 和 ABS，两台模拟机的尺寸/材料能力用配置给出即可。审批有到期时间，取机器真正开始前的当前时间重新判断；测试可以用可控制的时钟。其他不改变这些规则的实现细节你自行决定，继续完成可运行版本。"
    if not any(s["id"] == "U04" for s in doc["sources"]):
        doc["sources"].append({"id": "U04", "kind": "user", "text": text, "locator": "主会话在实现期间发送的模拟需求方补充；非真人测试"})
        for d in doc["decisions"]:
            if d["id"] in ("D08", "D09"):
                d.update(status="resolved", resolution={"kind": "user_answer", "text": "仅取消选中的那一次运行，不影响其他运行。" if d["id"] == "D08" else "填写三边毫米尺寸，有限正数，逐轴不超过配置上限，等于允许；不解析模型文件。PLA/ABS 按机器配置检查。", "source_refs": ["U04"]})
                d["source_refs"].append("U04")
        doc["decisions"].append({"id": "D12", "topic": "authority", "question": "审批何时到期，何时取时间？", "why": "打印占用前必须使用当前时间。", "affects": ["approval", "printing", "queue"], "blocking": True, "status": "resolved", "source_refs": ["U04"], "resolution": {"kind": "user_answer", "text": "审批有到期时间，开始打印前取当前时间重验；now < expires 有效，达到到期时刻即失效。测试使用可控时钟。", "source_refs": ["U04"]}})
    write("discovery.json", doc)
    intent = json.loads((ROOT / "intent.json").read_text())
    for r in intent["requirements"]:
        if r["id"] in ("R09", "R10"):
            d = next(d for d in doc["decisions"] if d["id"] == ("D08" if r["id"] == "R09" else "D09"))
            r.update(status="confirmed", text=d["resolution"]["text"], source="discovery.json:U04")
        if r["id"] == "R01":
            r["text"] += " 审批人仍有该机权限、未撤销且开始前当前时间早于到期时刻。"
    write("intent.json", intent)
    expected = {
        "policy": ("R01", {"matching": True, "self_approval": False, "old_version": False, "wrong_task": False, "wrong_printer": False, "missing_role": False, "expired": False, "revoked": False}),
        "happy": ("R04", {"waiting": "queued", "resumed": "printing", "finished": "completed", "released": True, "duplicate_no_effect": True, "same_submitter_two_runs": 2}),
        "approval_paths": ("R05", {"alternative": "queued", "blocked": "blocked", "bypass": True, "restored_position": True, "original_priority": True, "printing_survives_revoke": "printing"}),
        "expiry": ("R01", {"at_deadline": "blocked", "no_start": True, "new_approval_resumes": "printing"}),
        "expiry_window": ("R01", {"state": "blocked", "owner_empty": True}),
        "version_waiting": ("R03", {"old": "superseded", "new_before_approval": "awaiting_approval", "old_approval_not_reused": True, "new_after_approval": "printing", "new_version": 2}),
        "version_printing": ("R06", {"old_kept": "printing", "waits_for_stop": True, "old_cancelled": "cancelled", "new_unaffected": "printing", "new_owns": True}),
        "cancel_other_run": ("R09", {"new_cancelled": "cancelled", "old_unaffected": "printing", "old_owns": True}),
        "size_boundaries": ("R10", {"states": ["awaiting_approval"] + ["check_failed"] * 8, "specific_failures": True, "no_occupancy": True}),
        "materials": ("R10", {"states": ["check_failed", "awaiting_approval", "check_failed"]}),
        "check_error": ("R08", {"state": "check_error", "error_type": "RuntimeError", "message": "simulated material checker failure", "owner_empty": True}),
        "parallel": ("R02", {"state": "awaiting_approval", "overlap": True}),
        "concurrent_dispatch": ("R07", {"printing_count": 1, "start_effects": 1, "waiting_count": 1}),
        "two_printers": ("R07", {"printing_count": 2, "distinct_owners": 2}),
        "restart": ("R06", {"ownership_persisted": True, "next_started": "printing"}),
        "api_rejections": ("R01", {"rejected": ["alice", "unknown", "unrequested_stop"], "still_printing": "printing"}),
    }
    checks = [{"id": "approval-match", "requirement": "R01", "case": "policy", "path": ["matching"], "equals": True}, {"id": "approval-self-denied", "requirement": "R01", "case": "policy", "path": ["self_approval"], "equals": False}, {"id": "approval-old-version-denied", "requirement": "R03", "case": "policy", "path": ["old_version"], "equals": False}]
    for case, (rid, fields) in expected.items():
        checks += [{"id": case + ":" + key, "requirement": rid, "case": case, "path": [key], "equals": value} for key, value in fields.items()]
        checks.append({"id": case + ":state_constraints", "requirement": "R11", "case": case, "path": ["state_constraints"], "equals": True})
    write("acceptance.json", {"checks": checks, "model_checks": []})
    white_rules, white_checks = [], []
    for ident, rid, node, path, symbol, params, case, phase, select, fields in [
        ("grant-version", "R03", "grant-match", "app/policy.py", "grant_matches", {"grant": "dict", "run": "dict", "has_role": "bool", "now": "float"}, "happy", "decision", [], [{"path": ["inputs", "grant_version"], "compare": {"path": ["inputs", "run_version"], "op": "eq"}}, {"path": ["outputs", "eligible"], "equals": True}]),
        ("expiry-check", "R01", "approval", "bo_stategraph/workflow.py", "Workflow._authorization", {"run": "dict", "now": "float"}, "expiry_window", "decision", [{"path": ["inputs", "clock"], "equals": 110.0}], [{"path": ["outputs", "allowed"], "equals": False}]),
        ("parallel-result", "R02", "check-size", "app/checks.py", "check_size", {"dimensions": "list", "limits": "list"}, "happy", "return", [], [{"path": ["outputs", "passed"], "equals": True}, {"path": ["inputs", "value"], "equals": "[20, 20, 20]"}]),
        ("error-visible", "R08", "check-worker", "bo_stategraph/workflow.py", "Workflow._check", {"run_id": "str", "name": "str"}, "check_error", "error", [], [{"path": ["outputs", "error_type"], "equals": "RuntimeError"}]),
        ("cancel-waits", "R09", "cancel", "bo_stategraph/workflow.py", "Workflow.cancel", {"run_id": "str"}, "version_printing", "commit", [], [{"path": ["outputs", "state"], "equals": "stopping"}]),
        ("confirmation-release", "R06", "printer-stopped", "bo_stategraph/workflow.py", "Workflow.confirm", {"run_id": "str", "kind": "str"}, "version_printing", "commit", [], [{"path": ["outputs", "released"], "equals": True}]),
    ]:
        white_rules.append({"id": ident, "requirement": rid, "node": node, "source": {"path": path, "symbol": symbol}, "parameters": params, "category": "actual-values", "claim": ident, "basis": "intent.json:" + rid})
        white_checks.append({"id": ident, "rule": ident, "case": case, "phase": phase, "count": {"min": 1}, "select": select, "fields": fields})
    write("whitebox.json", {"schema_version": 1, "rules": white_rules, "checks": white_checks})
    write("ownership.json", {"schema_version": 1, "scan": ["app", "bo_stategraph", "integrations", "observer_runtime", "tooling", "tests", "static", "server.py", "main.py"], "layers": {"entry": {"paths": ["server.py", "main.py"], "allows": ["entry", "integration"]}, "core": {"paths": ["app", "bo_stategraph"], "allows": ["core"], "reject_dynamic": True}, "integration": {"paths": ["integrations"], "allows": ["core", "observer", "integration"]}, "observer": {"paths": ["observer_runtime"], "allows": ["observer", "core"]}, "tooling": {"paths": ["tooling", "tests"], "allows": ["core", "integration", "observer", "tooling"]}, "viewer": {"paths": ["static"], "allows": ["viewer"]}}, "managed_paths": [], "managed_hashes": {}, "regenerations": [], "core_layers": ["core"], "core_resources": ["config/printers.json"], "core_include": ["app", "bo_stategraph", "config/printers.json"]})

if __name__ == "__main__":
    prepare()

