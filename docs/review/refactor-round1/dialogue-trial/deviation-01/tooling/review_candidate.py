"""Persist this implementation's reviewed classification for the current candidate."""
import json
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from observer_runtime.change_sync import inspect
from observer_runtime.sync_config import config

if __name__ == "__main__":
    cfg = config(ROOT, "sync.json")
    active = json.loads((ROOT / ".stategraph/active.json").read_text())
    change = ROOT / active["change"]
    base, current, impact = inspect(ROOT, cfg, change)
    excluded = {}
    for ident in impact["unmapped_implementation_symbols"]:
        symbol = current["structure"]["symbols"][ident]
        if symbol["kind"] != "class":
            raise ValueError("Needs individual semantic review: " + ident)
        excluded[ident] = "Class declaration is a structural container; its constructor and every method are source-mapped. The class object itself is not a separate business action."
    review = {"candidate_id": current["id"], "decisions": {
        "business": {"action": "updated", "reason": "Implement U02/U03/U04 only: printer-scoped alternative approvals, expiry before start, parallel checks, eligible FIFO, independent versions and selected-run cancellation."},
        "state_machine": {"action": "updated", "reason": "Executor consumes bo_stategraph/declaration.py. SQLite writer transaction owns shared printer occupancy and queue; all transaction snapshots checked with the project shared-resource extension."},
        "abstraction": {"action": "updated", "reason": "Stable business IDs retain round-01 meaning; all implementation functions including transaction callbacks bind to current source, static auxiliaries remain under analysis details."},
        "probes": {"action": "updated", "reason": "Commit probes follow SQLite commit. Actual parameters, predicate flags, wait reasons and effect IDs are compared independently; overridden checker functions are attributed to the actual worker/callback, not falsely to the default checker."}}, "excluded_symbols": excluded, "requirement_changes": {r["id"]: "Authorized initial implementation; source U02/U03/U04 and preserved discovery history. Expectations authored before final runtime validation." for r in current["intent"]["requirements"]}, "limits": ["No real printer or mesh parsing", "Local synthetic actor identities, not authentication", "No automatic retry of interrupted checks after process crash; persisted waiting/printing ownership can resume", "No inferred causal edges or arbitrary natural-language equivalence"]}
    (change / "review.json").write_text(json.dumps(review, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"candidate_id": current["id"], "class_containers_classified": len(excluded), "structural_errors": impact["errors"]}))
