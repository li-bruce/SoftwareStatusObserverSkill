"""Extract the frozen v2 bundle to a new directory, then use its normal validation."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import zipfile

ROOT=Path(__file__).absolute().parents[2]
OUT=ROOT/"review/v2"
target=OUT/"project-export"
if target.exists():
    raise RuntimeError("Use a fresh export directory")
target.mkdir()
with zipfile.ZipFile(OUT/"project-v2.zip") as archive:
    for name in archive.namelist():
        (target/name).resolve().relative_to(target.resolve())
    archive.extractall(target)
assert (target/"validate.py").is_file()
result=subprocess.run([sys.executable,"-X","utf8","-B","validate.py"],cwd=target,
    capture_output=True,text=True,encoding="utf-8",timeout=120)
(OUT/"project-export-validation.txt").write_text(result.stdout+"\n"+result.stderr,encoding="utf-8",newline="\n")
report={"passed":result.returncode==0,"exit_code":result.returncode,"root":str(target),
        "command":["python","-X","utf8","-B","validate.py"],
        "package_sha256":hashlib.sha256((OUT/"project-v2.zip").read_bytes()).hexdigest(),
        "includes_frozen_v1":(target/"review/v1/source-snapshot/intent.json").exists()}
(OUT/"project-export-validation.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8",newline="\n")
print(json.dumps(report,ensure_ascii=False))
raise SystemExit(result.returncode)
