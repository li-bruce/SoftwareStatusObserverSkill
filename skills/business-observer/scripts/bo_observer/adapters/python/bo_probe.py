"""Bounded, fault-isolated JSON transport. Standard library only."""

from contextvars import ContextVar
from datetime import datetime, timezone
import json
import math
import queue
import threading
import time
from urllib.request import Request, urlopen
import uuid

_bo_internal = ContextVar("bo_transport_internal", default=False)


def bo_selected(value, spec, depth=0):
    """Copy only declared fields, with bounded nesting, string length, arrays, and numbers."""
    if depth > 6:
        raise ValueError("capture depth exceeded")
    if isinstance(spec, dict):
        if not isinstance(value, dict):
            raise ValueError("expected selected object")
        return {k: bo_selected(value[k], s, depth + 1) for k, s in spec.items() if k in value}
    if isinstance(spec, list):
        if not isinstance(value, list) or len(spec) != 1 or len(value) > 64:
            raise ValueError("bounded array required")
        return [bo_selected(v, spec[0], depth + 1) for v in value]
    if value is None:
        return None
    if (
        spec in ("number", "scalar")
        and type(value) in (int, float)
        and math.isfinite(value)
        and (type(value) is not int or abs(value) <= 9007199254740991)
    ):
        return value
    if spec in ("boolean", "scalar") and type(value) is bool:
        return value
    if spec in ("string", "scalar") and isinstance(value, str) and len(value) <= 256:
        return value
    raise ValueError("unapproved capture type")


class BOProbe:
    def __init__(
        self,
        project,
        build_id,
        *,
        endpoint="",
        token="",
        run_id=None,
        producer_id=None,
        enabled=True,
        capacity=256,
        timeout=0.5,
        sink=None,
    ):
        self.bo_project, self.bo_build = project, build_id
        self.bo_endpoint, self.bo_token, self.bo_timeout, self.bo_sink = (
            endpoint,
            token,
            timeout,
            sink,
        )
        self.bo_run, self.bo_producer = run_id or uuid.uuid4().hex, producer_id or uuid.uuid4().hex
        self.bo_enabled = enabled
        self.bo_seq = self.bo_errors = self.bo_dropped = self.bo_suppressed = 0
        self.bo_queue = queue.Queue(maxsize=max(1, capacity))
        self.bo_lock = threading.Lock()
        self.bo_closed = threading.Event()
        self.bo_nodes = {n["id"]: n for n in project["model"]["nodes"]}
        excluded = project["model"].get("implementation", {}).get("excluded", {})
        self.bo_excluded = {
            n["id"]
            for n in project["model"]["nodes"]
            if n.get("source")
            and excluded.get(n["source"]["path"] + "::" + n["source"]["symbol"], {}).get("category")
            == "observer"
        }
        self.bo_worker = threading.Thread(
            target=self.bo_drain, daemon=True, name="bo-json-transport"
        )
        if enabled:
            self.bo_worker.start()

    def bo_base(self, protocol):
        return {
            "protocol": protocol,
            "project_id": self.bo_project["project_id"],
            "model_revision": self.bo_project["model"]["revision"],
            "build_id": self.bo_build,
            "run_id": self.bo_run,
            "producer_id": self.bo_producer,
        }

    def bo_put(self, kind, body):
        raw = json.dumps(body, ensure_ascii=False, allow_nan=False).encode()
        if len(raw) > 24576:
            raise ValueError("observation too large")
        self.bo_queue.put_nowait((kind, raw))
        return True

    def record(
        self,
        node,
        phase,
        builder,
        *,
        entity="application",
        attempt="application",
        scope="application",
        basis=None,
        call_id=None,
        parent_call_id=None,
        depends=(),
        revision=None,
    ):
        """Build and enqueue a selected observation without changing the business result.

        Suppress observer activity and recursive capture. Count failures locally and
        return None when an observation cannot be queued.
        """
        if not self.bo_enabled or self.bo_closed.is_set():
            return None
        if _bo_internal.get() or node in self.bo_excluded:
            self.bo_suppressed += 1
            return None
        token = _bo_internal.set(True)
        try:
            if phase not in {
                "enter",
                "return",
                "read",
                "decision",
                "wait",
                "commit",
                "change",
                "error",
            }:
                raise ValueError("invalid phase")
            values = builder()
            spec = self.bo_nodes[node]["capture"]
            with self.bo_lock:
                self.bo_seq += 1
                eid = f"{self.bo_run}:{self.bo_producer}:{self.bo_seq}"
                body = {
                    **self.bo_base("bo-event/v1"),
                    "schema_version": 3,
                    "seq": self.bo_seq,
                    "id": eid,
                    "node": node,
                    "phase": phase,
                    "entity": entity,
                    "attempt": attempt,
                    "scope": scope,
                    "basis": bo_selected(
                        basis or {},
                        {"param_version": "number", "epoch": "number", "clock": "number"},
                    ),
                    "call_id": call_id or eid,
                    "parent_call_id": parent_call_id,
                    "inputs": bo_selected(values.get("inputs", {}), spec.get("in", {})),
                    "outputs": bo_selected(values.get("outputs", {}), spec.get("out", {})),
                    "depends": list(depends),
                    "observed_at": datetime.now(timezone.utc).isoformat(),
                }
                if revision is not None:
                    if type(revision) is not int or not 0 <= revision <= 9007199254740991:
                        raise ValueError("invalid state revision")
                    body["revision"] = revision
                self.bo_put("events", body)
            return eid
        except queue.Full:
            self.bo_dropped += 1
        except Exception:
            self.bo_errors += 1
        finally:
            _bo_internal.reset(token)
        return None

    def snapshot(
        self,
        instance_id,
        state,
        context,
        revision,
        evidence_id,
        *,
        event=None,
        guards=None,
        payload=None,
        configuration=None,
    ):
        """Queue a state snapshot associated with an already identified business event."""
        if not self.bo_enabled or self.bo_closed.is_set():
            return False
        if _bo_internal.get():
            self.bo_suppressed += 1
            return False
        try:
            return self.bo_put(
                "snapshots",
                {
                    **self.bo_base("bo-snapshot/v1"),
                    "instance_id": instance_id,
                    "state": state,
                    "context": context,
                    "revision": revision,
                    "evidence_id": evidence_id,
                    "event": event,
                    "guards": guards,
                    "payload": payload,
                    "configuration": configuration,
                },
            )
        except queue.Full:
            self.bo_dropped += 1
        except Exception:
            self.bo_errors += 1
        return False

    def bo_drain(self):
        """Send queued envelopes on the worker thread and count delivery failures."""
        while not self.bo_closed.is_set() or not self.bo_queue.empty():
            try:
                kind, raw = self.bo_queue.get(timeout=0.05)
            except queue.Empty:
                continue
            token = _bo_internal.set(True)
            try:
                if self.bo_sink:
                    self.bo_sink(json.loads(raw), kind)
                else:
                    req = Request(
                        self.bo_endpoint + "/api/bo/" + kind,
                        data=raw,
                        headers={"Content-Type": "application/json", "X-BO-Token": self.bo_token},
                        method="POST",
                    )
                    with urlopen(req, timeout=self.bo_timeout) as response:
                        response.read(32768)
            except Exception:
                self.bo_errors += 1
            finally:
                _bo_internal.reset(token)
                self.bo_queue.task_done()

    def flush(self, timeout=2):
        """Wait up to the supplied timeout for queued observations to finish sending."""
        deadline = time.monotonic() + timeout
        while self.bo_queue.unfinished_tasks and time.monotonic() < deadline:
            time.sleep(0.005)
        return not self.bo_queue.unfinished_tasks

    def close(self):
        """Request worker shutdown and bound the time spent joining it."""
        self.bo_closed.set()
        if self.bo_enabled:
            self.bo_worker.join(1)
