"""Selected core events, bounded memory and explicit gaps; no domain decisions."""
from datetime import datetime, timezone
import json
from pathlib import Path
import threading
import uuid
from observer_runtime.semantic_probe import selected

class BOCapture:
    def __init__(self, model, build_id, mode="on", capacity=8000, path=None):
        self.model, self.build_id, self.mode = model, build_id, mode
        self.nodes = {n["id"]: n for n in model["nodes"]}
        self.capacity, self.path = capacity, Path(path) if path else None
        self.events, self.errors, self.dropped, self.seq = [], 0, 0, 0
        self.producer = uuid.uuid4().hex[:12]
        self.lock = threading.RLock()

    def bo_record(self, node, phase, context, payload):
        if self.mode == "off":
            return
        with self.lock:
            if self.mode == "fault":
                self.errors += 1
                raise OSError("injected observation sink failure")
            spec = self.nodes[node]["capture"]
            self.seq += 1
            event = {"schema_version": 3, "id": f"{self.producer}:{self.seq}", "seq": self.seq, "run_id": self.producer, "attempt": context["attempt"], "entity": context["entity"], "call_id": context["call_id"], "parent_call_id": None, "build_id": self.build_id, "model_revision": self.model["revision"], "node": node, "phase": phase, "basis": {"param_version": context["param_version"], "epoch": context["revision"], "clock": payload.get("inputs", {}).get("clock")}, "revision": context["revision"], "inputs": selected(payload.get("inputs", {}), spec["in"]), "outputs": selected(payload.get("outputs", {}), spec["out"]), "depends": [], "observed_at": datetime.now(timezone.utc).isoformat()}
            if len(self.events) >= self.capacity:
                self.events.pop(0)
                self.dropped += 1
            self.events.append(event)
            if self.path:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                if self.path.exists() and self.path.stat().st_size > 4 * 1024 * 1024:
                    self.path.replace(self.path.with_suffix(".previous.jsonl"))
                with self.path.open("a", encoding="utf-8") as stream:
                    stream.write(json.dumps(event, ensure_ascii=False, allow_nan=False) + "\n")

    def bo_health(self):
        return {"enabled": self.mode != "off", "mode": self.mode, "errors": self.errors, "dropped": self.dropped, "retained": len(self.events), "collector": "synchronous callback; no separate process", "gaps": bool(self.errors or self.dropped)}
