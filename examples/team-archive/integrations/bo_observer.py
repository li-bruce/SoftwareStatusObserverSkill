"""Pinned observer adapter; removing this layer leaves the business package intact."""
import json
from pathlib import Path
import threading
from archive_app.ports import TracePort
from observer_runtime.semantic_probe import Pins, Trace
from observer_runtime.bo_retention import EventHistory
from bo_stategraph import BOStateGraph


class BOObserver:
    def __init__(self, model: dict, build_id: str, mode: str = "on", path: str | None = None,
                 capacity: int = 8192):
        self.mode, self.path = mode, Path(path) if path else None
        # Structure/query/export remain available even if event collection is off.
        self.bo_graph = BOStateGraph(model, build_id=build_id, mode="drive")
        self.lock = threading.Lock()
        self.events = EventHistory(project_root=Path(__file__).resolve().parents[1],path=self.path)
        self.pins = Pins(model,build_id,enabled=mode=="on",sink=self.write,capacity=capacity)

    def write(self, text: str) -> None:
        event = json.loads(text)
        with self.lock:
            self.events.append(event)
    def trace(self, entity: str, attempt: str) -> TracePort:
        if self.mode=="fault":
            def broken(*args, **kwargs):
                raise RuntimeError("injected observer failure")
            return TracePort(broken)
        return TracePort(Trace(self.pins,entity,attempt).record) if self.mode=="on" else TracePort()

    def snapshot(self) -> list[dict]:
        self.pins.flush()
        with self.lock:
            return self.events.snapshot()

    def health(self) -> dict:
        return {**self.pins.health(),**self.events.health(),"mode":self.mode,
                "evidence":"gap" if self.mode!="on" or self.pins.errors or self.pins.dropped else "available"}

    def close(self) -> None:
        self.pins.close()
