import json
from pathlib import Path
import shutil

ROOT=Path(__file__).absolute().parents[2]
OUT=ROOT/"review/v1"
OUT.mkdir(parents=True,exist_ok=True)
change=ROOT/json.loads((ROOT/".stategraph/active.json").read_text(encoding="utf-8"))["change"]
wrapped=json.loads((change/"checks/observations.json").read_text(encoding="utf-8"))
payload=json.loads(wrapped["stdout"])
assert wrapped["exit_code"]==0
accepted=json.loads((change/"accepted.json").read_text(encoding="utf-8"))
assert payload["build_id"]==accepted["build_id"]
(OUT/"observations.json").write_text(json.dumps(payload,ensure_ascii=False),encoding="utf-8",newline="\n")
for name in ["behavior.json","manifest.json","acceptance.json","whitebox.json","intent.json","discovery.json","sync.json","ownership.json"]:
    shutil.copy2(ROOT/name,OUT/name)
for name in ["accepted.json","verification.json","review.json"]:
    shutil.copy2(change/name,OUT/name)
shutil.copy2(change/"checks/whitebox.json",OUT/"whitebox-results.json")
print(json.dumps({"build_id":payload["build_id"],"runs":len(payload["runs"]),
                  "cases":len({r["case"] for r in payload["runs"]}),"saved":str(OUT)}))
