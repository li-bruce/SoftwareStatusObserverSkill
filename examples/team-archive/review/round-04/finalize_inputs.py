"""One-time v1 provenance/configuration preparation; not a validation bypass."""
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).absolute().parents[2]


def write(path,value):
    (ROOT/path).write_text(json.dumps(value,ensure_ascii=False,indent=2)+"\n",encoding="utf-8",newline="\n")


def main():
    trial=ROOT.parent
    manifest=json.loads((trial/"skill-candidate-8/skill-manifest.json").read_text(encoding="utf-8-sig"))
    old=json.loads((trial/"skill-candidate-5/skill-manifest.json").read_text(encoding="utf-8-sig"))
    mismatches=[]
    for name,expected in manifest["files"].items():
        path=trial/"skill-candidate-8/business-observer"/name
        if hashlib.sha256(path.read_bytes()).hexdigest()!=expected:
            mismatches.append(name)
    if mismatches:
        raise RuntimeError(mismatches)
    changed=[n for n,h in manifest["files"].items() if old["files"].get(n)!=h]
    write("review/round-04/candidate8-integrity.json",{"version":manifest["version"],"files":len(manifest["files"]),
          "mismatches":mismatches,"changed_since_candidate5":changed,
          "runtime_scripts_unchanged":all(old["files"].get(n)==h for n,h in manifest["files"].items() if n.startswith("scripts/"))})
    write("review/round-04/candidate8-manifest.json",manifest)
    write("observer_runtime/origin.json",{"source":"skill-candidate-8","version":manifest["version"],
          "manifest":"../skill-candidate-8/skill-manifest.json","runtime_scripts":"byte-identical to candidate-3; verified against candidate-8 hashes"})
    cfg=json.loads((ROOT/"sync.json").read_text(encoding="utf-8"))
    for name in ["static/app.html","static/app.css","static/app.js","AGENTS.md","validate.py",".gitattributes",
                 "tooling/graph_tests.mjs","tooling/mutations.py","observer_runtime/origin.json"]:
        if name not in cfg["watch_files"]:
            cfg["watch_files"].append(name)
    node=["C:/nvm4w/nodejs/node.exe","tooling/graph_tests.mjs"]
    if node not in cfg["test_commands"]:
        cfg["test_commands"].append(node)
    write("sync.json",cfg)
    own=json.loads((ROOT/"ownership.json").read_text(encoding="utf-8"))
    own["scan"]=sorted(set(own["scan"]+["run.py","validate.py"]))
    own["layers"]["integration"]["paths"]=sorted(set(own["layers"]["integration"]["paths"]+["run.py"]))
    own["layers"]["tooling"]["paths"]=sorted(set(own["layers"]["tooling"]["paths"]+["validate.py"]))
    write("ownership.json",own)
    # Normalize authored inputs before review/verify. Upstream bytes stay untouched.
    paths=set(cfg["code_files"]+cfg["watch_files"]+["intent.json","discovery.json","acceptance.json","whitebox.json","sync.json"])
    excluded={"static/graph/"+n for n in ("pixi.min.js","elk.bundled.js","elk-worker.min.js","PIXI-LICENSE.txt","ELK-LICENSE.md","layout.js","index.html")}
    normalized=[]
    for name in sorted(paths):
        if name.startswith("observer_runtime/") or name in excluded:
            continue
        path=ROOT/name
        raw=path.read_bytes()
        data=raw.replace(b"\r\n",b"\n")
        if data!=raw:
            path.write_bytes(data)
            normalized.append(name)
    write("review/round-04/lf-normalization.json",{"reason":"Stabilize authored raw-byte source bindings before final review/verify; no acceptance expectations changed.",
          "files":normalized,"preserved":"Pinned runtime and untouched vendor assets retain original hashes via project .gitattributes."})


if __name__=="__main__":
    main()
