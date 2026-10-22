"""Isolated stale-source and semantic counterexamples; never edits the original."""
import json
from pathlib import Path
import shutil
import subprocess
import sys
import uuid
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from observer_runtime.sync_verify import assess_observations
from observer_runtime.mapping_contract import assess as assess_mapping

def run():
    model = json.loads((ROOT / "behavior.json").read_text())
    expected = json.loads((ROOT / "acceptance.json").read_text())
    paths = set(model["source_files"]) | {"behavior.json", "intent.json", "discovery.json", "sync.json", "acceptance.json", "whitebox.json", "manifest.json", "ownership.json", "bo_stategraph/config/views/local.json"}
    result = []
    for name, file, old, new in [("expiry_inclusive", "app/policy.py", 'now < grant["expires"]', 'now <= grant["expires"]'), ("reject_exact_size", "app/checks.py", 'elif value > limit:', 'elif value >= limit:')]:
        clone = ROOT / ".validation" / (name + "-" + uuid.uuid4().hex[:8])
        clone.mkdir(parents=True)
        for item in paths:
            target = clone / item
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / item, target)
        shutil.copytree(ROOT / ".stategraph", clone / ".stategraph")
        source = clone / file
        content = source.read_text(encoding="utf-8-sig")
        if content.count(old) != 1:
            raise ValueError("mutation anchor differs")
        source.write_text(content.replace(old, new), encoding="utf-8")
        # The normal delivery entrypoint must reject core-only edits before rebuilding.
        stale = subprocess.run([sys.executable, "-X", "utf8", "-B", "tooling/gate.py", "check"], cwd=clone, capture_output=True, text=True, encoding="utf-8")
        (clone / "stale-gate.txt").write_text(stale.stdout + stale.stderr, encoding="utf-8")
        build = subprocess.run([sys.executable, "-X", "utf8", "-B", "tooling/build_model.py"], cwd=clone, capture_output=True, text=True, encoding="utf-8")
        if build.returncode:
            raise RuntimeError(build.stderr)
        observed = subprocess.run([sys.executable, "-X", "utf8", "-B", "tooling/observe.py"], cwd=clone, capture_output=True, text=True, encoding="utf-8", timeout=120)
        if observed.returncode:
            raise RuntimeError(observed.stderr)
        payload = json.loads(observed.stdout)
        candidate = json.loads((clone / "behavior.json").read_text())
        business = assess_observations({}, expected, payload, ["on", "off", "fault"])
        mapping = assess_mapping(payload, required=True)
        report = {"mutation": name, "directory": str(clone), "stale_gate_exit": stale.returncode, "mapping": mapping, "business_errors": business, "expected_contract_unchanged": (clone / "acceptance.json").read_bytes() == (ROOT / "acceptance.json").read_bytes(), "source_regenerated": build.returncode == 0}
        (clone / "mutation-result.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        (clone / "observations.json").write_text(observed.stdout, encoding="utf-8")
        if stale.returncode == 0 or not business or not mapping["valid"] or not report["expected_contract_unchanged"]:
            raise AssertionError(report)
        result.append(report)
    output = {"valid": True, "meaning": "Stale source rejected; after truthful remapping the injected business defect is still rejected by unchanged independent expectations", "mutations": result}
    (ROOT / "review/round-03/mutations.json").write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(output, ensure_ascii=False))

if __name__ == "__main__":
    run()
