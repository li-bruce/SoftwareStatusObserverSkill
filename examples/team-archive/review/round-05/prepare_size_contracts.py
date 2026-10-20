"""Independent v2 expectations recorded before implementing the new size rule."""
import json
from pathlib import Path
import shutil

ROOT=Path(__file__).absolute().parents[2]
HERE=Path(__file__).absolute().parent
U05="这版先保留。现在想加一个可以调整的归档大小上限，默认 8 KiB。资料正在检查时，如果我把上限调小，最终提交也要按新上限判断，不能拿之前通过的检查绕过去。条件恢复以后还是由我点“继续”。图里要能看出这份内容多大、当前上限是多少、为什么还在等。开发方案你按项目现有的来，图和检查你自己同步。我只想在这一轮完成后看到改了哪些节点和关键参数。"
A05="1. 归档大小上限是每个项目共用一份配置，还是只作用于当前资料？本地演练中仍由操作台直接调整。\n2. 大小是否按正文的 UTF-8 字节数计算，8 KiB = 8192 字节，恰好等于上限时允许归档？\n3. 运行中调小上限导致超限时，是否沿用审批失效的处理：已启动检查自然结束，未启动的等待，禁止提交；上限调大后由你点“继续”，复用同版本已通过的检查？"
U06="每个项目共用一个上限。只算正文的 UTF-8 字节数，8 KiB 就是 8192 字节，等于上限可以归档。设置上限时必须是正整数；小数、零、负数都提示错误，别替我取整。\n\n超限就按你说的等待方式：已经启动的检查做完，没启动的先等，禁止提交。把上限调大以后，我点‘继续’，同一版本已经通过的检查可以继续用。上限变化本身不改内容版本，也不让原本仍有效的审批自动作废；但继续和提交时都要按当时的上限重新判断。已经归档的快照保持不变。\n\n图里保留我第一版拖好的位置和标注，只把新增的大小条件和参数补进去。"


def read(name):
    return json.loads((ROOT/name).read_text(encoding="utf-8"))


def write(name,value):
    (ROOT/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+"\n",encoding="utf-8",newline="\n")


intent=read("intent.json")
assert not any(r["id"]=="R14" for r in intent["requirements"])
for rid,text in [
    ("R14","每个项目共用归档正文大小上限，默认 8192 字节；仅按 UTF-8 正文计量，等于上限允许。设置值必须为正整数，拒绝小数、零、负数且不取整。"),
    ("R15","开始/继续/提交按当前项目上限判断。超限时已启动检查自然结束、未启动等待、禁止提交；调大后须手动继续，复用同版本已通过检查。上限变化不改内容版本、不自动撤销审批，不改已有快照。"),
    ("R16","同一开发者图显示正文实际字节数、读取的上限/修订号及超限原因；保留首版坐标、标注和稳定节点 ID，提供可比较的首版/当前图及对应加载源码。")]:
    intent["requirements"].append({"id":rid,"text":text,"status":"confirmed","source":"模拟用户 U05-U06","source_refs":["U05","U06"]})
write("intent.json",intent)
discovery=read("discovery.json")
for ident,kind,text in [("U05","user",U05),("A05","assistant",A05),("U06","user",U06)]:
    discovery["sources"].append({"id":ident,"kind":kind,"text":text,
        "locator":"review/round-05/dialogue.md；实际模拟对话，不是真人试用"})
network=discovery["networks"][0]
for ident,label,kind in [("project_limit","项目当前大小上限","data"),("size_guard","正文大小是否符合当前上限","condition"),
                         ("set_size_limit","调整项目上限","action")]:
    network["nodes"].append({"id":ident,"label":label,"kind":kind,"source_refs":["U05","U06"],"model_nodes":[ident]})
for ident,topic,question,affects,req,checks in [
    ("D10","parameters","上限的作用范围和设置值是什么？",["project_limit","set_size_limit"],"R14",["size-default","size-project-isolation","size-invalid-inputs"]),
    ("D11","parameters","如何计量正文，恰好等于上限是否允许？",["size_guard"],"R14",["size-equality","size-utf8-over"]),
    ("D12","retry","运行中收紧及恢复时，检查结果和版本/审批如何处理？",["size_guard"],"R15",["size-running-wait","size-manual-resume","size-commit-fresh","size-snapshot-stable"]),
    ("D13","presentation","下一版如何保留第一版图的位置和标注？",["size_guard"],"R16",["size-model-stable-project"])]:
    discovery["decisions"].append({"id":ident,"topic":topic,"blocking":True,"status":"resolved","priority":1,
        "source_refs":["U05","U06"],"affects":affects,"question":question,
        "why":"该选择影响当前大小条件、恢复语义或新旧图身份。","asked_in":["A05"] if ident!="D13" else [],
        "resolution":{"kind":"user_answer","text":U06,"source_refs":["U06"]},
        "links":{"requirements":[req],"model_nodes":affects,"checks":checks}})
write("discovery.json",discovery)
acceptance=read("acceptance.json")
new=[
    ("size-default","R14","size_default",["limit_bytes"],8192),
    ("size-equality","R14","size_equal",["archive_count"],1),
    ("size-utf8-over","R14","size_utf8_over",["content_bytes"],8193),
    ("size-over-waits","R15","size_utf8_over",["phase"],"waiting"),
    ("size-over-no-start","R15","size_utf8_over",["workers_started"],0),
    ("size-invalid-inputs","R14","size_invalid",["all_rejected"],True),
    ("size-invalid-unchanged","R14","size_invalid",["unchanged"],True),
    ("size-project-isolation","R14","size_project_isolation",["other_project_limit"],8192),
    ("size-project-other-completes","R14","size_project_isolation",["other_completed"],True),
    ("size-running-wait","R15","size_running_restore",["index_waited"],True),
    ("size-running-natural-end","R15","size_running_restore",["running_finished"],True),
    ("size-manual-resume","R15","size_running_restore",["no_auto_resume"],True),
    ("size-reuse-result","R15","size_running_restore",["content_started_once"],True),
    ("size-running-completes","R15","size_running_restore",["archive_count"],1),
    ("size-no-version-change","R15","size_running_restore",["content_version_unchanged"],True),
    ("size-approval-survives","R15","size_running_restore",["approval_survived"],True),
    ("size-commit-fresh","R15","size_commit_fresh",["archive_count"],0),
    ("size-commit-new-limit","R15","size_commit_fresh",["limit_bytes"],1),
    ("size-resume-fresh","R15","size_resume_over",["still_waiting"],True),
    ("size-resume-no-start","R15","size_resume_over",["workers_started"],0),
    ("size-snapshot-stable","R15","size_snapshot_stable",["snapshot_unchanged"],True),
    ("size-settings-persist","R14","size_persist",["limit_bytes"],1234),
]
for ident,req,case,path,value in new:
    acceptance["checks"].append({"id":ident,"requirement":req,"case":case,"path":path,"equals":value})
acceptance["model_checks"].append({"id":"size-model-stable-project","requirement":"R16",
    "path":["project_id"],"equals":"team-archive-trial-01"})
write("acceptance.json",acceptance)
whitebox=read("whitebox.json")
whitebox["rules"].append({"id":"size","requirement":"R14","node":"size_guard",
    "source":{"path":"archive_app/policy.py","symbol":"check_size"},
    "parameters":{"content":"str","limit_bytes":"int","project_id":"str","limit_revision":"int"},"returns":"dict",
    "claim":"按 UTF-8 正文计算实际字节并与当前上限比较，包含相等边界",
    "basis":"实际模拟用户 U05-U06","category":"parameter-and-decision"})
for ident,case,fields in [
    ("size-exact-bytes","size_equal",[{"path":["inputs","content_bytes"],"equals":8192},{"path":["inputs","limit_bytes"],"equals":8192},{"path":["outputs","allowed"],"equals":True}]),
    ("size-multibyte-over","size_utf8_over",[{"path":["inputs","content_bytes"],"equals":8193},{"path":["outputs","allowed"],"equals":False}]),
    ("size-final-limit","size_commit_fresh",[{"path":["inputs","limit_bytes"],"equals":1},{"path":["outputs","allowed"],"equals":False}])]:
    item={"id":ident,"rule":"size","case":case,"phase":"decision","count":{"min":1},"fields":fields}
    if case=="size_commit_fresh":
        item["select"]=[{"path":["inputs","limit_bytes"],"equals":1}]
    whitebox["checks"].append(item)
write("whitebox.json",whitebox)
cfg=read("sync.json")
cfg["watch_files"].append("tooling/size_scenarios.py")
for case in ["size_running_restore","size_commit_fresh"]:
    cfg["required_execution_cases"].append(case)
write("sync.json",cfg)
(HERE/"dialogue.md").write_text("# 大小上限迭代 · 实际模拟对话\n\n"+U05+"\n\n## 实际追问\n\n"+A05+"\n\n## 实际回答\n\n"+U06+"\n",encoding="utf-8",newline="\n")
for name in ["intent.json","acceptance.json","whitebox.json","discovery.json","sync.json"]:
    shutil.copy2(ROOT/name,HERE/("before-code-"+name))
print(json.dumps({"new_requirements":["R14","R15","R16"],"new_checks":len(new),"total_checks":len(acceptance["checks"]),"status":"independent expectations saved before implementation"}))
