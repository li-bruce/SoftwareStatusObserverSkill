"""Independent contract, source isolation, and observation-failure checks."""
import json
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from observer_runtime.architecture_guard import inspect
from observer_runtime.behavior_model import capture, validate_events
from observer_runtime.sync_verify import assess_observations
from tests.scenarios import run_all
from app.ports import EventPort
from integrations.bo_capture import BOCapture

if __name__ == "__main__":
    model = json.loads((ROOT / "behavior.json").read_text())
    manifest = capture(ROOT, model)
    payload = run_all(model, manifest)
    errors = assess_observations(model, json.loads((ROOT / "acceptance.json").read_text()), payload, ["on", "off", "fault"])
    for run in payload["runs"]:
        if run["mode"] == "on":
            errors.extend(validate_events(run["events"], model, manifest["build_id"])["errors"])
            if run["health"]["port_errors"]:
                errors.append({"unexpected_probe_error": run["case"], "health": run["health"]})
        elif run["mode"] == "fault" and run["case"] != "policy" and not run["health"]["port_errors"]:
            errors.append("fault mode not exercised")
    port = EventPort()
    port.bo_emit("unknown", "return", {}, lambda: 1 / 0)
    if port.errors:
        errors.append("disabled port evaluated builder")
    enabled = EventPort(lambda *args: None)
    enabled.bo_emit("unknown", "return", {}, lambda: 1 / 0)
    if enabled.errors != 1:
        errors.append("payload failure not counted")
    # Bounded collector drops with an explicit gap; it cannot mutate any business state.
    collector = BOCapture(model, manifest["build_id"], capacity=1)
    context = {"attempt": "r", "entity": "t", "call_id": "c", "param_version": 1, "revision": 1}
    collector.bo_record("queue", "wait", context, {"inputs": {}, "outputs": {"state": "queued"}})
    collector.bo_record("queue", "wait", context, {"inputs": {}, "outputs": {"state": "blocked"}})
    if not collector.bo_health()["gaps"] or len(collector.events) != 1:
        errors.append("retention gap absent")
    architecture = inspect(ROOT, json.loads((ROOT / "ownership.json").read_text()))
    errors.extend(architecture["errors"])
    report = {"valid": not errors, "errors": errors, "scenarios": len(payload["runs"]), "state_frames": sum(c["frames"] for c in payload["shared_resource_checks"]), "scope": "explicit business assertions, every recorded transaction's shared resource invariants, observation isolation and static imports"}
    print(json.dumps(report, ensure_ascii=False))
    raise SystemExit(1 if errors else 0)
