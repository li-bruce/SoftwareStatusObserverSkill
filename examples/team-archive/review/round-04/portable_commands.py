"""Apply only command portability to an already begun change."""
import json
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).absolute().parents[2]
cfg=json.loads((ROOT/"sync.json").read_text(encoding="utf-8"))
cfg["observations_command"][0]="{python}"
for command in cfg["test_commands"]:
    command[0]="node" if command[-1].endswith(".mjs") else "{python}"
(ROOT/"sync.json").write_text(json.dumps(cfg,ensure_ascii=False,indent=2)+"\n",encoding="utf-8",newline="\n")
result=subprocess.run([sys.executable,"-X","utf8","-B","observer_runtime/change_sync.py","inspect","--root","."],
                      cwd=ROOT,capture_output=True,text=True,encoding="utf-8")
impact=json.loads(result.stdout)
assert not impact["errors"],impact["errors"]
assert not impact["changed_symbols"]
review={"candidate_id":impact["candidate_id"],"decisions":{
    part:{"action":"unchanged","reason":"只将检查配置中的本机 Python 路径改为 {python}、Node 路径改为 node；真实业务、机器、源码映射、探针和独立预期均未改变。"}
    for part in ["business","state_machine","abstraction","probes"]},"excluded_symbols":{},"requirement_changes":{}}
(ROOT/".stategraph/change-002/review.json").write_text(json.dumps(review,ensure_ascii=False,indent=2),encoding="utf-8",newline="\n")
(ROOT/"review/round-04/portable-inspect.json").write_text(result.stdout,encoding="utf-8",newline="\n")
