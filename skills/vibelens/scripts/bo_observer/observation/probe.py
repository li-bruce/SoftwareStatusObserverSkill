"""Best-effort, bounded, post-commit observer. Python standard library only."""

from __future__ import annotations
from datetime import datetime, timezone
import json
from itertools import islice
import math
from pathlib import Path
import queue
import threading
import time
import uuid

try:
    from ...observation_scope import bo_internal, bo_is_internal
except ImportError:
    from observation_scope import bo_internal, bo_is_internal


class Probe:
    def __init__(
        self,
        *,
        path=None,
        build_id,
        model_revision,
        fields,
        nodes,
        enabled=True,
        queue_size=1024,
        sink=None,
        run_id=None,
    ):
        self.enabled = enabled
        self.build_id, self.model_revision = build_id, model_revision
        self.fields = {k: set(v) for k, v in fields.items()}
        self.nodes = set(nodes)
        self.run_id = run_id or uuid.uuid4().hex
        self.path = Path(path) if path is not None else None
        self._sink = sink or self._write
        self._queue = queue.Queue(maxsize=max(1, queue_size))
        self._seq, self._dropped, self._errors, self._written = 0, 0, 0, 0
        self._closed = False
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self._thread = None
        if enabled:
            self._thread = threading.Thread(
                target=self._worker, name="business-observer", daemon=True
            )
            self._thread.start()

    @staticmethod
    def _scalar(value):
        if value is None or type(value) in (bool, int):
            return value
        if type(value) is float and math.isfinite(value):
            return value
        if isinstance(value, str) and len(value) <= 256:
            return value
        raise ValueError("payload value not an allowed bounded scalar")

    def emit(self, *, kind, node_id, entity_id, request_id, attempt_id, tx_id, payload):
        if not self.enabled or self._closed or bo_is_internal():
            return False
        try:
            if (
                kind not in {"fact", "decision", "transition", "effect"}
                or node_id not in self.nodes
            ):
                raise ValueError("undeclared event kind/node")
            clean = {}
            for k, value in payload.items():
                if k not in self.fields.get(kind, set()):
                    continue
                if isinstance(value, list):
                    if len(value) > 64:
                        raise ValueError("payload list too large")
                    clean[k] = [self._scalar(v) for v in value]
                else:
                    clean[k] = self._scalar(value)
            for identifier in (node_id, entity_id, request_id, attempt_id, tx_id):
                if not isinstance(identifier, str) or not identifier or len(identifier) > 128:
                    raise ValueError("invalid correlation id")
            with self._lock:
                self._seq += 1
                seq = self._seq
                event = {
                    "schema_version": 1,
                    "event_id": f"{self.run_id}:{seq}",
                    "run_id": self.run_id,
                    "seq": seq,
                    "build_id": self.build_id,
                    "model_revision": self.model_revision,
                    "request_id": request_id,
                    "attempt_id": attempt_id,
                    "tx_id": tx_id,
                    "entity_id": entity_id,
                    "node_id": node_id,
                    "observed_at": datetime.now(timezone.utc).isoformat(),
                    "kind": kind,
                    "payload": clean,
                }
                encoded = json.dumps(event, ensure_ascii=False, allow_nan=False)
                if len(encoded.encode()) > 16384:
                    raise ValueError("event too large")
                self._queue.put_nowait(encoded)
            return True
        except queue.Full:
            self._dropped += 1
        except Exception:
            self._errors += 1
        return False

    def capture(self, builder):
        if not self.enabled or self._closed or bo_is_internal():
            return
        try:
            with bo_internal():
                events = list(islice(builder(), 257))
            for i, event in enumerate(events):
                if i >= 256:
                    self._dropped += 1
                    break
                self.emit(**event)
        except Exception:
            self._errors += 1

    def _write(self, encoded):
        if self.path is None:
            raise ValueError("no sink path")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as f:
            f.write(encoded + "\n")

    def _worker(self):
        while not self._stop.is_set() or not self._queue.empty():
            try:
                encoded = self._queue.get(timeout=0.05)
            except queue.Empty:
                continue
            try:
                with bo_internal():
                    self._sink(encoded)
                self._written += 1
            except Exception:
                self._errors += 1
            finally:
                self._queue.task_done()

    def health(self):
        return {
            "enabled": self.enabled,
            "run_id": self.run_id,
            "attempted": self._seq,
            "written": self._written,
            "queued": self._queue.unfinished_tasks,
            "dropped": self._dropped,
            "errors": self._errors,
            "closed": self._closed,
        }

    def flush(self, timeout=2):
        end = time.monotonic() + timeout
        while self._queue.unfinished_tasks and time.monotonic() < end:
            time.sleep(0.005)
        return self._queue.unfinished_tasks == 0

    def close(self, timeout=2):
        self._closed = True
        drained = self.flush(timeout)
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=0.1)
        return drained
