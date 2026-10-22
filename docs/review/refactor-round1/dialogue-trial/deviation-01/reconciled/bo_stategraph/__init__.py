"""Stable, read-only stategraph interface; observation can be disabled independently."""
from bo_stategraph.declaration import definition

class BOStateGraph:
    def __init__(self, store):
        self.store = store

    def bo_definition(self):
        return definition()

    def bo_instances(self, snapshot=None):
        snap = snapshot if snapshot is not None else self.store.snapshot()
        return [{"id": r["id"], "task_id": r["task_id"], "version": r["version"], "state": r["state"], "printer_id": r["printer_id"], "queue_seq": r["queue_seq"], "reason": r["reason"], "parameters": {"dimensions": r["dimensions"], "material": r["material"], "printing": r["parameters"]}, "activities": [a for a in snap["activities"] if a["run_id"] == r["id"]], "occupies": [p["id"] for p in snap["printers"] if p["occupant"] == r["id"]]} for r in snap["runs"]]

    def bo_export(self):
        snap = self.store.snapshot()
        return {"definition": self.bo_definition(), "instances": self.bo_instances(snap), "resources": snap["printers"], "checks": validate_instances(snap), "source": "SQLite authoritative snapshot", "coverage": "two shared printers; submitted dimensions; local simulated device"}

def validate_instances(snapshot: dict) -> list:
    """Project extension: shared printer capacity, ALL checks, and run identities.

    The frozen activity-graph checker supports per-run resource pools only.
    These shared resources are checked here, against the actual SQLite snapshot.
    """
    errors = []
    runs = {r["id"]: r for r in snapshot["runs"]}
    for p in snapshot["printers"]:
        running = [r for r in runs.values() if r["printer_id"] == p["id"] and r["state"] in ("printing", "stopping")]
        if len(running) > 1:
            errors.append("printer capacity exceeded: " + p["id"])
        if {r["id"] for r in running} != ({p["occupant"]} if p["occupant"] else set()):
            errors.append("occupancy differs from running states: " + p["id"])
    for r in runs.values():
        acts = [a for a in snapshot["activities"] if a["run_id"] == r["id"]]
        if sorted(a["name"] for a in acts) != ["material", "size"]:
            errors.append("missing parallel activity: " + r["id"])
        if r["state"] in ("queued", "blocked", "printing", "stopping", "completed") and any(a["state"] != "passed" for a in acts):
            errors.append("ALL check barrier violated: " + r["id"])
        if r["state"] in ("queued", "blocked", "printing", "stopping", "completed") and r["queue_seq"] is None:
            errors.append("missing queue identity: " + r["id"])
    return errors
