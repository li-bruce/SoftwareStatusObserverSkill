"""Reproduce this documentation-only round from its frozen round-01 record."""
import difflib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ROUND = ROOT / "review" / "round-02"
previous_text = (ROOT / "review/round-01/discovery.json").read_text(encoding="utf-8-sig")
doc = json.loads(previous_text)
answer = "审批权先按指定打印机，每份审批还要对应任务；不允许自己审批自己的任务。机器空闲后按入队先后自动开始，同一人可以提交多份任务。尺寸和材料希望同时检查，两项都通过才能用机器。参数变更后怎么办我还没想清，先别替我定。你可以先整理已经确定的部分，把剩下真正影响实现的问题问清楚。"
questions = [
    "是否由提交人指定一台打印机，尺寸、材料都通过且该任务获批后，才进入这台机器的队列？还是先入队，再等待检查和审批？",
    "排队期间审批被撤销或审批人失去该机审批权，任务应退出队列，还是保留位置等待重新审批？已经开始打印的任务是否继续？",
    "本轮先使用本地模拟打印机，还是需要连接真实设备？打印完成或取消时，是否收到设备的完成／停止确认后才释放机器？",
]
doc["sources"] += [
    {"id": "U02", "kind": "user", "text": answer, "locator": "2026-10-22 主会话发送的模拟需求方第二轮答复；非真人反馈"},
    {"id": "I02", "kind": "inference", "text": "打印机占用如何结束以及本轮是否接真实设备尚未明确；设备完成或停止确认仅是待询问的候选条件。", "locator": "本对话第二轮需求分析，非已确认规则"},
    {"id": "A02", "kind": "assistant", "text": "\n".join(f"{i + 1}. {q}" for i, q in enumerate(questions)), "locator": "review/round-02/dialogue.md；第二轮实际提问，与本轮最终消息一致"},
]
by_id = {d["id"]: d for d in doc["decisions"]}
for ident, result in [
    ("D01", "审批权按指定打印机；每份审批对应任务；审批人不能是任务提交人。"),
    ("D02", "机器空闲后按入队先后自动开始；同一人可提交多份任务。机器选择及入队时点尚未回答，由 D05 单独处理。"),
]:
    by_id[ident].update(status="resolved", resolution={"kind": "user_answer", "text": result, "source_refs": ["U02"]})
    by_id[ident]["source_refs"].append("U02")
by_id["D03"]["source_refs"].append("U02")
by_id["D03"]["note"] = "模拟需求方明确尚未想清且要求不代定；继续 open/blocking，本轮不重复提问，不实现依赖参数变更规则的行为。"
network = doc["networks"][0]
nodes = {n["id"]: n for n in network["nodes"]}
nodes["checks"].update(label="尺寸与材料并行检查，均通过", source_refs=["U01", "U02"])
nodes["approval"].update(label="任务与指定打印机审批，禁止自批", source_refs=["U01", "U02"])
nodes["queue"].update(label="入队先后顺序；自动放行", source_refs=["U01", "U02"])
network["nodes"] += [
    {"id": "check-size", "label": "尺寸检查", "kind": "action", "source_refs": ["U02"]},
    {"id": "check-material", "label": "材料检查", "kind": "action", "source_refs": ["U02"]},
    {"id": "printer-stopped", "label": "设备完成或停止确认：范围待定", "kind": "event", "source_refs": ["I02"]},
]
edges = {e["id"]: e for e in network["edges"]}
edges["e-checks-queue"].update(label="两项均通过后可用机器；入队时点待定", source_refs=["U01", "U02"], decision_refs=["D04", "D05"])
edges["e-approval-queue"].update(label="审批必须匹配任务与机器且非自批；何时入队待定", source_refs=["U02"], decision_refs=["D01", "D05"])
edges["e-queue-printing"].update(label="机器空闲后按入队先后自动开始", source_refs=["U02"], decision_refs=["D02"])
network["edges"] += [
    {"id": "e-submit-size", "from": "submit", "to": "check-size", "relation": "flow", "label": "并行分支：尺寸", "source_refs": ["U02"], "decision_refs": ["D04"]},
    {"id": "e-submit-material", "from": "submit", "to": "check-material", "relation": "flow", "label": "并行分支：材料", "source_refs": ["U02"], "decision_refs": ["D04"]},
    {"id": "e-size-join", "from": "check-size", "to": "checks", "relation": "join", "label": "尺寸通过为必要条件", "source_refs": ["U02"], "decision_refs": ["D04"]},
    {"id": "e-material-join", "from": "check-material", "to": "checks", "relation": "join", "label": "材料通过为必要条件", "source_refs": ["U02"], "decision_refs": ["D04"]},
    {"id": "e-stopped-release", "from": "printer-stopped", "to": "printer", "relation": "resource", "label": "何时归还资源待确认", "source_refs": ["I02"], "decision_refs": ["D07"]},
]
doc["decisions"].append({"id": "D04", "topic": "concurrency", "question": "尺寸与材料检查能否并行，使用机器是否必须等两项通过？", "why": "决定检查分支和汇合条件。", "affects": ["checks", "check-size", "check-material"], "blocking": True, "status": "resolved", "priority": 1, "source_refs": ["U02"], "resolution": {"kind": "user_answer", "text": "尺寸与材料同时检查；两项都通过才能使用机器。", "source_refs": ["U02"]}})
for ident, topic, question, why, affects in [
    ("D05", "resources", questions[0], "明确指定资源和 FIFO 的入队时间；不能将提交时间冒充已确认的入队时间。", ["submit", "checks", "approval", "queue", "printer"]),
    ("D06", "authority", questions[1], "权限变化会影响等待、队列位置和已在进行的打印，不能从初次审批推定永久许可。", ["approval", "queue", "printing"]),
    ("D07", "completion", questions[2], "决定本地模拟或外部设备的执行边界，以及何种实际效果可释放独占资源。", ["printing", "printer-stopped", "printer"]),
]:
    doc["decisions"].append({"id": ident, "topic": topic, "question": question, "why": why, "affects": affects, "blocking": True, "status": "open", "priority": 1, "source_refs": ["U01", "U02"], "asked_in": ["A02"]})
current_text = json.dumps(doc, ensure_ascii=False, indent=2) + "\n"
(ROOT / "discovery.json").write_text(current_text, encoding="utf-8")
(ROUND / "discovery.json").write_text(current_text, encoding="utf-8")
(ROUND / "discovery.diff").write_text("".join(difflib.unified_diff(previous_text.splitlines(True), current_text.splitlines(True), fromfile="round-01/discovery.json", tofile="round-02/discovery.json")), encoding="utf-8")
(ROUND / "decisions-before-after.json").write_text(json.dumps({"previous": json.loads(previous_text)["decisions"], "current": doc["decisions"]}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"resolved": [d["id"] for d in doc["decisions"] if d["status"] == "resolved"], "open": [d["id"] for d in doc["decisions"] if d["status"] == "open"], "business_source_changes": 0, "runtime_events": 0}, ensure_ascii=False))
