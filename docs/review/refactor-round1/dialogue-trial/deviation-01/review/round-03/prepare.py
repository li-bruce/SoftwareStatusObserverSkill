"""Prepare the recorded first implementation change; never replaces a baseline."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
doc = json.loads((ROOT / "discovery.json").read_text(encoding="utf-8-sig"))
answer = "提交时指定打印机；两项检查和审批都通过后才入这台机器的队列。排队时撤销一份审批或审批人失去该机权限，都重新判断：还有另一份有效审批就继续；没有就保留队列位置等待，恢复后自动继续。有资格的后续任务可以越过暂时没有资格的任务，仍按各自原来的入队时间排序。已经打印的继续完成，不因为审批改变停止。参数改动我决定了：尺寸、材料、打印参数任一变化都生成新版本，旧检查和旧审批不用于新版本；未开始打印的旧版本作废，新版本重新检查审批；已在打印的旧版本继续完成，新版本是另一份运行，别混在一起。只做本地模拟设备。取消已开始的打印要等待模拟设备停止确认，收到确认才释放机器；正常完成同样按完成确认释放。每台机器一次只打印一个任务，先放两台机器供测试。尺寸和材料检查失败要能看见具体失败项；检查函数异常也不能吞掉。请据此实现可运行版本，并用这个 Skill 做完整的代码映射、埋点、状态网和验收。使用普通 Python、SQLite 即可；框架你决定。让我能从图看到一次真实任务怎样等待、恢复、占用和释放打印机。"
questions = [
    "同一任务的旧版本正在打印、新版本正在检查或排队时，取消应只作用于选中的那次运行，还是同时取消该任务所有未完成运行？",
    "本轮是否采用提交时提供的三边尺寸（毫米），逐轴与打印机上限比较、等于上限允许，材料按机器支持列表检查？还是需要从 STL／3MF 文件解析尺寸？",
]
doc["sources"] += [
    {"id": "U03", "kind": "user", "text": answer, "locator": "2026-10-22 主会话模拟需求方第三轮答复；非真人测试"},
    {"id": "A03", "kind": "assistant", "text": "\n".join(questions), "locator": "review/round-03/dialogue.md；第三轮实际提问"},
    {"id": "I03", "kind": "inference", "text": "取消作用于哪几次运行、尺寸数据来源与边界比较尚未被用户明确指定，不能因为实现框架授权而代定。", "locator": "第三轮开发前语义核对"},
]
resolved = {
    "D03": "尺寸、材料或打印参数任一变化均新建版本；新版本不复用旧检查和旧审批。未开始打印的旧版本作废；正在打印的旧版本继续完成，新版本另建运行，不混用状态与证据。",
    "D05": "提交时指定打印机；两项检查及审批都通过后才进入指定机器队列。",
    "D06": "撤销审批或撤销审批人对该机的权限后重新判断全部可用审批；任一有效则继续，否则保留队列位置等待。恢复后自动继续，后续有资格任务可越过暂时无资格任务，按原入队顺序选择。打印已开始后不因审批变化停止。",
    "D07": "仅本地模拟设备；取消已开始的打印须等待设备停止确认，正常完成须等待设备完成确认；收到确认才释放机器。取消所涵盖的运行范围由 D08 待定。",
}
for d in doc["decisions"]:
    if d["id"] in resolved:
        d.update(status="resolved", resolution={"kind": "user_answer", "text": resolved[d["id"]], "source_refs": ["U03"]})
        d["source_refs"].append("U03")
        d.pop("note", None)
net = doc["networks"][0]
nodes = {n["id"]: n for n in net["nodes"]}
nodes["queue"].update(label="保留入队位置；选最早有资格任务", source_refs=["U02", "U03"])
nodes["parameter-change"].update(label="参数改动建立新版本和独立运行", source_refs=["U03"])
nodes["printer-stopped"].update(label="模拟设备完成／停止确认", source_refs=["U03"])
nodes["printer"].update(label="两台独立打印机，每台容量 1", source_refs=["U03"])
for e in net["edges"]:
    mapping = {
        "e-checks-queue": "两项通过且获批后入队",
        "e-approval-queue": "匹配任务、机器、版本且非自批；至少一份有效",
        "e-queue-printing": "机器空闲时自动选择原入队时间最早的有资格任务",
        "e-change-checks": "新版本重新做两项检查，不复用旧结果",
        "e-change-approval": "新版本重新审批，旧审批不用于新版本",
        "e-change-printing": "未打印旧版本作废；正在打印旧版本继续，新版本另建运行",
        "e-stopped-release": "设备完成／停止确认后释放实际占用",
    }
    if e["id"] in mapping:
        e.update(label=mapping[e["id"]], source_refs=["U03"])
for ident, topic, question, affects, why in [
    ("D08", "cancellation", questions[0], ["printing", "parameter-change", "printer-stopped"], "新旧运行可并存；取消一个运行和取消整项任务产生不同业务效果。"),
    ("D09", "parameters", questions[1], ["submit", "check-size", "check-material"], "实际校验的输入来源、单位与边界不同会改变检查结果及实现范围。"),
]:
    doc["decisions"].append({"id": ident, "topic": topic, "question": question, "why": why, "affects": affects, "blocking": True, "status": "open", "priority": 1, "source_refs": ["U01", "U03", "I03"], "asked_in": ["A03"]})
for ident, topic, result, affects in [
    ("D10", "resources", "两台本地模拟打印机，每台同时最多打印一个任务。", ["printer", "printing"]),
    ("D11", "completion", "尺寸和材料失败项分别可见；函数异常必须显式显示，不能当作通过或吞掉。", ["check-size", "check-material", "checks"]),
]:
    doc["decisions"].append({"id": ident, "topic": topic, "question": result, "why": "来自第三轮直接补充的业务约束。", "affects": affects, "blocking": True, "status": "resolved", "priority": 1, "source_refs": ["U03"], "resolution": {"kind": "user_answer", "text": result, "source_refs": ["U03"]}})

def write(name, value):
    path = ROOT / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

write("discovery.json", doc)
write("review/round-03/discovery.json", doc)
requirements = [
    ("R01", "D01", "匹配任务及指定打印机且非提交人自批的有效审批，至少一份可使授权成立。"),
    ("R02", "D04", "尺寸与材料并行检查并汇合，两项都通过才能用机器；具体校验输入等 D09。"),
    ("R03", "D03", resolved["D03"]),
    ("R04", "D05", resolved["D05"]),
    ("R05", "D06", resolved["D06"]),
    ("R06", "D07", resolved["D07"]),
    ("R07", "D10", "两台本地模拟打印机，各有一个共享容量；同一人可多次提交。"),
    ("R08", "D11", "检查失败分别可见；检查异常保留明确错误。"),
    ("R09", "D08", questions[0]),
    ("R10", "D09", questions[1]),
    ("R11", None, "只读图显示真实函数、实际参数、等待恢复路线和资源效果；采集关闭或失败不改变业务。"),
]
write("intent.json", {"intent_id": "studio-print-trial", "revision": "round-03", "goal": doc["goal"], "requirements": [{"id": rid, "text": text, "status": "pending" if rid in ("R09", "R10") else "confirmed", "source": "discovery.json:" + (did or "U01") } for rid, did, text in requirements], "exclusions": ["真实设备", "真人可用性证据", "未验证的任意并发调度", "图操作执行业务命令"]})
write("acceptance.json", {"checks": [{"id": "approval-match", "requirement": "R01", "case": "policy", "path": ["matching"], "equals": True}, {"id": "approval-self-denied", "requirement": "R01", "case": "policy", "path": ["self_approval"], "equals": False}, {"id": "approval-old-version-denied", "requirement": "R03", "case": "policy", "path": ["old_version"], "equals": False}], "model_checks": []})
write("behavior.json", {"schema_version": 3, "revision": "round-03-initial", "title": "工作室 3D 打印任务", "intent": "intent.json", "source_files": ["app/policy.py"], "nodes": [{"id": "approval", "kind": "data", "label": "审批规则待绑定实现", "summary": "初始变更基线，尚无运行证据。", "capture": {"in": {}, "out": {}}}], "edges": [], "overview": [{"node": "approval", "x": 30, "y": 30}], "scope": {"unknowns": ["尚未实现完整执行器、探针、状态网和页面", "D08、D09 尚未回答"]}})
write("sync.json", {"model": "behavior.json", "manifest": "manifest.json", "code_files": ["app/policy.py"], "watch_files": ["tooling/gate.py", "AGENTS.md", "review/round-03/prepare.py"], "acceptance": "acceptance.json", "discovery": "discovery.json", "slice_depth": 1, "probe_callees": ["events.bo_emit"], "probe_modes": ["on", "off", "fault"], "require_mapping_witnesses": True, "source_scope": {"roots": ["."], "exclude": {"review/*": "轮次记录与文档重现脚本，非业务实现", "tooling/*": "开发检查入口，作为 watch_files 单独绑定", "tests/*": "独立测试，作为 watch_files 单独绑定"}, "require_symbol_classification": True}, "observations_command": ["{python}", "-B", "-X", "utf8", "tooling/observe.py"], "test_commands": [["{python}", "-B", "-X", "utf8", "tests/test_policy.py"]], "timeout_seconds": 120})
(ROOT / "app").mkdir(exist_ok=True)
(ROOT / "app/policy.py").write_text('"""Approval rules: initial empty implementation baseline."""\n', encoding="utf-8")
print("Prepared documentation and an empty source baseline; not implemented.")
