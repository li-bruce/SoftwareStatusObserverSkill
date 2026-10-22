"""Synthetic scenarios; expected results live separately in acceptance.json."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
import json
import math
from pathlib import Path
import sqlite3
import threading
import uuid
from app.checks import check_size, check_material
from app.policy import grant_matches
from app.ports import EventPort
from app.store import Store
from bo_stategraph import BOStateGraph, validate_instances
from bo_stategraph.workflow import Workflow
from integrations.bo_capture import BOCapture

ROOT = Path(__file__).resolve().parents[1]

class Lab:
    def __init__(self, case, mode, model, manifest):
        self.now = 100.0
        path = ROOT / ".test-data" / (case + "-" + mode + "-" + uuid.uuid4().hex + ".sqlite")
        self.store = Store(str(path), json.loads((ROOT / "config/printers.json").read_text()))
        self.capture = BOCapture(model, manifest["build_id"], mode)
        self.port = EventPort(self.capture.bo_record if mode != "off" else None)
        self.w = Workflow(self.store, self.port, lambda: self.now)
        self.graph = BOStateGraph(self.store)
        for actor in ("bob", "carol"):
            for printer in ("P1", "P2"):
                self.w.set_role(actor, printer, True)

    def submit(self, printer="P1", dimensions=None, material="PLA", parameters=None, task_id=None):
        return self.w.submit("alice", printer, [20, 20, 20] if dimensions is None else dimensions, material, {} if parameters is None else parameters, task_id)

    def approve(self, run, actor="bob", expires=500):
        return self.w.approve(run, actor, expires)

    def row(self, run):
        return next(r for r in self.store.snapshot()["runs"] if r["id"] == run)

    def state(self, run):
        return self.row(run)["state"]

    def owner(self, printer="P1"):
        return next(p["occupant"] for p in self.store.snapshot()["printers"] if p["id"] == printer)

def scenario(case, lab):
    w = lab.w
    if case == "policy":
        run = {"task_id": "T", "printer_id": "P1", "version": 2, "submitter": "alice"}
        grant = {"task_id": "T", "printer_id": "P1", "version": 2, "approver": "bob", "expires": 200, "revoked": 0}
        return {"matching": grant_matches(grant, run, True, 100)["eligible"], "self_approval": grant_matches({**grant, "approver": "alice"}, run, True, 100)["eligible"], "old_version": grant_matches({**grant, "version": 1}, run, True, 100)["eligible"], "wrong_task": grant_matches({**grant, "task_id": "other"}, run, True, 100)["eligible"], "wrong_printer": grant_matches({**grant, "printer_id": "P2"}, run, True, 100)["eligible"], "missing_role": grant_matches(grant, run, False, 100)["eligible"], "expired": grant_matches(grant, run, True, 200)["eligible"], "revoked": grant_matches({**grant, "revoked": 1}, run, True, 100)["eligible"]}
    if case == "happy":
        a, b = lab.submit(), lab.submit()
        lab.approve(a); lab.approve(b)
        waiting = lab.state(b)
        w.confirm(a, "complete")
        resumed = lab.state(b)
        w.confirm(b, "complete")
        count = len(lab.store.snapshot()["effects"])
        w.confirm(b, "complete")
        return {"waiting": waiting, "resumed": resumed, "finished": lab.state(b), "released": lab.owner() is None, "duplicate_no_effect": len(lab.store.snapshot()["effects"]) == count, "same_submitter_two_runs": len(lab.store.snapshot()["runs"])}
    if case == "approval_paths":
        a, b, c, d = [lab.submit() for _ in range(4)]
        lab.approve(a); gb = lab.approve(b); gc = lab.approve(b, "carol"); lab.approve(c); lab.approve(d)
        original = lab.row(b)["queue_seq"]
        w.revoke(gb)
        alternative = lab.state(b)
        w.set_role("carol", "P1", False)
        blocked = lab.state(b)
        w.confirm(a, "complete")
        bypass = lab.owner() == c
        w.set_role("carol", "P1", True)
        restored = lab.row(b)["queue_seq"] == original and lab.state(b) == "queued"
        w.confirm(c, "complete")
        priority = lab.owner() == b
        w.revoke(gc)
        return {"alternative": alternative, "blocked": blocked, "bypass": bypass, "restored_position": restored, "original_priority": priority, "printing_survives_revoke": lab.state(b)}
    if case == "expiry":
        a, b = lab.submit(), lab.submit()
        lab.approve(a); lab.approve(b, expires=110)
        lab.now = 110
        w.confirm(a, "complete")
        expired = lab.state(b)
        owner = lab.owner()
        lab.approve(b, "carol", 200)
        return {"at_deadline": expired, "no_start": owner is None, "new_approval_resumes": lab.state(b)}
    if case == "expiry_window":
        b = lab.submit()
        # Admission sees 109, final pre-start check sees exact expiration 110.
        times = iter([109.0, 109.0, 110.0])
        w.clock = lambda: next(times, 110.0)
        lab.approve(b, expires=110)
        return {"state": lab.state(b), "owner_empty": lab.owner() is None}
    if case == "version_waiting":
        a, b = lab.submit(), lab.submit()
        lab.approve(a); lab.approve(b)
        task = lab.row(b)["task_id"]
        new = lab.submit(dimensions=[21, 20, 20], task_id=task)
        old_state, new_state = lab.state(b), lab.state(new)
        w.confirm(a, "complete")
        not_started = lab.owner() is None
        lab.approve(new)
        return {"old": old_state, "new_before_approval": new_state, "old_approval_not_reused": not_started, "new_after_approval": lab.state(new), "new_version": lab.row(new)["version"]}
    if case == "version_printing":
        old = lab.submit(); lab.approve(old)
        new = lab.submit(parameters={"layer_mm": 0.3}, task_id=lab.row(old)["task_id"])
        lab.approve(new)
        old_kept = lab.state(old)
        w.cancel(old)
        before_confirm = lab.owner() == old and lab.state(old) == "stopping" and lab.state(new) == "queued"
        w.confirm(old, "stop")
        return {"old_kept": old_kept, "waits_for_stop": before_confirm, "old_cancelled": lab.state(old), "new_unaffected": lab.state(new), "new_owns": lab.owner() == new}
    if case == "cancel_other_run":
        old = lab.submit(); lab.approve(old)
        new = lab.submit(material="ABS", task_id=lab.row(old)["task_id"])
        w.cancel(new)
        return {"new_cancelled": lab.state(new), "old_unaffected": lab.state(old), "old_owns": lab.owner() == old}
    if case == "size_boundaries":
        values = [[200, 200, 200], [200.01, 1, 1], [0, 1, 1], [-1, 1, 1], [float("inf"), 1, 1], [float("nan"), 1, 1], [True, 1, 1], ["2", 1, 1], [1, 2]]
        ids = [lab.submit(dimensions=value) for value in values]
        return {"states": [lab.state(r) for r in ids], "specific_failures": all(next(a for a in lab.store.snapshot()["activities"] if a["run_id"] == r and a["name"] == "size")["result"]["failures"] for r in ids[1:]), "no_occupancy": lab.owner() is None}
    if case == "materials":
        a = lab.submit(material="ABS"); b = lab.submit(printer="P2", material="ABS"); c = lab.submit(printer="P2", material="PETG")
        return {"states": [lab.state(r) for r in (a, b, c)]}
    if case == "check_error":
        def broken(*args):
            raise RuntimeError("simulated material checker failure")
        w.check_functions["material"] = broken
        run = lab.submit()
        act = next(a for a in lab.store.snapshot()["activities"] if a["run_id"] == run and a["name"] == "material")
        return {"state": lab.state(run), "error_type": act["result"].get("error_type"), "message": act["result"].get("error"), "owner_empty": lab.owner() is None}
    if case == "parallel":
        barrier = threading.Barrier(2)
        def size(*args):
            barrier.wait(5)
            return check_size(*args)
        def material(*args):
            barrier.wait(5)
            return check_material(*args)
        w.check_functions = {"size": size, "material": material}
        run = lab.submit()
        acts = [a for a in lab.store.snapshot()["activities"] if a["run_id"] == run]
        return {"state": lab.state(run), "overlap": max(a["started"] for a in acts) < min(a["ended"] for a in acts)}
    if case == "concurrent_dispatch":
        a, b = lab.submit(), lab.submit()
        # Independently insert two valid approvals in one transaction, then race real dispatchers.
        def grants(c):
            for r in (a, b):
                row = c.execute("SELECT * FROM runs WHERE id=?", (r,)).fetchone()
                c.execute("INSERT INTO approvals VALUES(?,?,?,?,?,?,0)", (r, row["task_id"], row["version"], "P1", "bob", 500))
        lab.store.change("fixture_two_approvals", grants)
        barrier = threading.Barrier(2)
        def start():
            other = Workflow(lab.store, lab.port, lambda: lab.now)
            barrier.wait(5)
            return other.schedule()
        with ThreadPoolExecutor(max_workers=2) as pool:
            list(pool.map(lambda _: start(), range(2)))
        snap = lab.store.snapshot()
        return {"printing_count": sum(r["state"] == "printing" for r in snap["runs"]), "start_effects": sum(e["kind"] == "start" for e in snap["effects"]), "waiting_count": sum(r["state"] == "queued" for r in snap["runs"])}
    if case == "two_printers":
        a, b = lab.submit(), lab.submit(printer="P2", material="ABS")
        lab.approve(a); lab.approve(b)
        return {"printing_count": sum(r["state"] == "printing" for r in lab.store.snapshot()["runs"]), "distinct_owners": len(set(p["occupant"] for p in lab.store.snapshot()["printers"]))}
    if case == "restart":
        a, b = lab.submit(), lab.submit()
        lab.approve(a); lab.approve(b)
        w.cancel(a)
        fresh = Workflow(Store(lab.store.path, []), lab.port, lambda: lab.now)
        preserved = lab.owner() == a
        fresh.confirm(a, "stop")
        return {"ownership_persisted": preserved, "next_started": lab.state(b)}
    if case == "api_rejections":
        run = lab.submit()
        rejected = []
        for actor in ("alice", "unknown"):
            try: w.approve(run, actor, 500)
            except PermissionError: rejected.append(actor)
        lab.approve(run)
        try: w.confirm(run, "stop")
        except ValueError: rejected.append("unrequested_stop")
        return {"rejected": rejected, "still_printing": lab.state(run)}
    raise KeyError(case)

CASES = ["policy", "happy", "approval_paths", "expiry", "expiry_window", "version_waiting", "version_printing", "cancel_other_run", "size_boundaries", "materials", "check_error", "parallel", "concurrent_dispatch", "two_printers", "restart", "api_rejections"]

def run_all(model, manifest, modes=("on", "off", "fault")):
    runs, mapping, state_checks = [], [], []
    for mode in modes:
        for case in CASES:
            lab = Lab(case, mode, model, manifest)
            result = scenario(case, lab)
            instances = lab.graph.bo_instances()
            # Independently query SQLite rather than copying the graph projection as truth.
            with closing(sqlite3.connect(lab.store.path)) as c:
                actual = [list(row) for row in c.execute("SELECT id,state,version,queue_seq,printer_id,reason FROM runs ORDER BY id")]
            mapped = sorted([[r["id"], r["state"], r["version"], r["queue_seq"], r["printer_id"], r["reason"]] for r in instances])
            mapping.append({"id": case + ":" + mode, "source": "direct SQLite SELECT in tests/scenarios.py", "projection": "BOStateGraph.bo_instances", "actual": actual, "mapped": mapped})
            with closing(sqlite3.connect(lab.store.path)) as c:
                actual_params = [[r[0], json.loads(r[1]), r[2], json.loads(r[3])] for r in c.execute("SELECT id,dimensions,material,parameters FROM runs ORDER BY id")]
                actual_printers = [list(r) for r in c.execute("SELECT id,occupant FROM printers ORDER BY id")]
                actual_effects = [r[0] for r in c.execute("SELECT id FROM effects ORDER BY id")]
                actual_activities = [[r[0], r[1], r[2], json.loads(r[3]) if r[3] else None] for r in c.execute("SELECT run_id,name,state,result FROM activities ORDER BY run_id,name")]
            mapped_params = sorted([[r["id"], r["parameters"]["dimensions"], r["parameters"]["material"], r["parameters"]["printing"]] for r in instances])
            mapped_activities = sorted([[r["id"], a["name"], a["state"], a["result"]] for r in instances for a in r["activities"]])
            # Non-finite invalid inputs are preserved as explicit text in the mapping witness.
            def normalized(value):
                if isinstance(value, float) and not math.isfinite(value):
                    return {"invalid_number": str(value)}
                if isinstance(value, list):
                    return [normalized(item) for item in value]
                if isinstance(value, dict):
                    return {key: normalized(item) for key, item in value.items()}
                return value
            for name, truth, projection in [("parameters", normalized(actual_params), normalized(mapped_params)), ("activities", actual_activities, mapped_activities), ("resources", actual_printers, sorted([[p["id"], p["occupant"]] for p in lab.graph.bo_export()["resources"]]))]:
                mapping.append({"id": case + ":" + mode + ":" + name, "source": "independent direct SQLite query", "projection": "BOStateGraph." + name, "actual": truth, "mapped": projection})
            if mode == "on":
                observed_effects = sorted(e["outputs"]["effect_id"] for e in lab.capture.events if e["node"] in ("printing", "printer-stopped") and e["phase"] == "commit" and "effect_id" in e["outputs"])
                mapping.append({"id": case + ":" + mode + ":effects", "source": "independent effects table query", "projection": "commit probe effect_id", "actual": actual_effects, "mapped": observed_effects})
            errors = []
            for frame in lab.store.history():
                errors.extend({"revision": frame["revision"], "error": e} for e in validate_instances(frame["snapshot"]))
            state_checks.append({"case": case, "mode": mode, "errors": errors, "frames": len(lab.store.history())})
            result["state_constraints"] = not errors
            runs.append({"case": case, "mode": mode, "observations": result, "events": lab.capture.events, "health": {**lab.capture.bo_health(), "port_errors": lab.port.errors}})
    return {"build_id": manifest["build_id"], "machine": BOStateGraph(lab.store).bo_definition(), "runs": runs, "mapping_checks": mapping, "shared_resource_checks": state_checks}
