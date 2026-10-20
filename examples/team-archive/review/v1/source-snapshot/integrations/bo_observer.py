"""Pinned observer adapter; removing this layer leaves the business package intact."""
import json
from pathlib import Path
import threading
from archive_app.ports import TracePort
from observer_runtime.semantic_probe import Pins, Trace


class BOObserver:
    def __init__(self, model: dict, build_id: str, mode: str = "on", path: str | None = None,
                 capacity: int = 8192):
        self.mode, self.path = mode, Path(path) if path else None
        self.lock = threading.Lock()
        self.events = []
        self.pins = Pins(model,build_id,enabled=mode=="on",sink=self.write,capacity=capacity)

    def write(self, text: str) -> None:
        event = json.loads(text)
        with self.lock:
            self.events.append(event)
        if self.path:
            self.path.parent.mkdir(parents=True,exist_ok=True)
            with self.path.open("a",encoding="utf-8") as stream:
                stream.write(text+"\n")

    def trace(self, entity: str, attempt: str) -> TracePort:
        if self.mode=="fault":
            def broken(*args, **kwargs):
                raise RuntimeError("injected observer failure")
            return TracePort(broken)
        return TracePort(Trace(self.pins,entity,attempt).record) if self.mode=="on" else TracePort()

    def snapshot(self) -> list[dict]:
        self.pins.flush()
        with self.lock:
            return list(self.events)

    def health(self) -> dict:
        return {**self.pins.health(),"mode":self.mode,
                "evidence":"gap" if self.mode!="on" or self.pins.errors or self.pins.dropped else "available"}

    def close(self) -> None:
        self.pins.close()
