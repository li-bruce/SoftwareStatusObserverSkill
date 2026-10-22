"""Application composition and read-only graph projections for CLI/HTTP."""
import copy
import json
from pathlib import Path
import threading
import time
import uuid
from app.store import Store
from app.ports import EventPort
from bo_stategraph import BOStateGraph
from bo_stategraph.workflow import Workflow
from observer_runtime.behavior_model import capture, check
from integrations.bo_capture import BOCapture

ROOT = Path(__file__).resolve().parents[1]

class BOApplication:
    def __init__(self, database, mode="on"):
        self.model = json.loads((ROOT / "behavior.json").read_text(encoding="utf-8"))
        self.manifest = capture(ROOT, self.model)
        self.sources = {p: (ROOT / p).read_text(encoding="utf-8-sig") for p in self.model["source_files"]}
        self.store = Store(str(database), json.loads((ROOT / "config/printers.json").read_text()))
        self.collector = BOCapture(self.model, self.manifest["build_id"], mode, path=ROOT / "data/events.jsonl")
        self.port = EventPort(self.collector.bo_record if mode != "off" else None)
        self.workflow = Workflow(self.store, self.port)
        self.graph = BOStateGraph(self.store)
        self.lock = threading.RLock()
        self.recording = None
        self.recordings_dir = ROOT / "data/recordings"
        self.recordings_dir.mkdir(parents=True, exist_ok=True)
        self.view_file = ROOT / "bo_stategraph/config/views/local.json"
        if not self.view_file.exists():
            self.view_file.parent.mkdir(parents=True, exist_ok=True)
            self.view_file.write_text(json.dumps({"revision": 0, "positions": {}, "expanded": [], "labels": {}, "notes": {}, "core": [], "type": "all", "edge_type": "all", "search": ""}), encoding="utf-8")
        self.expired_seen = set()

    def bo_view(self):
        with self.lock:
            history = self.store.history()
            snap = history[-1]["snapshot"] if history else self.store.snapshot()
            events = copy.deepcopy(self.collector.events)
            return {"model": self.model, "manifest": self.manifest, "binding_status": check(ROOT, self.model, self.manifest), "instances": self.graph.bo_instances(snap), "snapshot": snap, "history": history, "events": events, "health": {**self.collector.bo_health(), "port_errors": self.port.errors}, "layout_id": "studio-print-trial", "recording": self.recording["id"] if self.recording else None, "scope": "本地模拟设备；只读运行图。选择历史时刻只展示当时已提交事实。"}

    def bo_preferences(self, value=None):
        with self.lock:
            current = json.loads(self.view_file.read_text())
            if value is None:
                return current
            if value.get("revision") != current["revision"]:
                raise RuntimeError("preference_revision_conflict")
            updated = {**value, "revision": current["revision"] + 1}
            temporary = self.view_file.with_suffix(".tmp")
            temporary.write_text(json.dumps(updated, ensure_ascii=False), encoding="utf-8")
            temporary.replace(self.view_file)
            return updated

    def bo_record(self, action):
        with self.lock:
            if action == "start":
                if self.recording:
                    return {"id": self.recording["id"]}
                view = self.bo_view()
                self.recording = {"id": uuid.uuid4().hex[:12], "initial": view, "start_seq": self.collector.seq, "sources": self.sources, "status": "recording"}
                return {"id": self.recording["id"]}
            if not self.recording:
                raise ValueError("no active recording")
            record = self.recording
            final = self.bo_view()
            events = [e for e in final["events"] if e["seq"] > record["start_seq"]]
            record.update(final=final, events=events[:20000], status="saved", gap=bool(final["health"]["gaps"] or self.port.errors or len(events) > 20000), capture_scope="core probes; display filtering does not change capture")
            path = self.recordings_dir / (record["id"] + ".json")
            temporary = path.with_suffix(".tmp")
            temporary.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")
            temporary.replace(path)
            self.recording = None
            return {"id": record["id"], "events": len(events), "gap": record["gap"]}

    def bo_command(self, command):
        # Local operator CLI/API; graph view never calls this endpoint.
        with self.lock:
            name = command.pop("command")
            methods = {"submit": self.workflow.submit, "approve": self.workflow.approve, "revoke": self.workflow.revoke, "role": self.workflow.set_role, "cancel": self.workflow.cancel, "confirm": self.workflow.confirm, "schedule": self.workflow.schedule}
            if name not in methods:
                raise ValueError("unknown command")
            return {"result": methods[name](**command)}

    def bo_tick(self):
        with self.lock:
            now = time.time()
            expired = {a["id"] for a in self.store.snapshot()["approvals"] if not a["revoked"] and a["expires"] <= now}
            if expired - self.expired_seen:
                self.workflow.schedule()
            self.expired_seen = expired

    def bo_demo(self):
        if self.store.snapshot()["runs"]:
            return {"existing": True}
        self.bo_record("start")
        w = self.workflow
        for actor in ("bob", "carol"):
            for printer in ("P1", "P2"):
                w.set_role(actor, printer, True)
        end = time.time() + 7200
        a = w.submit("alice", "P1", [120, 90, 60], "PLA", {"layer_mm": 0.2}, "任务-A")
        b = w.submit("alice", "P1", [80, 70, 50], "PLA", {"layer_mm": 0.2}, "任务-B")
        c = w.submit("dana", "P1", [50, 50, 50], "PLA", {}, "任务-C")
        w.approve(a, "bob", end)
        first = w.approve(b, "bob", end)
        w.approve(b, "carol", end)
        w.approve(c, "bob", end)
        w.revoke(first)
        w.set_role("carol", "P1", False)
        w.confirm(a, "complete")
        w.set_role("carol", "P1", True)
        w.confirm(c, "complete")
        new = w.submit("alice", "P1", [90, 70, 50], "PLA", {"layer_mm": 0.25}, "任务-B")
        w.approve(new, "bob", end)
        w.cancel(b)
        w.confirm(b, "stop")
        p2 = w.submit("dana", "P2", [250, 200, 100], "ABS", {}, "任务-D")
        w.approve(p2, "carol", end)
        w.confirm(new, "complete")
        record = self.bo_record("stop")
        info = {"runs": {"A": a, "B1": b, "B2": new, "C": c, "D": p2}, "recording": record["id"], "meaning": "Actual synthetic function calls persisted in SQLite; not fabricated events or real printer execution"}
        (ROOT / "data/demo.json").write_text(json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8")
        return info
