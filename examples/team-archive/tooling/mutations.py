"""Run intentionally wrong core copies against unchanged independent expectations."""
import json
from pathlib import Path
import shutil
import subprocess
import sys
import uuid

ROOT = Path(__file__).absolute().parents[1]
MUTATIONS = [
    ("deadline_inclusive", "policy.py", 'now < grant["deadline"]',
     'now <= grant["deadline"]', "approval_at_deadline"),
    ("ignore_version", "policy.py", 'grant["content_version"] == request["content_version"]',
     "True", "approval_target_other_version"),
    ("ignore_direct_folder", "policy.py", 'and a["folder_id"] == folder_id', "and True", "scope_ancestor_only"),
    ("require_every_approval", "policy.py", 'any(c["allowed"] for c in candidates)',
     'all(c["allowed"] for c in candidates)', "revoke_with_alternative"),
    ("allow_secret", "policy.py", '"passed": "SECRET:" not in content',
     '"passed": True', "secret_content"),
    ("size_exclusive_boundary", "policy.py", "content_bytes <= limit_bytes",
     "content_bytes < limit_bytes", "size_equal"),
    ("size_count_characters", "policy.py", 'len(content.encode("utf-8"))',
     "len(content)", "size_utf8_over"),
    ("size_commit_cached", "service.py", 'self.evaluate(db,run,trace,"commit")',
     'run["qualification"]', "size_commit_fresh"),
    ("size_auto_resume", "service.py", 'elif run["resume_required"]:',
     'elif False:', "size_running_restore"),
]


def main():
    target = ROOT / "review/mutations" / uuid.uuid4().hex
    target.mkdir(parents=True)
    expected = json.loads((ROOT / "acceptance.json").read_text(encoding="utf-8"))
    reports = []
    for name, module, before, after, case in MUTATIONS:
        if "--size-only" in sys.argv and not case.startswith("size_"):
            continue
        folder = target / name
        for item in ("archive_app", "integrations", "observer_runtime", "tooling"):
            shutil.copytree(ROOT/item, folder/item, ignore=shutil.ignore_patterns("__pycache__"))
        shutil.copy2(ROOT/"behavior.json",folder/"behavior.json")
        source = folder/"archive_app"/module
        text = source.read_text(encoding="utf-8")
        if text.count(before) != 1:
            raise RuntimeError("mutation target must match exactly once: "+name)
        source.write_text(text.replace(before,after),encoding="utf-8",newline="\n")
        scenario_module="tooling.size_scenarios" if case.startswith("size_") else "tooling.scenarios"
        script = (f"import json; from {scenario_module} import execute; "
                  "m=json.load(open('behavior.json',encoding='utf-8')); "
                  f"print(json.dumps(execute({case!r},'off',m,'mutation-core')))")
        result = subprocess.run([sys.executable,"-X","utf8","-B","-c",script],cwd=folder,
                                capture_output=True,text=True,encoding="utf-8",timeout=25)
        failures = []
        if result.returncode:
            failures.append({"execution_error":result.stderr})
        else:
            observed = json.loads(result.stdout)["observations"]
            for check in expected["checks"]:
                if check["case"] != case:
                    continue
                value = observed
                for key in check["path"]:
                    value = value[key]
                if value != check["equals"]:
                    failures.append({"check":check["id"],"expected":check["equals"],"actual":value})
        reports.append({"mutation":name,"case":case,"detected_by_business_expectation":bool(failures),
                        "returncode":result.returncode,"failures":failures})
    report={"scope":"Modified isolated core copies. These failures are business outcomes, not source hash mismatches.",
            "mutations":reports,"passed":all(r["detected_by_business_expectation"] for r in reports)}
    (target/"report.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8",newline="\n")
    print(json.dumps({"report":str(target/"report.json"),**report},ensure_ascii=False))
    return 0 if report["passed"] else 1


if __name__=="__main__":
    raise SystemExit(main())
