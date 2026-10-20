"""One-time pre-implementation record. Does not import the application."""
import json
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).absolute().parents[2]
SKILL = ROOT.parent / "skill-candidate-3" / "business-observer"


def read(name):
    return json.loads((ROOT / name).read_text(encoding="utf-8-sig"))


def write(name, value):
    path = ROOT / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


answer = """内容里不能出现 SECRET: 这个标记；索引检查要求标题、项目和资料编号齐全。任一项失败就不能归档，修好以后新开一次运行，不拼用不同运行的结果。新运行先有有效审批才开始检查；如果只有一个名额，第一项做着时审批失效，第二项先等着，我点“继续”且资格恢复后才开始。你说的旧运行收尾方式符合我的意思：未开始的作废，已开始的自然结束，记录都在且不能提交。我还需要一个“取消本次运行”，不删资料，已经开始的检查实际结束后再归还名额。目录归属变化也要按当前关系判断，提交时确保当时的权限和内容版本仍符合要求。"""
preference = """梳理图时需要我回答业务问题；之后按你选择的开发方案实现，图、状态机、探针和检查由你自行维护。我只想每轮结束查看变化后的图、展开检索、读关键参数和源码，不想手动操作同步命令或填写内部记录。"""
(ROOT / "review/round-04/dialogue.md").write_text(
    "# 第四轮：模拟用户演练\n\n## 实际业务答复 U04\n\n" + answer +
    "\n\n## 实际使用偏好 U04P\n\n" + preference +
    "\n\n## 使用范围\n\n采用用户正式提供的只读 skill-candidate-3，保留此前快照和失败。"
    "容量作为新建运行的参数；首版不添加未要求的运行中容量修改入口。"
    "这项范围选择来自实现方案授权，不冒充用户逐项确认。取消仅针对明确选择的本次运行。"
    "\n\n本轮开始集中实现，以下验收预期先于业务代码建立。\n", encoding="utf-8")

intent = read("intent.json")
replacements = {
    "R03": "任一审批目标四字段匹配、审核员非操作人、未撤销且 now < deadline 即有效；撤销重评，无有效审批等待。",
    "R04": "内容不得包含 SECRET:；索引要求标题、项目、资料编号齐全。两项都通过才可提交，失败后新建运行，不拼用不同运行结果。",
    "R05": "每次运行独享名额，创建时选择 1 或 2，默认 2；两项检查各占 1，实际结束后归还。",
    "R06": "内容改版后旧运行禁止提交；未开始检查作废，已开始检查自然结束；保留全部运行，新版本独立启动且不复用旧审批或旧结果。",
    "R11": "新运行须具备当前资格才启动检查；失去审批后已启动的自然结束，尚未启动的等待；点击继续并重查资格后再开始或提交。",
}
for r in intent["requirements"]:
    if r["id"] in replacements:
        r["text"] = replacements[r["id"]]
        r["source_refs"] = sorted(set(r["source_refs"] + ["U04"]))
    r["source"] = "模拟用户演练：" + ",".join(r["source_refs"])
    r["status"] = "confirmed"
intent["requirements"] += [
    {"id":"R12","text":"取消本次运行：停止启动未开始的检查，已启动检查实际结束后归还名额，不提交、不删除资料，也不影响其他运行。","status":"confirmed","source":"模拟用户 U04","source_refs":["U04"]},
    {"id":"R13","text":"目录归属变化按当前直接关系判断；提交事务重新验证权限、审批有效期、内容版本和同运行检查结果。","status":"confirmed","source":"模拟用户 U04","source_refs":["U04"]},
]
intent["status"] = "implementation"
write("intent.json", intent)

accept = read("acceptance.json")
accept["status"] = "planned_not_run"
accept["basis"] = "模拟用户 U01–U04；在实现前定义期望，观察程序不读取本文件。"
cases = [
    ("approval-expiry-boundary","R03","approval_at_deadline",["candidate_allowed"],False),
    ("approval-self-denied","R03","approval_self",["candidate_allowed"],False),
    ("approval-role-denied","R03","approval_not_reviewer",["candidate_allowed"],False),
    ("approval-alternative","R03","revoke_with_alternative",["completed"],True),
    ("approval-missing-waits","R03","no_approval",["phase"],"waiting"),
    ("checks-secret-rejected","R04","secret_content",["archive_count"],0),
    ("checks-index-rejected","R04","missing_index",["archive_count"],0),
    ("one-slot-max","R05","capacity_one",["max_running"],1),
    ("one-slot-wait","R05","capacity_one",["resource_wait_observed"],True),
    ("two-slots-overlap","R05","capacity_two",["max_running"],2),
    ("incomplete-cannot-commit","R04","join_pending",["before_completion_archives"],0),
    ("approval-loss-no-commit","R11","loss_and_resume",["before_resume_archives"],0),
    ("approval-loss-pending-stays","R11","loss_and_resume",["pending_did_not_start"],True),
    ("approval-manual-resume","R11","loss_and_resume",["completed"],True),
    ("old-run-cannot-commit","R06","edit_overlap",["old_archive_count"],0),
    ("old-new-coexist","R06","edit_overlap",["old_new_visible_while_running"],True),
    ("new-run-own-checks","R06","edit_overlap",["new_completed"],True),
    ("cancel-held-until-end","R12","cancel_running",["held_after_request"],1),
    ("cancel-releases-at-end","R12","cancel_running",["available_after_end"],1),
    ("cancel-does-not-commit","R12","cancel_running",["archive_count"],0),
    ("cancel-only-selected-run","R12","cancel_one_of_two",["other_completed"],True),
    ("cancel-preserves-document","R12","cancel_running",["source_document_exists"],True),
    ("move-denies-at-commit","R13","move_before_commit",["archive_count"],0),
    ("expiry-denies-at-commit","R13","expire_before_commit",["archive_count"],0),
    ("version-denies-at-commit","R13","edit_before_commit",["archive_count"],0),
    ("same-version-concurrent-once","R09","concurrent_same_version",["archive_count"],1),
    ("restart-preserves-history","R06","restart_interrupted",["phase"],"interrupted"),
]
accept["checks"] += [dict(id=i,requirement=r,case=c,path=p,equals=e) for i,r,c,p,e in cases]
write("acceptance.json", accept)

discovery = read("discovery.json")
discovery["sources"] += [
    {"id":"U04","kind":"user","text":answer,"locator":"review/round-04/dialogue.md；模拟用户实际回答"},
    {"id":"U04P","kind":"user","text":preference,"locator":"review/round-04/dialogue.md；模拟使用偏好"},
]
resolutions = {
    "D06": ("改版时未开始检查作废、已开始自然结束，旧运行可查但不可提交；新运行独立。",["R06"],["content_changed","run_identity"],["old-run-cannot-commit","old-new-coexist","new-run-own-checks"]),
    "D07": ("内容禁用 SECRET:；索引要求标题、项目、编号齐全。失败后新运行，不混用结果。",["R04"],["content_check","index_check"],["checks-secret-rejected","checks-index-rejected","incomplete-cannot-commit"]),
    "D08": ("新运行有有效审批才检查；途中失效后未启动检查等待手动继续且资格恢复。",["R11"],["resume_run","approval_check"],["approval-loss-no-commit","approval-loss-pending-stays","approval-manual-resume"]),
    "D09": ("首版在创建每次运行时选择 1 或 2 名额，固定为本次运行参数。未要求的运行中修改容量不纳入首版。",["R05"],["processing_slots"],["one-slot-max","two-slots-overlap"]),
}
for d in discovery["decisions"]:
    if d["id"] in resolutions:
        text,req,nodes,checks = resolutions[d["id"]]
        d["status"]="resolved"
        d["resolution"]={"kind":"user_answer","text":text,"source_refs":["U04"]}
        if d["id"]=="D09":
            d["resolution"]={"kind":"delegated_choice","text":text,"source_refs":["U03","U04P"],
                "rationale":"按每次运行单独设置的已定范围，将容量作为创建参数；用户授权选择实现方案，首版不扩充运行中修改入口。该选择已在本轮进度明示。"}
        d["links"]={"requirements":req,"model_nodes":nodes,"checks":checks}
write("discovery.json", discovery)

for folder in ["archive_app","integrations","tooling","observer_runtime"]:
    (ROOT/folder).mkdir(exist_ok=True)
    (ROOT/folder/"__init__.py").write_text('"""Project package."""\n',encoding="utf-8")
for path in SKILL.joinpath("scripts").glob("*.py"):
    shutil.copy2(path,ROOT/"observer_runtime"/path.name)
shutil.copy2(SKILL/"LICENSE.txt",ROOT/"observer_runtime"/"LICENSE.txt")
write("observer_runtime/origin.json",{"source":"skill-candidate-3","version":"0.4.0-candidate.3","manifest":"../skill-candidate-3/skill-manifest.json"})

codefiles = ["archive_app/ports.py","archive_app/policy.py","archive_app/workflow.py","archive_app/storage.py","archive_app/service.py","integrations/bo_observer.py"]
for name in codefiles + ["tooling/build_model.py","tooling/observe.py","tooling/tests.py"]:
    (ROOT/name).write_text('"""Pre-implementation placeholder; no business behavior yet."""\n',encoding="utf-8")
rules = [
("scope","R02","scope_check","archive_app/policy.py","is_direct_manager",{"project_id":"str","operator_id":"str","folder_id":"str","assignments":"list[dict]"},"bool","直接负责匹配"),
("candidate","R03","approval_candidate","archive_app/policy.py","candidate_allowed",{"grant":"dict","request":"dict","now":"float","reviewers":"list[str]"},"dict","审批目标、角色、排除本人、撤销和严格有效期"),
("content","R04","content_check","archive_app/policy.py","check_content",{"content":"str"},"dict","禁止 SECRET: 标记"),
("index","R04","index_check","archive_app/policy.py","check_index",{"title":"str","project_id":"str","document_number":"str"},"dict","三个索引字段齐全"),
("commit","R13","archive_commit","archive_app/service.py","ArchiveService.try_commit",{"db":"sqlite3.Connection","run":"dict","trace":"TracePort"},"str | None","当前资格、版本和本运行汇合后提交"),
]
whitebox={"schema_version":1,"rules":[],"checks":[]}
for ident,req,node,path,symbol,params,returns,claim in rules:
    whitebox["rules"].append(dict(id=ident,requirement=req,node=node,source={"path":path,"symbol":symbol},parameters=params,returns=returns,claim=claim,basis="模拟用户 U02–U04",category="parameter-and-decision"))
for ident,rule,case,phase,path,value in [
("scope-actual-true","scope","scope_direct_manager","decision",["outputs","allowed"],True),
("scope-actual-false","scope","scope_ancestor_only","decision",["outputs","allowed"],False),
("candidate-target-version","candidate","approval_target_other_version","decision",["outputs","version_ok"],False),
("candidate-expiry","candidate","approval_at_deadline","decision",["outputs","time_ok"],False),
("candidate-self","candidate","approval_self","decision",["outputs","different_actor"],False),
("content-secret","content","secret_content","return",["outputs","passed"],False),
("index-missing","index","missing_index","return",["outputs","passed"],False),
("commit-actual-version","commit","archive_snapshot","commit",["inputs","content_version"],1),
]:
    whitebox["checks"].append(dict(id=ident,rule=rule,case=case,phase=phase,count={"min":1},fields=[{"path":path,"equals":value}]))
write("whitebox.json",whitebox)
runtime_files = ["observer_runtime/"+p.name for p in (ROOT/"observer_runtime").glob("*.py")]
sync={"model":"behavior.json","manifest":"manifest.json","code_files":codefiles,
      "watch_files":["tooling/build_model.py","tooling/observe.py","tooling/tests.py","ownership.json",*runtime_files],
      "acceptance":"acceptance.json","discovery":"discovery.json","whitebox":"whitebox.json",
      "slice_depth":1,"probe_callees":["trace.record"],
      "required_probes":[{"node":"scope_check","phase":"decision"},{"node":"approval_candidate","phase":"decision"},{"node":"archive_commit","phase":"commit"}],
      "required_runtime_probes":[{"case":"archive_snapshot","node":"archive_commit","phase":"commit"},{"case":"secret_content","node":"content_check","phase":"return"}],
      "probe_modes":["on","off","fault"],
      "required_execution_cases":["capacity_one","capacity_two","edit_overlap","cancel_running","loss_and_resume","join_pending"],
      "observations_command":[sys.executable,"-X","utf8","-B","tooling/observe.py"],
      "test_commands":[[sys.executable,"-X","utf8","-B","tooling/tests.py"]],
      "timeout_seconds":120}
write("sync.json",sync)
write("ownership.json",{"schema_version":1,"scan":["archive_app","integrations","observer_runtime","tooling"],
 "layers":{"business":{"paths":["archive_app"],"allows":["business"],"reject_dynamic":True},
           "integration":{"paths":["integrations"],"allows":["business","observer","integration"]},
           "observer":{"paths":["observer_runtime"],"allows":["observer"]},
           "tooling":{"paths":["tooling"],"allows":["business","integration","observer","tooling"]}},
 "managed_paths":["observer_runtime"],"managed_hashes":{},"regenerations":[],
 "core_layers":["business"],"core_resources":["requirements.txt"],"core_include":["archive_app","requirements.txt"]})
import importlib.metadata
(ROOT/"requirements.txt").write_text("transitions=="+importlib.metadata.version("transitions")+"\n",encoding="utf-8")
for name in ["intent.json","discovery.json","acceptance.json","whitebox.json","sync.json"]:
    shutil.copy2(ROOT/name,ROOT/"review/round-04"/("before-code-"+name))
print(json.dumps({"stage":"planned_before_implementation","requirements":len(intent["requirements"]),"checks":len(accept["checks"]),"whitebox_rules":len(rules)}))
