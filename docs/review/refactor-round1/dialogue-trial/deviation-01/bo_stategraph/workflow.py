"""Project executor: parallel checks and transactionally exclusive printer dispatch."""
from concurrent.futures import ThreadPoolExecutor
import json
import math
import time
import uuid
from app.checks import check_size, check_material
from app.policy import grant_matches
from app.ports import EventPort
from bo_stategraph.declaration import transition

class Workflow:
    def __init__(self, store, events=None, clock=None, check_functions=None):
        self.store = store
        self.events = events or EventPort()
        self.clock = clock or time.time
        self.check_functions = check_functions or {"size": check_size, "material": check_material}

    def _emit(self, node, phase, receipt, run_id, builder, call_id=None):
        if self.events.callback is None:
            return
        try:
            run = next((r for r in receipt[2]["runs"] if r["id"] == run_id), None)
            context = {"revision": receipt[1], "attempt": run_id or "administration", "entity": run["task_id"] if run else "studio", "param_version": run["version"] if run else 0, "call_id": call_id or uuid.uuid4().hex}
            self.events.bo_emit(node, phase, context, builder)
        except Exception:
            self.events.errors += 1

    def submit(self, submitter: str, printer_id: str, dimensions: list, material: str, parameters: dict, task_id=None) -> str:
        task_id = task_id or uuid.uuid4().hex[:10]
        run_id = uuid.uuid4().hex[:12]
        def create(c):
            if not c.execute("SELECT 1 FROM printers WHERE id=?", (printer_id,)).fetchone():
                raise ValueError("unknown printer")
            old = c.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
            if old:
                if old["submitter"] != submitter:
                    raise PermissionError("only original submitter may change parameters")
                latest = c.execute("SELECT * FROM runs WHERE task_id=? AND version=?", (task_id, old["version"])).fetchone()
                if latest["printer_id"] != printer_id:
                    raise ValueError("printer reassignment is outside this version operation")
                if json.loads(latest["dimensions"]) == dimensions and latest["material"] == material and json.loads(latest["parameters"]) == parameters:
                    return {"run_id": latest["id"], "unchanged": True}
                version = old["version"] + 1
                for row in c.execute("SELECT id,state FROM runs WHERE task_id=?", (task_id,)).fetchall():
                    if row["state"] in ("checking", "awaiting_approval", "queued", "blocked", "check_failed", "check_error"):
                        transition(c, row["id"], "invalidate")
                        c.execute("UPDATE runs SET reason='new_version' WHERE id=?", (row["id"],))
                c.execute("UPDATE tasks SET version=? WHERE id=?", (version, task_id))
            else:
                version = 1
                c.execute("INSERT INTO tasks VALUES(?,?,?)", (task_id, submitter, version))
            c.execute("INSERT INTO runs VALUES(?,?,?,?,?,?,?,?,?,?,?)", (run_id, task_id, version, submitter, printer_id, json.dumps(dimensions), material, json.dumps(parameters, allow_nan=False, sort_keys=True), "checking", None, "checks_pending"))
            c.executemany("INSERT INTO activities(run_id,name,state) VALUES(?,?,'pending')", [(run_id, "size"), (run_id, "material")])
            return {"run_id": run_id, "unchanged": False, "version": version}
        receipt = self.store.change("submit_or_revise", create)
        actual_id = receipt[0]["run_id"]
        self._emit("submit", "commit", receipt, actual_id, lambda: {"inputs": {"printer_id": printer_id, "dimensions": json.dumps(dimensions), "material": material, "parameters": json.dumps(parameters, sort_keys=True)}, "outputs": receipt[0]})
        if not receipt[0]["unchanged"]:
            self.run_checks(actual_id)
        return actual_id

    def _check(self, run_id: str, name: str) -> dict:
        call_id = uuid.uuid4().hex
        def start(c):
            c.execute("UPDATE activities SET state='running',started=? WHERE run_id=? AND name=?", (time.monotonic(), run_id, name))
        receipt = self.store.change("check_start:" + name, start)
        run = next(r for r in receipt[2]["runs"] if r["id"] == run_id)
        printer = next(p for p in receipt[2]["printers"] if p["id"] == run["printer_id"])
        args = (run["dimensions"], printer["limits"]) if name == "size" else (run["material"], printer["materials"])
        function = self.check_functions[name]
        default_function = check_size if name == "size" else check_material
        probe_node = "check-" + name if function is default_function else "check-worker"
        self._emit(probe_node, "enter", receipt, run_id, lambda: {"inputs": {"value": json.dumps(args[0]), "capability": json.dumps(args[1]), "implementation": function.__module__ + "." + function.__qualname__}, "outputs": {}}, call_id)
        try:
            result = function(*args)
            state = "passed" if result["passed"] else "failed"
        except Exception as exc:
            result = {"passed": False, "failures": [], "error_type": type(exc).__name__, "error": str(exc)[:200]}
            state = "error"
        def finish(c):
            c.execute("UPDATE activities SET state=?,result=?,ended=? WHERE run_id=? AND name=?", (state, json.dumps(result), time.monotonic(), run_id, name))
        receipt = self.store.change("check_finish:" + name, finish)
        self._emit(probe_node, "error" if state == "error" else "return", receipt, run_id, lambda: {"inputs": {"value": json.dumps(args[0]), "capability": json.dumps(args[1]), "implementation": function.__module__ + "." + function.__qualname__}, "outputs": {**result, "activity_state": state}}, call_id)
        return result

    def run_checks(self, run_id: str):
        with ThreadPoolExecutor(max_workers=2, thread_name_prefix="printer-check") as pool:
            futures = [pool.submit(self._check, run_id, name) for name in ("size", "material")]
            for future in futures:
                future.result()
        def join(c):
            run = c.execute("SELECT * FROM runs WHERE id=?", (run_id,)).fetchone()
            activities = [dict(a) for a in c.execute("SELECT * FROM activities WHERE run_id=? ORDER BY name", (run_id,))]
            if run["state"] != "checking":
                return {"state": run["state"], "passed": False, "reason": "run_no_longer_current"}
            states = [a["state"] for a in activities]
            trigger = "checks_error" if "error" in states else "checks_passed" if states == ["passed", "passed"] else "checks_failed"
            state = transition(c, run_id, trigger)
            c.execute("UPDATE runs SET reason=? WHERE id=?", ("approval_required" if trigger == "checks_passed" else trigger, run_id))
            return {"state": state, "passed": trigger == "checks_passed", "size": next(a["state"] for a in activities if a["name"] == "size"), "material": next(a["state"] for a in activities if a["name"] == "material")}
        receipt = self.store.change("check_join", join)
        self._emit("checks", "decision", receipt, run_id, lambda: {"inputs": {}, "outputs": receipt[0]})
        self.schedule()

    def set_role(self, actor: str, printer_id: str, active: bool):
        receipt = self.store.change("role_change", lambda c: c.execute("INSERT INTO roles VALUES(?,?,?) ON CONFLICT(actor,printer_id) DO UPDATE SET active=excluded.active", (actor, printer_id, int(active))) and None)
        self._emit("approval-change", "change", receipt, None, lambda: {"inputs": {"actor": actor, "printer_id": printer_id, "active": active}, "outputs": {}})
        self.schedule()

    def approve(self, run_id: str, approver: str, expires: float) -> str:
        if type(expires) not in (int, float) or not math.isfinite(expires):
            raise ValueError("expiry must be finite")
        approval_id = uuid.uuid4().hex[:12]
        def add(c):
            run = c.execute("SELECT * FROM runs WHERE id=?", (run_id,)).fetchone()
            if run is None:
                raise ValueError("unknown run")
            role = c.execute("SELECT active FROM roles WHERE actor=? AND printer_id=?", (approver, run["printer_id"])).fetchone()
            if approver == run["submitter"] or not role or not role[0]:
                raise PermissionError("self approval or missing printer role")
            if expires <= self.clock():
                raise ValueError("approval already expired")
            c.execute("INSERT INTO approvals VALUES(?,?,?,?,?,?,0)", (approval_id, run["task_id"], run["version"], run["printer_id"], approver, expires))
            return {"approval_id": approval_id, "expires": expires}
        receipt = self.store.change("approve", add)
        self._emit("approval-change", "commit", receipt, run_id, lambda: {"inputs": {"actor": approver, "expires": expires}, "outputs": receipt[0]})
        self.schedule()
        return approval_id

    def revoke(self, approval_id: str):
        def change(c):
            if c.execute("UPDATE approvals SET revoked=1 WHERE id=?", (approval_id,)).rowcount != 1:
                raise ValueError("unknown approval")
        receipt = self.store.change("revoke", change)
        self._emit("approval-change", "change", receipt, None, lambda: {"inputs": {"approval_id": approval_id}, "outputs": {"revoked": True}})
        self.schedule()

    def _authorization(self, c, run: dict, now: float) -> dict:
        # Read all task candidates, including mismatching version/printer evidence.
        candidates = []
        for row in c.execute("SELECT * FROM approvals WHERE task_id=? ORDER BY rowid", (run["task_id"],)):
            grant = dict(row)
            role = c.execute("SELECT active FROM roles WHERE actor=? AND printer_id=?", (grant["approver"], run["printer_id"])).fetchone()
            flags = grant_matches(grant, run, bool(role and role[0]), now)
            candidates.append({"id": grant["id"], "version": grant["version"], "expires": grant["expires"], "printer_id": grant["printer_id"], "task_id": grant["task_id"], "approver": grant["approver"], **flags})
        return {"allowed": any(g["eligible"] for g in candidates), "candidates": candidates, "clock": now, "version": run["version"]}

    def schedule(self):
        def dispatch(c):
            decisions, starts = [], []
            for row in c.execute("SELECT * FROM runs WHERE state IN ('awaiting_approval','queued','blocked') ORDER BY rowid").fetchall():
                run = dict(row)
                auth = self._authorization(c, run, self.clock())
                decisions.append({"run_id": run["id"], **auth})
                if auth["allowed"] and run["state"] == "awaiting_approval":
                    c.execute("UPDATE counters SET value=value+1 WHERE name='queue'")
                    seq = c.execute("SELECT value FROM counters WHERE name='queue'").fetchone()[0]
                    transition(c, run["id"], "admit")
                    c.execute("UPDATE runs SET queue_seq=?,reason='printer_busy' WHERE id=?", (seq, run["id"]))
                elif auth["allowed"] and run["state"] == "blocked":
                    transition(c, run["id"], "restore_approval")
                    c.execute("UPDATE runs SET reason='printer_busy' WHERE id=?", (run["id"],))
                elif not auth["allowed"] and run["state"] == "queued":
                    transition(c, run["id"], "lose_approval")
                    c.execute("UPDATE runs SET reason='no_valid_approval' WHERE id=?", (run["id"],))
            for printer in c.execute("SELECT * FROM printers WHERE occupant IS NULL ORDER BY id").fetchall():
                for row in c.execute("SELECT * FROM runs WHERE printer_id=? AND state='queued' ORDER BY queue_seq", (printer["id"],)).fetchall():
                    run = dict(row)
                    # Re-read time and authorization immediately before claiming the device, inside the same writer transaction.
                    auth = self._authorization(c, run, self.clock())
                    decisions.append({"run_id": run["id"], **auth})
                    if not auth["allowed"]:
                        transition(c, run["id"], "lose_approval")
                        c.execute("UPDATE runs SET reason='no_valid_approval' WHERE id=?", (run["id"],))
                        continue
                    transition(c, run["id"], "start")
                    c.execute("UPDATE printers SET occupant=? WHERE id=?", (run["id"], printer["id"]))
                    c.execute("UPDATE runs SET reason='' WHERE id=?", (run["id"],))
                    effect = c.execute("INSERT INTO effects(run_id,kind,printer_id,clock) VALUES(?,'start',?,?)", (run["id"], printer["id"], auth["clock"])).lastrowid
                    starts.append({"run_id": run["id"], "printer_id": printer["id"], "effect_id": effect, "clock": auth["clock"], "state": "printing"})
                    break
            return {"decisions": decisions, "starts": starts}
        receipt = self.store.change("schedule", dispatch)
        for decision in receipt[0]["decisions"]:
            self._emit("approval", "decision", receipt, decision["run_id"], lambda d=decision: {"inputs": {"clock": d["clock"], "version": d["version"]}, "outputs": d})
            for candidate in decision["candidates"]:
                self._emit("grant-match", "decision", receipt, decision["run_id"], lambda d=decision, g=candidate: {"inputs": {"clock": d["clock"], "run_version": d["version"], "grant_version": g["version"], "expires": g["expires"], "printer_id": g["printer_id"], "task_id": g["task_id"], "approver": g["approver"]}, "outputs": g})
        for start in receipt[0]["starts"]:
            self._emit("printing", "commit", receipt, start["run_id"], lambda s=start: {"inputs": {"clock": s["clock"]}, "outputs": s})
        for run in receipt[2]["runs"]:
            if run["state"] in ("awaiting_approval", "queued", "blocked"):
                self._emit("queue", "wait", receipt, run["id"], lambda r=run: {"inputs": {"printer_id": r["printer_id"]}, "outputs": {"state": r["state"], "reason": r["reason"], "queue_seq": r["queue_seq"]}})
        return receipt[0]

    def cancel(self, run_id: str):
        def request(c):
            run = c.execute("SELECT * FROM runs WHERE id=?", (run_id,)).fetchone()
            if not run:
                raise ValueError("unknown run")
            if run["state"] == "printing":
                state = transition(c, run_id, "cancel_print")
                c.execute("UPDATE runs SET reason='device_stop_confirmation' WHERE id=?", (run_id,))
            elif run["state"] in ("stopping", "completed", "cancelled", "superseded"):
                state = run["state"]
            else:
                state = transition(c, run_id, "cancel_pending")
                c.execute("UPDATE runs SET reason='' WHERE id=?", (run_id,))
            return {"state": state}
        receipt = self.store.change("cancel_run", request)
        self._emit("cancel", "commit", receipt, run_id, lambda: {"inputs": {"run_id": run_id}, "outputs": receipt[0]})
        self.schedule()

    def confirm(self, run_id: str, kind: str):
        if kind not in ("complete", "stop"):
            raise ValueError("unknown device confirmation")
        def release(c):
            run = c.execute("SELECT * FROM runs WHERE id=?", (run_id,)).fetchone()
            if not run:
                raise ValueError("unknown run")
            if run["state"] in ("completed", "cancelled"):
                return {"state": run["state"], "duplicate": True}
            printer = c.execute("SELECT * FROM printers WHERE id=?", (run["printer_id"],)).fetchone()
            if printer["occupant"] != run_id:
                raise ValueError("confirmation does not match device occupant")
            state = transition(c, run_id, "complete_confirmed" if kind == "complete" else "stop_confirmed")
            c.execute("UPDATE printers SET occupant=NULL WHERE id=? AND occupant=?", (run["printer_id"], run_id))
            c.execute("UPDATE runs SET reason='' WHERE id=?", (run_id,))
            effect = c.execute("INSERT INTO effects(run_id,kind,printer_id,clock) VALUES(?,?,?,?)", (run_id, kind, run["printer_id"], self.clock())).lastrowid
            return {"state": state, "duplicate": False, "effect_id": effect, "printer_id": run["printer_id"], "released": True}
        receipt = self.store.change("device_" + kind, release)
        self._emit("printer-stopped", "commit", receipt, run_id, lambda: {"inputs": {"kind": kind}, "outputs": receipt[0]})
        self.schedule()
