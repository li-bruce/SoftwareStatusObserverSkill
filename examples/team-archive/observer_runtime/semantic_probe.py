"""Explicit, selected, bounded semantic observations; no business decisions."""
from __future__ import annotations
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import queue
import threading
import time
import uuid
try:
    from .bo_retention import EventHistory
except ImportError:
    from bo_retention import EventHistory


def selected(value, spec, depth=0):
    if depth > 6:
        raise ValueError("capture nesting limit")
    if isinstance(spec, dict):
        if not isinstance(value, dict):
            raise ValueError("expected selected fields")
        return {k: selected(value[k], s, depth+1) for k, s in spec.items() if k in value}
    if isinstance(spec, list):
        if not isinstance(value, list) or len(value) > 64 or len(spec) != 1:
            raise ValueError("bounded list required")
        return [selected(v, spec[0], depth+1) for v in value]
    if value is None:
        return None
    if spec in {"number", "scalar"} and type(value) in (int, float) and math.isfinite(value):
        return value
    if spec in {"boolean", "scalar"} and type(value) is bool:
        return value
    if spec in {"string", "scalar"} and isinstance(value, str) and len(value) <= 256:
        return value
    raise ValueError("unapproved type or value length")


class Pins:
    def __init__(self, model, build_id, *, path=None, enabled=True, sink=None, capacity=2048,
                 project_root=None, retention=None):
        self.model, self.build_id, self.enabled = model, build_id, enabled
        self.nodes = {n["id"]: n for n in model["nodes"]}
        self.path = Path(path) if path else None
        # The public path sink is bounded too, not only example adapters. An
        # explicit project root loads its policy; path-only uses bounded defaults.
        self.history = EventHistory(project_root=project_root, path=self.path, limits=retention) if sink is None and self.path else None
        self.run_id = uuid.uuid4().hex[:12]
        self.seq = self.written = self.errors = self.dropped = 0
        self.bo_scope = None
        self.bo_filtered = 0
        self.queue = queue.Queue(maxsize=max(1, capacity))
        self.lock = threading.Lock()
        self.closed = False
        self.stop = threading.Event()
        self.sink = sink or self._write
        self.thread = threading.Thread(target=self._worker, daemon=True, name="semantic-pins")
        if enabled:
            self.thread.start()

    def attempt(self, entity):
        return Trace(self, entity, uuid.uuid4().hex[:10])

    def bo_set_scope(self, node_ids=None):
        """Select observations only; never alter the application's execution."""
        scope = None if node_ids is None else frozenset(node_ids)
        if scope is not None and not scope <= self.nodes.keys():
            raise ValueError('Unknown observation node')
        with self.lock:
            self.bo_scope = scope

    def _write(self, text):
        if self.history is None: raise ValueError('path or bounded sink is required')
        before = self.history.log_errors
        self.history.append(json.loads(text))
        if self.history.log_errors != before: raise OSError('bounded observation log write failed')

    def _worker(self):
        while not self.stop.is_set() or not self.queue.empty():
            try:
                text = self.queue.get(timeout=.05)
            except queue.Empty:
                continue
            try:
                self.sink(text)
                self.written += 1
            except Exception:
                self.errors += 1
            finally:
                self.queue.task_done()

    def health(self):
        return {"enabled": self.enabled, "run_id": self.run_id, "attempted": self.seq,
                "written": self.written, "errors": self.errors, "dropped": self.dropped,
                "queued": self.queue.unfinished_tasks, "filtered": self.bo_filtered,
                "capture_nodes": sorted(self.bo_scope) if self.bo_scope is not None else None,
                'retention': self.history.health() if self.history is not None else None}

    def flush(self, timeout=2):
        deadline = time.monotonic() + timeout
        while self.queue.unfinished_tasks and time.monotonic() < deadline:
            time.sleep(.005)
        return not self.queue.unfinished_tasks

    def close(self):
        self.closed = True
        self.flush()
        self.stop.set()
        if self.thread.is_alive():
            self.thread.join(.1)


class Trace:
    def __init__(self, pins, entity, attempt):
        self.pins, self.entity, self.attempt_id = pins, entity, attempt

    def record(self, node, phase, basis, builder, *, depends=(), call_id=None, parent_call_id=None, scope='attempt'):
        p = self.pins
        if not p.enabled or p.closed:
            return None
        if p.bo_scope is not None and node not in p.bo_scope:
            p.bo_filtered += 1
            return None  # Skip payload construction as well as the event.
        try:
            if scope not in {'attempt', 'entity', 'application'}:
                raise ValueError('unknown observation scope')
            spec = p.nodes[node]["capture"]
            values = builder()
            inputs = selected(values.get("inputs", {}), spec.get("in", {}))
            outputs = selected(values.get("outputs", {}), spec.get("out", {}))
            clean_basis = selected(basis, {"param_version": "number", "epoch": "number", "clock": "number"})
            refs = [{"event": eid, "type": kind} for eid, kind in depends if eid]
            if len(refs) > 128:
                raise ValueError("too many references")
            with p.lock:
                p.seq += 1
                eid = f"{p.run_id}:{p.seq}"
                event = {"schema_version": 3, "id": eid, "seq": p.seq, "run_id": p.run_id,
                    "build_id": p.build_id, "model_revision": p.model["revision"], "entity": self.entity,
                    "attempt": self.attempt_id, "node": node, "phase": phase,
                    "call_id": call_id or f"{self.attempt_id}:{node}", "parent_call_id": parent_call_id,
                    "basis": clean_basis, "inputs": inputs, "outputs": outputs, "depends": refs,
                    "observed_at": datetime.now(timezone.utc).isoformat()}
                if scope != 'attempt': event['scope'] = scope
                text = json.dumps(event, ensure_ascii=False, allow_nan=False)
                if len(text.encode()) > 24576:
                    raise ValueError("event too large")
                p.queue.put_nowait(text)
            return eid
        except queue.Full:
            p.dropped += 1
        except Exception:
            p.errors += 1
        return None
