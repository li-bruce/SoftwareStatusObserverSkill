import json
from pathlib import Path
import shutil

ROOT=Path(__file__).absolute().parents[2]
OUT=ROOT/"review/v2"
OUT.mkdir(parents=True,exist_ok=True)
change=ROOT/json.loads((ROOT/".stategraph/active.json").read_text(encoding="utf-8"))["change"]
wrapped=json.loads((change/"checks/observations.json").read_text(encoding="utf-8"))
payload=json.loads(wrapped["stdout"])
accepted=json.loads((change/"accepted.json").read_text(encoding="utf-8"))
assert wrapped["exit_code"]==0 and payload["build_id"]==accepted["build_id"]
(OUT/"observations.json").write_text(json.dumps(payload,ensure_ascii=False),encoding="utf-8",newline="\n")
for name in ("behavior.json","manifest.json","acceptance.json","whitebox.json","intent.json","discovery.json","sync.json","ownership.json"):
    shutil.copy2(ROOT/name,OUT/name)
for name in ("accepted.json","verification.json","review.json"):
    shutil.copy2(change/name,OUT/name)
shutil.copy2(change/"checks/whitebox.json",OUT/"whitebox-results.json")
shutil.copy2(ROOT/"review/round-05/normal-validation.txt",OUT/"normal-validation.txt")
shutil.copy2(ROOT/"review/round-05/size-mutations.json",OUT/"size-mutations.json")
old=json.loads((ROOT/"review/v1/behavior.json").read_text(encoding="utf-8"))
new=json.loads((ROOT/"behavior.json").read_text(encoding="utf-8"))
old_nodes={n["id"]:n for n in old["nodes"]}
new_nodes={n["id"]:n for n in new["nodes"]}
diff={"from":"v1","to":"v2","from_build":json.loads((ROOT/"review/v1/manifest.json").read_text(encoding="utf-8"))["build_id"],
      "to_build":payload["build_id"],"project_id_unchanged":old["project_id"]==new["project_id"],
      "layout_id_unchanged":old["presentation"]["layout_id"]==new["presentation"]["layout_id"],
      "added_nodes":[new_nodes[n] for n in sorted(new_nodes.keys()-old_nodes.keys())],
      "removed_nodes":sorted(old_nodes.keys()-new_nodes.keys()),
      "changed_captures":[{"id":n,"before":old_nodes[n].get("capture"),"after":new_nodes[n].get("capture")}
                          for n in old_nodes.keys()&new_nodes.keys()
                          if old_nodes[n].get("capture")!=new_nodes[n].get("capture")],
      "stable_existing_ids":len(old_nodes.keys()&new_nodes.keys()),
      "unchanged_original_business_expectations":True}
old_accept=json.loads((ROOT/"review/v1/acceptance.json").read_text(encoding="utf-8"))
new_accept=json.loads((ROOT/"acceptance.json").read_text(encoding="utf-8"))
assert all(c in new_accept["checks"] for c in old_accept["checks"])
(OUT/"node-changes.json").write_text(json.dumps(diff,ensure_ascii=False,indent=2),encoding="utf-8",newline="\n")
print(json.dumps({"build_id":payload["build_id"],"runs":len(payload["runs"]),
    "business_checks":len(new_accept["checks"]),"model_checks":len(new_accept["model_checks"]),
    "new_nodes":[n["id"] for n in diff["added_nodes"]],"removed":diff["removed_nodes"]}))
