"""Freeze a reviewable v2 export with the required immutable v1 references."""
import json
from pathlib import Path
import shutil
import sys

ROOT=Path(__file__).absolute().parents[2]
sys.path.insert(0,str(ROOT))
from observer_runtime.project_bundle import export,inspect

out=ROOT/"review/v2"
cfg=json.loads((ROOT/"sync.json").read_text(encoding="utf-8"))
manifest=json.loads((ROOT/"manifest.json").read_text(encoding="utf-8"))
names=set(cfg["code_files"]+cfg["watch_files"]+[
    "behavior.json","manifest.json","sync.json","intent.json","discovery.json",
    "acceptance.json","whitebox.json","ownership.json","README.md","requirements.txt",
    "archive_app/__init__.py","integrations/__init__.py","tooling/__init__.py"])
for folder in ("observer_runtime",".stategraph","review/v1/source-snapshot"):
    names.update(p.relative_to(ROOT).as_posix() for p in (ROOT/folder).rglob("*")
                 if p.is_file() and "__pycache__" not in p.parts)
for version in ("v1","v2"):
    for path in (ROOT/"review"/version).iterdir():
        if path.is_file() and path.suffix in (".json",".png",".txt",".md") and not path.name.startswith(("server","bundle","core-package")):
            names.add(path.relative_to(ROOT).as_posix())
names.update(["review/v1/project-v1.zip","review/round-04/candidate8-manifest.json",
              "review/round-04/candidate8-integrity.json","review/round-05/dialogue.md",
              "review/round-05/development-notes.md","review/round-05/core_export_smoke.py"])
for path in (out/"initial-01113409").iterdir():
    if path.is_file() and not path.name.startswith("server"):
        names.add(path.relative_to(ROOT).as_posix())
bundle={"schema_version":1,"kind":"project","project_id":"team-archive-trial-01",
        "data_policy":"synthetic-only","versions":{"v2":manifest["build_id"],
            "v1":json.loads((ROOT/"review/v1/manifest.json").read_text(encoding="utf-8"))["build_id"],
            "skill":"0.4.0-candidate.8"},"files":sorted(names),
        "commands":["python -X utf8 -B validate.py","python -X utf8 -B run.py --port 8824 --db data/v2.sqlite3 --delay 4"]}
(out/"bundle-config.json").write_text(json.dumps(bundle,ensure_ascii=False,indent=2),encoding="utf-8",newline="\n")
if (out/"project-v2.zip").exists():
    raise RuntimeError("Never overwrite an existing frozen v2 ZIP")
result=export(ROOT,bundle,"review/v2/project-v2.zip")
assert inspect(out/"project-v2.zip")["valid"]
(out/"bundle-integrity.json").write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8",newline="\n")
for name in [*manifest["files"],"intent.json"]:
    path=out/"source-snapshot"/name
    path.parent.mkdir(parents=True,exist_ok=True)
    shutil.copy2(ROOT/name,path)
print(json.dumps(result,ensure_ascii=False))
