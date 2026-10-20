"""Project maintenance before inspect; does not accept, capture, or alter expectations."""
import json
from pathlib import Path

ROOT=Path(__file__).absolute().parents[2]
cfg=json.loads((ROOT/"sync.json").read_text(encoding="utf-8"))
for probe in ({"node":"project_limit","phase":"read"},{"node":"size_guard","phase":"decision"}):
    if probe not in cfg["required_probes"]:
        cfg["required_probes"].append(probe)
probe={"case":"size_commit_fresh","node":"size_guard","phase":"decision"}
if probe not in cfg["required_runtime_probes"]:
    cfg["required_runtime_probes"].append(probe)
(ROOT/"sync.json").write_text(json.dumps(cfg,ensure_ascii=False,indent=2),encoding="utf-8",newline="\n")
authored=set(cfg["code_files"]+cfg["watch_files"]+[
    "sync.json","intent.json","discovery.json","acceptance.json","whitebox.json"])
pinned={"static/graph/index.html","static/graph/layout.js","static/graph/elk-worker.min.js",
        "static/graph/elk.bundled.js","static/graph/pixi.min.js",
        "static/graph/PIXI-LICENSE.txt","static/graph/ELK-LICENSE.md"}
changed=[]
for name in sorted(authored):
    if name.startswith("observer_runtime/") or name in pinned:
        continue
    path=ROOT/name
    before=path.read_bytes()
    after=before.replace(b"\r\n",b"\n")
    if before!=after:
        path.write_bytes(after)
        changed.append(name)
(ROOT/"review/round-05/lf-normalization.json").write_text(
    json.dumps({"changed":changed,"reason":"Normalize authored text only; upstream pinned bytes unchanged."},
               ensure_ascii=False,indent=2),encoding="utf-8",newline="\n")
print(json.dumps({"normalized":changed},ensure_ascii=False))
