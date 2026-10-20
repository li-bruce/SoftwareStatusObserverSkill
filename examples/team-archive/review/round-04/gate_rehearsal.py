"""Prove the normal entry rejects a missing probe, then verify its repair."""
import json
from pathlib import Path
import shutil
import subprocess
import sys
import uuid

ROOT=Path(__file__).absolute().parents[2]
DEST=ROOT/"review/gate-rehearsal"/uuid.uuid4().hex
cfg=json.loads((ROOT/"sync.json").read_text(encoding="utf-8"))
files=set(cfg["code_files"]+cfg["watch_files"]+["sync.json","behavior.json","manifest.json",
          "intent.json","acceptance.json","whitebox.json","discovery.json","requirements.txt"])
for folder in ["observer_runtime","archive_app","integrations","tooling",".stategraph"]:
    files.update(p.relative_to(ROOT).as_posix() for p in (ROOT/folder).rglob("*") if p.is_file() and "__pycache__" not in p.parts)
for name in files:
    path=DEST/name
    path.parent.mkdir(parents=True,exist_ok=True)
    shutil.copy2(ROOT/name,path)
log=[]


def run(args):
    result=subprocess.run([sys.executable,"-X","utf8","-B",*args],cwd=DEST,
                          capture_output=True,text=True,encoding="utf-8",timeout=120)
    log.append({"argv":args,"exit_code":result.returncode,"stdout":result.stdout,"stderr":result.stderr})
    return result


begin=run(["observer_runtime/change_sync.py","begin","--root",".","--change",".stategraph/change-003",
           "--request","隔离演练：故意遗漏范围探针，验证正常入口拒绝并恢复同一探针","--requirements","R02"])
assert begin.returncode==0,begin.stdout
source=DEST/"archive_app/policy.py"
original=source.read_bytes()
text=original.decode("utf-8")
start=text.index('    trace.record("scope_check"')
end=text.index("    return allowed",start)
source.write_text(text[:start]+text[end:],encoding="utf-8",newline="\n")
rejected=run(["validate.py"])
assert rejected.returncode!=0,"Normal delivery entry incorrectly accepted missing probe"
# Preserve the failed source separately, then repair in the same recorded change.
shutil.copy2(source,DEST/"missing-probe.py.evidence")
source.write_bytes(original)
inspected=run(["observer_runtime/change_sync.py","inspect","--root","."])
impact=json.loads(inspected.stdout)
assert not impact["errors"]
review={"candidate_id":impact["candidate_id"],"decisions":{
    part:{"action":"unchanged","reason":"隔离反例已恢复漏掉的原探针；业务、机器、图和独立预期保持首版原值，重新执行所有验证。"}
    for part in ["business","state_machine","abstraction","probes"]},
    "excluded_symbols":{},"requirement_changes":{}}
assert not impact["unmapped_changed_symbols"]
(DEST/".stategraph/change-003/review.json").write_text(json.dumps(review,ensure_ascii=False),encoding="utf-8",newline="\n")
for args in [
    ["observer_runtime/change_sync.py","verify","--root","."],
    ["observer_runtime/change_sync.py","accept","--root","."],
    ["validate.py"]]:
    result=run(args)
    assert result.returncode==0,result.stdout
report={"passed":True,"isolated_project":str(DEST),"main_project_unchanged":True,
        "omitted":"scope_check decision probe","normal_entry_rejected":rejected.returncode,
        "repair":"Restored the real probe in the same recorded change, then verify/accept/normal validate.",
        "log":log}
out=ROOT/"review/v1/gate-rehearsal.json"
out.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8",newline="\n")
print(json.dumps({k:v for k,v in report.items() if k!="log"},ensure_ascii=False))
