"""Explicit frozen project export, preserving source/evidence without live databases."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

ROOT=Path(__file__).absolute().parents[2]
sys.path.insert(0,str(ROOT))
from observer_runtime.project_bundle import export,inspect
cfg=json.loads((ROOT/"sync.json").read_text(encoding="utf-8"))
manifest=json.loads((ROOT/"manifest.json").read_text(encoding="utf-8"))
out=ROOT/"review/v1"
names=set(cfg["code_files"]+cfg["watch_files"]+["behavior.json","manifest.json","sync.json",
          "intent.json","discovery.json","acceptance.json","whitebox.json","ownership.json",
          "README.md","AGENTS.md","requirements.txt","archive_app/__init__.py","integrations/__init__.py","tooling/__init__.py"])
for folder in ["observer_runtime",".stategraph"]:
    names.update(p.relative_to(ROOT).as_posix() for p in (ROOT/folder).rglob("*") if p.is_file() and "__pycache__" not in p.parts)
for p in out.iterdir():
    if p.is_file() and p.suffix in (".json",".png",".txt",".md") and not p.name.startswith(("server","bundle")):
        names.add(p.relative_to(ROOT).as_posix())
names.update(["review/round-04/candidate8-manifest.json","review/round-04/candidate8-integrity.json",
              "review/round-04/lf-normalization.json"])
bundle={"schema_version":1,"kind":"project","project_id":"team-archive-trial-01",
        "data_policy":"synthetic-only","versions":{"v1":manifest["build_id"],"skill":"0.4.0-candidate.8"},
        "files":sorted(names),"commands":["python -X utf8 -B validate.py","python -X utf8 -B run.py --port 8824 --db data/v1.sqlite3"]}
(out/"bundle-config.json").write_text(json.dumps(bundle,ensure_ascii=False,indent=2),encoding="utf-8",newline="\n")
result=export(ROOT,bundle,"review/v1/project-v1.zip")
inspected=inspect(out/"project-v1.zip")
assert inspected["valid"]
(out/"bundle-integrity.json").write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8",newline="\n")
sources=out/"source-snapshot"
for name in manifest["files"]:
    path=sources/name
    path.parent.mkdir(parents=True,exist_ok=True)
    shutil.copy2(ROOT/name,path)
print(json.dumps(result,ensure_ascii=False))
